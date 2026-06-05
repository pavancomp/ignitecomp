"""Seed: admin users, plan config, rank_config (all INR), products, tree root."""
from decimal import Decimal
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from passlib.context import CryptContext
from db.models import AdminUser, PlanConfig, RankConfig, Product, Distributor, TreePosition, TrackingCenter, CoinBalance, DistributorStatus, UserRole

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed_all(db: AsyncSession) -> None:
    await _seed_plan_config(db); await _seed_rank_config(db)
    await _seed_products(db); await _seed_admin_users(db)
    await _seed_tree_root(db); await db.commit()
    print("✓ Seed complete")


async def _seed_plan_config(db):
    if await db.get(PlanConfig, 1): return
    db.add(PlanConfig(id=1, cv_per_step=1800, flush_ratio=Decimal("3.0"), tds_rate=Decimal("0.0500"), tds_threshold_inr=15000, gst_threshold_inr=2000000, inr_rounding=500, coin_lifetime_cap=12, yellow_coin_step_interval=6, first_step_half_rate=True, cycle_type="weekly", max_centers_per_ba=3))


async def _seed_rank_config(db):
    if (await db.execute(select(func.count()).select_from(RankConfig))).scalar_one(): return
    ranks = [
        dict(rank_name="Silver Star",   min_cumulative_steps=0,   min_direct_cv=600,  step_rate_inr=21250, max_weekly_steps=None, matching_bonus_levels=0,  maintenance_bonus_inr=0,      maintenance_hold_months=0, sort_order=1),
        dict(rank_name="Titanium Star", min_cumulative_steps=2,   min_direct_cv=600,  step_rate_inr=25500, max_weekly_steps=None, matching_bonus_levels=0,  maintenance_bonus_inr=0,      maintenance_hold_months=0, sort_order=2),
        dict(rank_name="Gold Star",     min_cumulative_steps=5,   min_direct_cv=600,  step_rate_inr=29750, max_weekly_steps=None, matching_bonus_levels=0,  maintenance_bonus_inr=0,      maintenance_hold_months=0, sort_order=3),
        dict(rank_name="Platinum Star", min_cumulative_steps=10,  min_direct_cv=1200, step_rate_inr=34000, max_weekly_steps=None, matching_bonus_levels=10, maintenance_bonus_inr=0,      maintenance_hold_months=0, sort_order=4),
        dict(rank_name="Sapphire Star", min_cumulative_steps=25,  min_direct_cv=1200, step_rate_inr=38250, max_weekly_steps=None, matching_bonus_levels=10, maintenance_bonus_inr=0,      maintenance_hold_months=0, sort_order=5),
        dict(rank_name="Diamond Star",  min_cumulative_steps=50,  min_direct_cv=1800, step_rate_inr=42500, max_weekly_steps=None, matching_bonus_levels=10, maintenance_bonus_inr=0,      maintenance_hold_months=0, sort_order=6),
        dict(rank_name="Emerald Star",  min_cumulative_steps=100, min_direct_cv=1800, step_rate_inr=46750, max_weekly_steps=None, matching_bonus_levels=10, maintenance_bonus_inr=212500, maintenance_hold_months=2, sort_order=7),
        dict(rank_name="Crown Diamond", min_cumulative_steps=250, min_direct_cv=3600, step_rate_inr=48450, max_weekly_steps=None, matching_bonus_levels=10, maintenance_bonus_inr=425000, maintenance_hold_months=3, sort_order=8),
    ]
    for r in ranks: db.add(RankConfig(**r))


async def _seed_products(db):
    if (await db.execute(select(func.count()).select_from(Product))).scalar_one(): return
    for p in [
        dict(sku="SAN-ACT", name="SANAREY Activa",  ba_price_inr=51000, retail_price_inr=56100, cv=600, coins_awarded=1),
        dict(sku="SAN-SIM", name="SANAREY Simetra", ba_price_inr=51000, retail_price_inr=56100, cv=600, coins_awarded=1),
        dict(sku="SAN-ARI", name="SANAREY Aria",    ba_price_inr=51000, retail_price_inr=56100, cv=600, coins_awarded=1),
        dict(sku="SAN-BR9", name="SANAREY BR-9",    ba_price_inr=51000, retail_price_inr=56100, cv=600, coins_awarded=1),
        dict(sku="BRN-ANN", name="brAInify Annual", ba_price_inr=51000, retail_price_inr=56100, cv=600, coins_awarded=1),
    ]: db.add(Product(**p))


async def _seed_admin_users(db):
    for username, email, pw, role in [("admin","admin@ignite.in","Ignite@2026!",UserRole.ADMIN),("finance","finance@ignite.in","Finance@2026!",UserRole.FINANCE)]:
        if not (await db.execute(select(AdminUser).where(AdminUser.username==username))).scalar_one_or_none():
            db.add(AdminUser(username=username, email=email, hashed_password=pwd_ctx.hash(pw), role=role, is_active=True))


async def _seed_tree_root(db):
    if (await db.execute(select(Distributor).where(Distributor.distributor_id=="ROOT"))).scalar_one_or_none(): return
    root_ba = Distributor(distributor_id="ROOT", full_name="Ignite Root", email="root@ignite.in", phone="9999999999", status=DistributorStatus.ACTIVE)
    db.add(root_ba); await db.flush()
    root_pos = TreePosition(parent_id=None, depth=0, path="root")
    db.add(root_pos); await db.flush()
    root_center = TrackingCenter(distributor_id=root_ba.id, center_number=1, position_id=root_pos.id, is_active=True)
    db.add(root_center); await db.flush()
    db.add(CoinBalance(distributor_id=root_ba.id))
