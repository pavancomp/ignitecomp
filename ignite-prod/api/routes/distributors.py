from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.connection import get_db
from db.models import (
    Distributor, TrackingCenter, TreePosition, CoinBalance,
    DistributorStatus, AdminUser, PlanConfig,
    Order, OrderItem, OrderStatus, OrderType, Product, Cycle, CycleStatus,
)
from api.deps import require_admin, require_finance, require_viewer, write_audit
from schemas.models import DistributorCreate, DistributorUpdate, DistributorOut
from engine.tree import place_center, place_triple_header

router = APIRouter(prefix="/distributors", tags=["distributors"])


# ── Tree nodes (MUST be before /{distributor_id} to avoid route shadowing) ──

@router.get("/tree/nodes")
async def get_tree_nodes(db: AsyncSession = Depends(get_db),
                         _: AdminUser = Depends(require_viewer)):
    positions = (await db.execute(select(TreePosition))).scalars().all()
    centers   = (await db.execute(select(TrackingCenter))).scalars().all()
    bas       = (await db.execute(select(Distributor))).scalars().all()
    center_by_pos = {c.position_id: c for c in centers}
    ba_by_id  = {b.id: b for b in bas}
    result = []
    for pos in positions:
        c  = center_by_pos.get(pos.id)
        ba = ba_by_id.get(c.distributor_id) if c else None
        result.append({
            "position_id": pos.id, "parent_id": pos.parent_id,
            "leg": pos.leg.value if pos.leg else None, "depth": pos.depth,
            "distributor_id": ba.id if ba else None,
            "distributor_name": ba.full_name if ba else None,
            "distributor_ref": ba.distributor_id if ba else None,
            "center_id": c.id if c else None,
            "center_number": c.center_number if c else None,
            "is_active": c.is_active if c else False,
        })
    return result


# ── CRUD ──────────────────────────────────────────────────────────────────

@router.get("/", response_model=dict)
async def list_distributors(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = None, search: Optional[str] = None,
    db: AsyncSession = Depends(get_db), _: AdminUser = Depends(require_viewer),
):
    q = select(Distributor).where(Distributor.distributor_id != "ROOT")
    if status: q = q.where(Distributor.status == status)
    if search:
        q = q.where(Distributor.full_name.ilike(f"%{search}%") | Distributor.email.ilike(f"%{search}%"))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [DistributorOut.model_validate(d) for d in items]}


@router.post("/", response_model=DistributorOut, status_code=201)
async def create_distributor(body: DistributorCreate, request: Request,
                              db: AsyncSession = Depends(get_db),
                              current_user: AdminUser = Depends(require_admin)):
    if (await db.execute(
        select(Distributor).where((Distributor.distributor_id == body.distributor_id) | (Distributor.email == body.email))
    )).scalar_one_or_none():
        raise HTTPException(409, "Distributor ID or email already exists")

    # Exclude joined_date from model_dump to avoid duplicate kwarg
    ba_data = body.model_dump(exclude={"joined_date"})
    ba = Distributor(**ba_data, status=DistributorStatus.PENDING_KYC,
                     joined_date=body.joined_date or date.today())
    db.add(ba); await db.flush()
    db.add(CoinBalance(distributor_id=ba.id))
    await write_audit(db, current_user.id, "create_distributor", "Distributor", ba.id,
                      new_value={"distributor_id": ba.distributor_id}, request=request)
    return ba


@router.get("/{distributor_id}", response_model=DistributorOut)
async def get_distributor(distributor_id: int, db: AsyncSession = Depends(get_db),
                           _: AdminUser = Depends(require_viewer)):
    ba = await db.get(Distributor, distributor_id)
    if not ba: raise HTTPException(404, "Not found")
    return ba


@router.patch("/{distributor_id}", response_model=DistributorOut)
async def update_distributor(distributor_id: int, body: DistributorUpdate, request: Request,
                              db: AsyncSession = Depends(get_db),
                              current_user: AdminUser = Depends(require_admin)):
    ba = await db.get(Distributor, distributor_id)
    if not ba: raise HTTPException(404, "Not found")
    old = {k: str(getattr(ba, k)) for k in body.model_dump(exclude_none=True)}
    for f, v in body.model_dump(exclude_none=True).items(): setattr(ba, f, v)
    await write_audit(db, current_user.id, "update_distributor", "Distributor", ba.id,
                      old_value=old, new_value=body.model_dump(exclude_none=True), request=request)
    return ba


# ── Tracking centers ──────────────────────────────────────────────────────

@router.get("/{distributor_id}/centers")
async def get_centers(distributor_id: int, db: AsyncSession = Depends(get_db),
                      _: AdminUser = Depends(require_viewer)):
    ba = await db.get(Distributor, distributor_id)
    if not ba: raise HTTPException(404, "Not found")
    centers = (await db.execute(
        select(TrackingCenter).where(TrackingCenter.distributor_id == distributor_id)
        .order_by(TrackingCenter.center_number)
    )).scalars().all()
    result = []
    for c in centers:
        pos = await db.get(TreePosition, c.position_id) if c.position_id else None
        result.append({"center_id": c.id, "center_number": c.center_number,
                        "position_id": c.position_id, "depth": pos.depth if pos else None,
                        "is_active": c.is_active, "activated_at": c.activated_at})
    return {"distributor_id": distributor_id, "center_count": len(result), "centers": result}


