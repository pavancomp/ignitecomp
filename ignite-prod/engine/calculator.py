"""
Ignite Step-Binary Compensation Calculator
India market — all amounts in INR (₹).

Key mechanics:
  • Steps = floor(min(left_cv, right_cv) / cv_per_step), capped by rank
  • First 2 lifetime steps earn 50% of the rank step rate
  • Green coins bridge unbalanced weeks (3/6/12-coin tiers, 12 lifetime cap)
  • Yellow coins: 1 coin per yellow_coin_step_interval cumulative steps
  • Matching bonus: strong-leg unilevel, 10 levels, Platinum Star+
  • Maintenance bonuses: Emerald / Crown Diamond, one-time after hold period
  • TDS: Section 194H, 5% on FY income above ₹15,000 threshold
  • Carry-forward: persisted per cycle; strong leg flushed at flush_ratio × weak leg
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


# ── INR rounding ────────────────────────────────────────────────────────────

def round_inr(amount: int, unit: int = 500) -> int:
    """Round INR amount to nearest `unit` (default ₹500)."""
    if unit <= 0:
        return amount
    return int(Decimal(amount).quantize(Decimal(unit), rounding=ROUND_HALF_UP))


# ── Data containers ─────────────────────────────────────────────────────────

@dataclass
class RankRow:
    name: str
    min_cumulative_steps: int
    min_direct_cv: int
    step_rate_inr: int               # ₹ per full step
    max_weekly_steps: Optional[int]  # None = unlimited
    matching_bonus_levels: int       # 0 = no matching
    maintenance_bonus_inr: int       # 0 = none
    maintenance_hold_months: int     # consecutive months required


@dataclass
class PlanParams:
    cv_per_step: int = 1800
    flush_ratio: float = 3.0
    tds_rate: float = 0.05
    tds_threshold_inr: int = 15_000
    inr_rounding: int = 500
    coin_lifetime_cap: int = 12
    yellow_coin_step_interval: int = 6
    first_step_half_rate: bool = True


@dataclass
class CycleInput:
    distributor_id: int
    left_cv_this_cycle: int
    right_cv_this_cycle: int
    left_cv_carry_in: int            # from previous cycle
    right_cv_carry_in: int
    lifetime_steps_before: int       # cumulative steps before this cycle
    direct_cv_this_cycle: int        # personal purchases CV
    green_coins_available: int       # balance before this cycle
    green_coins_lifetime: int        # total ever earned (for cap)
    cumulative_matching_bonus_inr: int = 0  # from tree engine
    maintenance_months_at_rank: int = 0     # consecutive months holding current rank
    maintenance_already_paid: bool = False  # idempotency guard


@dataclass
class CycleResult:
    distributor_id: int
    rank_name: str
    steps_earned: int
    lifetime_steps_after: int

    # All INR
    step_commission_inr: int = 0
    green_coin_income_inr: int = 0
    matching_bonus_inr: int = 0
    maintenance_bonus_inr: int = 0
    gross_commission_inr: int = 0
    tds_deducted_inr: int = 0
    net_payable_inr: int = 0

    # Carry-forward output
    left_cv_carry_out: int = 0
    right_cv_carry_out: int = 0

    # Coin outputs
    yellow_coins_earned: int = 0
    green_coins_converted: int = 0

    # Debug / breakdown
    breakdown: dict = field(default_factory=dict)


# ── Green coin conversion table ──────────────────────────────────────────────

# (coins_to_convert, inr_value) — only multiples of 3
GREEN_COIN_TIERS = [
    (12, 21250),  # ₹21,250 for 12 coins  (≈$250)
    (6,  10625),  # ₹10,625 for 6 coins   (≈$125)
    (3,   3400),  # ₹3,400  for 3 coins   (≈$40)
]


def best_green_coin_conversion(
    available: int,
    lifetime_used: int,
    lifetime_cap: int
) -> tuple[int, int]:
    """
    Return (coins_to_convert, inr_earned).
    Cannot exceed (lifetime_cap - lifetime_used) remaining slots.
    """
    remaining_cap = lifetime_cap - lifetime_used
    if remaining_cap <= 0 or available < 3:
        return 0, 0

    for coins, inr in GREEN_COIN_TIERS:
        usable = min(available, remaining_cap)
        if usable >= coins:
            return coins, inr

    return 0, 0


# ── Rank determination ───────────────────────────────────────────────────────

def determine_rank(
    lifetime_steps: int,
    direct_cv: int,
    rank_table: list[RankRow],
) -> RankRow:
    """
    Walk rank table from highest to lowest; return highest rank qualified.
    Qualification: lifetime_steps >= min_cumulative_steps AND direct_cv >= min_direct_cv.
    """
    eligible = [
        r for r in rank_table
        if lifetime_steps >= r.min_cumulative_steps and direct_cv >= r.min_direct_cv
    ]
    if not eligible:
        return rank_table[0]  # Silver Star baseline
    return max(eligible, key=lambda r: r.min_cumulative_steps)


# ── Main calculator ──────────────────────────────────────────────────────────

def calculate_cycle_commission(
    inp: CycleInput,
    plan: PlanParams,
    rank_table: list[RankRow],
    fy_gross_already_inr: int = 0,  # FY gross income prior to this cycle (for TDS)
) -> CycleResult:
    """
    Core compensation calculation. Pure function — no DB access.
    Returns CycleResult with full breakdown.
    """
    # ── 1. Combine carry + this-cycle CV ─────────────────────────────────
    left_total  = inp.left_cv_carry_in  + inp.left_cv_this_cycle
    right_total = inp.right_cv_carry_in + inp.right_cv_this_cycle

    # ── 2. Determine rank ─────────────────────────────────────────────────
    rank = determine_rank(inp.lifetime_steps_before, inp.direct_cv_this_cycle, rank_table)

    # ── 3. Calculate steps ────────────────────────────────────────────────
    weak_leg  = min(left_total, right_total)
    strong_leg = max(left_total, right_total)
    raw_steps = weak_leg // plan.cv_per_step

    if rank.max_weekly_steps is not None:
        steps = min(raw_steps, rank.max_weekly_steps)
    else:
        steps = raw_steps

    # ── 4. Step commission — first 2 lifetime steps at 50% ───────────────
    step_commission = 0
    ls_before = inp.lifetime_steps_before
    ls_after  = ls_before + steps

    for i in range(steps):
        lifetime_index = ls_before + i + 1  # 1-indexed
        if plan.first_step_half_rate and lifetime_index <= 2:
            rate = rank.step_rate_inr // 2
        else:
            rate = rank.step_rate_inr
        step_commission += rate

    # ── 5. Green coin bridge ──────────────────────────────────────────────
    coins_to_convert, green_coin_income = best_green_coin_conversion(
        available=inp.green_coins_available,
        lifetime_used=inp.green_coins_lifetime,
        lifetime_cap=plan.coin_lifetime_cap,
    )

    # ── 6. Yellow coin award ──────────────────────────────────────────────
    # 1 yellow coin for each multiple of yellow_coin_step_interval crossed this cycle
    milestones_before = ls_before // plan.yellow_coin_step_interval
    milestones_after  = ls_after  // plan.yellow_coin_step_interval
    yellow_earned = milestones_after - milestones_before

    # ── 7. Matching bonus (passed in from tree engine) ────────────────────
    matching_bonus = inp.cumulative_matching_bonus_inr

    # ── 8. Maintenance bonus ──────────────────────────────────────────────
    maintenance_bonus = 0
    if (
        not inp.maintenance_already_paid
        and rank.maintenance_bonus_inr > 0
        and inp.maintenance_months_at_rank >= rank.maintenance_hold_months
    ):
        maintenance_bonus = rank.maintenance_bonus_inr

    # ── 9. Gross commission ───────────────────────────────────────────────
    gross_raw = step_commission + green_coin_income + matching_bonus + maintenance_bonus
    gross_commission = round_inr(gross_raw, plan.inr_rounding)

    # ── 10. TDS calculation (Section 194H) ────────────────────────────────
    tds_deducted = _calculate_tds(
        gross_this_cycle=gross_commission,
        fy_gross_before=fy_gross_already_inr,
        threshold=plan.tds_threshold_inr,
        rate=plan.tds_rate,
        rounding=plan.inr_rounding,
    )

    net_payable = gross_commission - tds_deducted

    # ── 11. Carry-forward ─────────────────────────────────────────────────
    matched_cv = steps * plan.cv_per_step
    left_carry_raw  = left_total  - matched_cv if left_total  >= matched_cv else left_total
    right_carry_raw = right_total - matched_cv if right_total >= matched_cv else right_total

    # Flush strong leg: strong leg carry capped at flush_ratio × weak leg carry
    weak_carry   = min(left_carry_raw, right_carry_raw)
    strong_carry = max(left_carry_raw, right_carry_raw)
    flush_cap    = int(weak_carry * plan.flush_ratio)
    strong_carry = min(strong_carry, flush_cap)

    if left_carry_raw <= right_carry_raw:
        left_carry_out  = left_carry_raw
        right_carry_out = strong_carry
    else:
        left_carry_out  = strong_carry
        right_carry_out = right_carry_raw

    result = CycleResult(
        distributor_id=inp.distributor_id,
        rank_name=rank.name,
        steps_earned=steps,
        lifetime_steps_after=ls_after,
        step_commission_inr=step_commission,
        green_coin_income_inr=green_coin_income,
        matching_bonus_inr=matching_bonus,
        maintenance_bonus_inr=maintenance_bonus,
        gross_commission_inr=gross_commission,
        tds_deducted_inr=tds_deducted,
        net_payable_inr=net_payable,
        left_cv_carry_out=left_carry_out,
        right_cv_carry_out=right_carry_out,
        yellow_coins_earned=yellow_earned,
        green_coins_converted=coins_to_convert,
        breakdown={
            "left_total_cv": left_total,
            "right_total_cv": right_total,
            "weak_leg_cv": weak_leg,
            "strong_leg_cv": strong_leg,
            "raw_steps": raw_steps,
            "capped_steps": steps,
            "step_commission_raw": step_commission,
            "gross_raw": gross_raw,
        },
    )
    return result


def _calculate_tds(
    gross_this_cycle: int,
    fy_gross_before: int,
    threshold: int,
    rate: float,
    rounding: int,
) -> int:
    """
    TDS = 5% of amount above ₹15,000 threshold, cumulative in FY.
    Only deduct on the portion not yet TDS-assessed.
    """
    fy_gross_after = fy_gross_before + gross_this_cycle

    if fy_gross_after <= threshold:
        return 0

    taxable_before = max(0, fy_gross_before - threshold)
    taxable_after  = max(0, fy_gross_after  - threshold)
    incremental_taxable = taxable_after - taxable_before

    if incremental_taxable <= 0:
        return 0

    tds_raw = int(incremental_taxable * rate)
    return round_inr(tds_raw, rounding)
