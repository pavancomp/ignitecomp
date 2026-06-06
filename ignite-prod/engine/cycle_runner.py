"""
Cycle Runner v3 — center-keyed, idempotent, correct enum comparisons.
"""
import json, logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, func

from config import get_settings
from db.models import (
    Cycle, CycleStatus, CommissionLedger, DistributorCarryForward,
    DistributorRank, Distributor, DistributorStatus, TrackingCenter,
    CoinBalance, CoinTransaction, TaxTracking, TdsStatement,
    SystemEvent, RankConfig, PlanConfig, Order, OrderStatus, OrderType,
)
from engine.calculator import PlanParams, RankRow, CycleInput, calculate_cycle_commission
from engine.tree import get_leg_cv, calculate_matching_bonus

logger = logging.getLogger(__name__)


def _fy(dt):
    y = dt.year
    return f"{y}-{str(y+1)[2:]}" if dt.month >= 4 else f"{y-1}-{str(y)[2:]}"


async def run_cycle_close(cycle_id, actor_id, session_factory):
    async with session_factory() as db:
        try:
            await _do_close(db, cycle_id, actor_id)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.exception(f"Cycle {cycle_id} failed: {exc}")
            async with session_factory() as db2:
                db2.add(SystemEvent(event_type="cycle_close_failed",
                                    payload=json.dumps({"cycle_id": cycle_id, "error": str(exc)}),
                                    status="error"))
                # Also reset status to open so it can be retried
                cycle = await db2.get(Cycle, cycle_id)
                if cycle and cycle.status == CycleStatus.PROCESSING:
                    cycle.status = CycleStatus.OPEN
                await db2.commit()