@router.post("/{distributor_id}/centers")
async def activate_centers(
    distributor_id: int,
    sponsor_position_id: int,
    center_count: int = Query(1, ge=1, le=3),
    preferred_leg: Optional[str] = Query(None, pattern="^(left|right)$"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_admin),
):
    ba = await db.get(Distributor, distributor_id)
    if not ba: raise HTTPException(404, "Distributor not found")
    existing = (await db.execute(
        select(func.count()).select_from(TrackingCenter).where(TrackingCenter.distributor_id == distributor_id)
    )).scalar_one()
    if existing > 0: raise HTTPException(409, "Distributor already has tracking centers")
    plan = await db.get(PlanConfig, 1)
    if center_count > (plan.max_centers_per_ba if plan else 3):
        raise HTTPException(400, f"Plan allows max {plan.max_centers_per_ba} centers")

    if center_count == 3:
        centers = await place_triple_header(db, distributor_id, sponsor_position_id, preferred_leg)
    elif center_count == 2:
        c1 = await place_center(db, distributor_id, 1, sponsor_position_id, preferred_leg)
        c1_pos = await db.get(TreePosition, c1.position_id)
        c2_pos = TreePosition(parent_id=c1.position_id, leg="left",
                               depth=(c1_pos.depth + 1) if c1_pos else 1,  # FIX: correct depth
                               path=f"{c1_pos.path}.{c1_pos.id}" if c1_pos and c1_pos.path else str(c1.position_id))
        db.add(c2_pos); await db.flush()
        c2 = TrackingCenter(distributor_id=distributor_id, center_number=2, position_id=c2_pos.id, is_active=True)
        db.add(c2); await db.flush()
        centers = [c1, c2]
    else:
        c1 = await place_center(db, distributor_id, 1, sponsor_position_id, preferred_leg)
        centers = [c1]

    if ba.status == DistributorStatus.PENDING_KYC:
        ba.status = DistributorStatus.ACTIVE
    await write_audit(db, current_user.id, "activate_centers", "TrackingCenter", distributor_id,
                      new_value={"center_count": len(centers)}, request=request)
    return {"success": True, "center_count": len(centers),
            "centers": [{"center_id": c.id, "center_number": c.center_number, "position_id": c.position_id} for c in centers]}


# ── Orders per BA ─────────────────────────────────────────────────────────

@router.get("/{distributor_id}/orders")
async def get_ba_orders(distributor_id: int, db: AsyncSession = Depends(get_db),
                        _: AdminUser = Depends(require_viewer)):
    orders = (await db.execute(
        select(Order).where(Order.distributor_id == distributor_id)
        .order_by(Order.order_date.desc()).limit(100)
    )).scalars().all()
    return [{"id": o.id, "order_ref": o.order_ref, "order_type": o.order_type.value,
             "status": o.status.value, "amount_inr": o.amount_inr, "cv_total": o.cv_total,
             "order_date": str(o.order_date), "cycle_id": o.cycle_id, "center_id": o.center_id}
            for o in orders]


@router.post("/{distributor_id}/orders")
async def add_ba_order(
    distributor_id: int,
    product_id: int,
    quantity: int,
    cycle_id: int,
    center_id: Optional[int] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_finance),
):
    ba = await db.get(Distributor, distributor_id)
    if not ba: raise HTTPException(404, "BA not found")

    center_count = (await db.execute(
        select(func.count()).select_from(TrackingCenter)
        .where(TrackingCenter.distributor_id == distributor_id, TrackingCenter.is_active == True)
    )).scalar_one()
    if center_count > 1 and not center_id:
        raise HTTPException(400, f"This BA has {center_count} tracking centers — specify center_id to allocate BV.")
    if center_id:
        center = await db.get(TrackingCenter, center_id)
        if not center or center.distributor_id != distributor_id:
            raise HTTPException(400, "center_id does not belong to this BA")

    prod = await db.get(Product, product_id)
    if not prod: raise HTTPException(404, "Product not found")
    cycle = await db.get(Cycle, cycle_id)
    if not cycle or cycle.status != CycleStatus.OPEN:
        raise HTTPException(400, "Cycle not found or not open")

    order = Order(
        order_ref=f"ORD-{uuid.uuid4().hex[:10].upper()}",
        distributor_id=distributor_id, center_id=center_id, cycle_id=cycle_id,
        order_type=OrderType.BA_PURCHASE, status=OrderStatus.PENDING,
        amount_inr=prod.ba_price_inr * quantity, cv_total=prod.cv * quantity,
        order_date=cycle.start_date,
    )
    db.add(order); await db.flush()
    db.add(OrderItem(order_id=order.id, product_id=product_id, quantity=quantity,
                     unit_price_inr=prod.ba_price_inr, cv_per_unit=prod.cv))
    await write_audit(db, current_user.id, "add_order", "Order", order.id, request=request)
    return {"order_id": order.id, "order_ref": order.order_ref,
            "amount_inr": order.amount_inr, "cv_total": order.cv_total,
            "allocated_to_center": center_id}
