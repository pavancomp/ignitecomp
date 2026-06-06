from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.connection import get_db
from db.models import PlanConfig, RankConfig, AdminUser
from api.deps import require_admin, require_viewer, write_audit
from schemas.models import PlanConfigOut, PlanConfigUpdate, RankConfigOut, RankConfigUpdate

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/plan", response_model=PlanConfigOut)
async def get_plan_config(db: AsyncSession = Depends(get_db), _: AdminUser = Depends(require_viewer)):
    cfg = await db.get(PlanConfig, 1)
    if not cfg:
        raise HTTPException(status_code=404, detail="Plan config not found — run seed first")
    return cfg


@router.patch("/plan", response_model=PlanConfigOut)
async def update_plan_config(
    body: PlanConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_admin),
):
    cfg = await db.get(PlanConfig, 1)
    if not cfg:
        raise HTTPException(status_code=404, detail="Plan config not found")
    old = {k: getattr(cfg, k) for k in body.model_dump(exclude_none=True)}
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(cfg, field, value)
    await write_audit(db, current_user.id, "update_plan_config", "PlanConfig", 1,
                      old_value=old, new_value=body.model_dump(exclude_none=True), request=request)
    return cfg


@router.get("/ranks", response_model=list[RankConfigOut])
async def list_rank_config(db: AsyncSession = Depends(get_db), _: AdminUser = Depends(require_viewer)):
    rows = (await db.execute(
        select(RankConfig).where(RankConfig.is_active == True).order_by(RankConfig.sort_order)
    )).scalars().all()
    return rows


@router.patch("/ranks/{rank_id}", response_model=RankConfigOut)
async def update_rank_config(
    rank_id: int,
    body: RankConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_admin),
):
    rank = await db.get(RankConfig, rank_id)
    if not rank:
        raise HTTPException(status_code=404, detail="Rank not found")
    old = {k: getattr(rank, k) for k in body.model_dump(exclude_none=True)}
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(rank, field, value)
    await write_audit(db, current_user.id, "update_rank_config", "RankConfig", rank_id,
                      old_value=old, new_value=body.model_dump(exclude_none=True), request=request)
    return rank


@router.get("/products")
async def list_products(db: AsyncSession = Depends(get_db), _: AdminUser = Depends(require_viewer)):
    from db.models import Product
    rows = (await db.execute(select(Product).where(Product.is_active == True))).scalars().all()
    return [{"id": p.id, "sku": p.sku, "name": p.name,
             "ba_price_inr": p.ba_price_inr, "cv": p.cv,
             "coins_awarded": p.coins_awarded} for p in rows]