async def _do_close(db: AsyncSession, cycle_id: int, actor_id: int):
    cycle = await db.get(Cycle, cycle_id)
    if not cycle: raise ValueError(f"Cycle {cycle_id} not found")

    plan_cfg = await db.get(PlanConfig, 1)
    plan = PlanParams(
        cv_per_step=plan_cfg.cv_per_step, flush_ratio=float(plan_cfg.flush_ratio),
        tds_rate=float(plan_cfg.tds_rate), tds_threshold_inr=plan_cfg.tds_threshold_inr,
        inr_rounding=plan_cfg.inr_rounding, coin_lifetime_cap=plan_cfg.coin_lifetime_cap,
        yellow_coin_step_interval=plan_cfg.yellow_coin_step_interval,
        first_step_half_rate=plan_cfg.first_step_half_rate,
    )

    rank_cfgs = (await db.execute(
        select(RankConfig).where(RankConfig.is_active == True).order_by(RankConfig.sort_order)
    )).scalars().all()
    rank_table = [RankRow(r.rank_name, r.min_cumulative_steps, r.min_direct_cv, r.step_rate_inr,
                          r.max_weekly_steps, r.matching_bonus_levels, r.maintenance_bonus_inr,
                          r.maintenance_hold_months) for r in rank_cfgs]

    centers = (await db.execute(
        select(TrackingCenter).join(Distributor)
        .where(TrackingCenter.is_active == True,
               Distributor.status == DistributorStatus.ACTIVE,
               Distributor.distributor_id != "ROOT")
    )).scalars().all()

    fy = _fy(datetime.now(tz=timezone.utc))

    # Pass 1: step commissions only (for matching bonus map)
    step_comm_map: dict[int, int] = {}
    pass1: dict[int, object] = {}
    for center in centers:
        r = await _calc_center(db, center, cycle_id, plan, rank_table, fy)
        if r:
            step_comm_map[center.id] = r.step_commission_inr
            pass1[center.id] = r

    # Pass 2: finalize with matching bonus, write all records
    fy_gross_map: dict[int, int] = {}
    ba_gross: dict[int, int] = {}

    for center in centers:
        # Idempotency
        if (await db.execute(select(CommissionLedger).where(
            CommissionLedger.center_id == center.id, CommissionLedger.cycle_id == cycle_id
        ))).scalar_one_or_none():
            continue

        # Matching bonus
        matching = 0
        if center.position_id and center.id in pass1:
            rank_name = pass1[center.id].rank_name
            matching = await calculate_matching_bonus(db, center.position_id, cycle_id,
                                                       rank_name, rank_table, step_comm_map)

        # FY gross before this cycle (read once per BA)
        if center.distributor_id not in fy_gross_map:
            tax = (await db.execute(
                select(TaxTracking).where(TaxTracking.distributor_id == center.distributor_id,
                                          TaxTracking.financial_year == fy)
            )).scalar_one_or_none()
            fy_gross_map[center.distributor_id] = tax.gross_income_inr if tax else 0

        final = await _calc_center(db, center, cycle_id, plan, rank_table, fy,
                                    matching_bonus=matching,
                                    fy_gross_before=fy_gross_map[center.distributor_id])
        if not final: continue

        # Write ledger
        db.add(CommissionLedger(
            center_id=center.id, distributor_id=center.distributor_id, cycle_id=cycle_id,
            rank_at_cycle=final.rank_name, steps_earned=final.steps_earned,
            lifetime_steps_after=final.lifetime_steps_after,
            step_commission_inr=final.step_commission_inr,
            green_coin_income_inr=final.green_coin_income_inr,
            matching_bonus_inr=final.matching_bonus_inr,
            maintenance_bonus_inr=final.maintenance_bonus_inr,
            gross_commission_inr=final.gross_commission_inr,
            tds_deducted_inr=final.tds_deducted_inr,
            net_payable_inr=final.net_payable_inr,
            left_cv_carry_out=final.left_cv_carry_out,
            right_cv_carry_out=final.right_cv_carry_out,
            yellow_coins_earned=final.yellow_coins_earned,
            green_coins_converted=final.green_coins_converted,
        ))

        # Write carry-forward
        db.add(DistributorCarryForward(
            center_id=center.id, distributor_id=center.distributor_id, cycle_id=cycle_id,
            left_cv_carry=final.left_cv_carry_out, right_cv_carry=final.right_cv_carry_out,
        ))

        # Accumulate for TDS loop
        ba_gross[center.distributor_id] = ba_gross.get(center.distributor_id, 0) + final.gross_commission_inr
        fy_gross_map[center.distributor_id] += final.gross_commission_inr  # running total for next center

        # Update rank
        hist = (await db.execute(
            select(DistributorRank).where(DistributorRank.distributor_id == center.distributor_id)
            .order_by(DistributorRank.achieved_at.desc()).limit(1)
        )).scalars().all()
        if not hist or hist[0].rank_name != final.rank_name:
            db.add(DistributorRank(distributor_id=center.distributor_id, rank_name=final.rank_name,
                                   achieved_at=cycle.end_date, cycle_id=cycle_id,
                                   cumulative_steps=final.lifetime_steps_after))
        elif hist:
            hist[0].cumulative_steps = final.lifetime_steps_after

        # Coins
        coins = (await db.execute(
            select(CoinBalance).where(CoinBalance.distributor_id == center.distributor_id)
        )).scalar_one_or_none()
        if coins:
            if final.green_coins_converted > 0:
                coins.green_coins = max(0, coins.green_coins - final.green_coins_converted)
                coins.green_coins_lifetime += final.green_coins_converted
                db.add(CoinTransaction(distributor_id=center.distributor_id, center_id=center.id,
                                       cycle_id=cycle_id, coin_type="green",
                                       delta=-final.green_coins_converted, reason="bridge_conversion",
                                       inr_value=final.green_coin_income_inr))
            if final.yellow_coins_earned > 0:
                coins.yellow_coins += final.yellow_coins_earned
                db.add(CoinTransaction(distributor_id=center.distributor_id, center_id=center.id,
                                       cycle_id=cycle_id, coin_type="yellow",
                                       delta=final.yellow_coins_earned, reason="step_milestone",
                                       inr_value=0))

        await db.flush()

    # TDS tracking — one update per BA (aggregates across all their centers)
    for dist_id, gross in ba_gross.items():
        if gross <= 0: continue
        tds_cycle = (await db.execute(
            select(func.sum(CommissionLedger.tds_deducted_inr))
            .where(CommissionLedger.distributor_id == dist_id, CommissionLedger.cycle_id == cycle_id)
        )).scalar_one_or_none() or 0

        tax = (await db.execute(
            select(TaxTracking).where(TaxTracking.distributor_id == dist_id, TaxTracking.financial_year == fy)
        )).scalar_one_or_none()
        if tax:
            tax.gross_income_inr += gross
            tax.tds_deducted_inr += tds_cycle
        else:
            db.add(TaxTracking(distributor_id=dist_id, financial_year=fy,
                               gross_income_inr=gross, tds_deducted_inr=tds_cycle))

        ba = await db.get(Distributor, dist_id)
        stmt = (await db.execute(
            select(TdsStatement).where(TdsStatement.distributor_id == dist_id, TdsStatement.financial_year == fy)
        )).scalar_one_or_none()
        if stmt:
            stmt.gross_income_inr += gross
            stmt.tds_deducted_inr += tds_cycle
        else:
            db.add(TdsStatement(distributor_id=dist_id, financial_year=fy,
                                pan_number=ba.pan_number if ba else None,
                                gross_income_inr=gross, tds_deducted_inr=tds_cycle))

    # Finalize cycle
    totals = (await db.execute(
        select(func.sum(CommissionLedger.gross_commission_inr),
               func.sum(CommissionLedger.tds_deducted_inr),
               func.sum(CommissionLedger.net_payable_inr))
        .where(CommissionLedger.cycle_id == cycle_id)
    )).one()

    cycle.status = CycleStatus.CLOSED
    cycle.closed_at = datetime.now(tz=timezone.utc)
    cycle.total_payout_inr = totals[2] or 0
    cycle.total_tds_inr    = totals[1] or 0
    cycle.distributor_count = len(set(c.distributor_id for c in centers))
    cycle.center_count      = len(centers)
    db.add(SystemEvent(event_type="cycle_closed",
                       payload=json.dumps({"cycle_id": cycle_id, "centers": len(centers),
                                           "payout_inr": cycle.total_payout_inr}),
                       status="info"))


async def _calc_center(db, center, cycle_id, plan, rank_table, fy, matching_bonus=0, fy_gross_before=None):
    if not center.position_id: return None
    left_cv, right_cv = await get_leg_cv(db, center.position_id, cycle_id)

    carry = (await db.execute(
        select(DistributorCarryForward)
        .where(DistributorCarryForward.center_id == center.id)
        .order_by(DistributorCarryForward.cycle_id.desc()).limit(1)
    )).scalar_one_or_none()
    carry_in = (carry.left_cv_carry, carry.right_cv_carry) if carry and carry.cycle_id < cycle_id else (0, 0)

    # Use enum comparisons — NOT raw strings
    direct_cv = (await db.execute(
        select(func.sum(Order.cv_total)).where(
            Order.distributor_id == center.distributor_id,
            Order.cycle_id == cycle_id,
            Order.status == OrderStatus.VERIFIED,
            Order.order_type == OrderType.BA_PURCHASE,
        )
    )).scalar_one_or_none() or 0

    coins = (await db.execute(
        select(CoinBalance).where(CoinBalance.distributor_id == center.distributor_id)
    )).scalar_one_or_none()

    hist = (await db.execute(
        select(DistributorRank).where(DistributorRank.distributor_id == center.distributor_id)
        .order_by(DistributorRank.achieved_at.desc()).limit(1)
    )).scalars().all()
    lifetime_steps = hist[0].cumulative_steps if hist else 0

    if fy_gross_before is None:
        tax = (await db.execute(
            select(TaxTracking).where(TaxTracking.distributor_id == center.distributor_id,
                                      TaxTracking.financial_year == fy)
        )).scalar_one_or_none()
        fy_gross_before = tax.gross_income_inr if tax else 0

    maint_months = await _consec_months(db, center.distributor_id)
    maint_paid   = await _maint_paid(db, center.distributor_id)

    inp = CycleInput(
        distributor_id=center.distributor_id,
        left_cv_this_cycle=left_cv, right_cv_this_cycle=right_cv,
        left_cv_carry_in=carry_in[0], right_cv_carry_in=carry_in[1],
        lifetime_steps_before=lifetime_steps, direct_cv_this_cycle=direct_cv,
        green_coins_available=coins.green_coins if coins else 0,
        green_coins_lifetime=coins.green_coins_lifetime if coins else 0,
        cumulative_matching_bonus_inr=matching_bonus,
        maintenance_months_at_rank=maint_months,
        maintenance_already_paid=maint_paid,
    )
    return calculate_cycle_commission(inp, plan, rank_table, fy_gross_before)


async def _consec_months(db, dist_id):
    rows = (await db.execute(
        select(DistributorRank).where(DistributorRank.distributor_id == dist_id)
        .order_by(DistributorRank.achieved_at.desc()).limit(12)
    )).scalars().all()
    if not rows: return 0
    current = rows[0].rank_name; count = 0
    for r in rows:
        if r.rank_name == current: count += 1
        else: break
    return count


async def _maint_paid(db, dist_id):
    return bool((await db.execute(
        select(CommissionLedger).where(CommissionLedger.distributor_id == dist_id,
                                       CommissionLedger.maintenance_bonus_inr > 0).limit(1)
    )).scalar_one_or_none())
