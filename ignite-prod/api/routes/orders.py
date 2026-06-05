from datetime import date
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.connection import get_db
from db.models import (
    Order, OrderItem, OrderStatus, OrderType,
    Product, Distributor, Cycle, CycleStatus, AdminUser
)
from api.deps import require_admin, require_finance, require_viewer, write_audit
from schemas.models import OrderCreate, OrderOut

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderOut, status_code=201)
async def create_order(
    body: OrderCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_finance),
):
    ba = await db.get(Distributor, body.distributor_id)
    if not ba:
        raise HTTPException(status_code=404, detail="Distributor not found")

    total_amount = 0
    total_cv = 0
    items_out = []

    for item in body.items:
        prod = await db.get(Product, item.product_id)
        if not prod or not prod.is_active:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        line_amount = prod.ba_price_inr * item.quantity
        line_cv     = prod.cv * item.quantity
        total_amount += line_amount
        total_cv     += line_cv
        items_out.append((prod, item.quantity, line_amount, line_cv))

    order = Order(
        order_ref=f"ORD-{uuid.uuid4().hex[:10].upper()}",
        distributor_id=body.distributor_id,
        cycle_id=body.cycle_id,
        order_type=body.order_type or OrderType.BA_PURCHASE,
        status=OrderStatus.PENDING,
        amount_inr=total_amount,
        cv_total=total_cv,
        order_date=body.order_date or date.today(),
        ecom_order_id=body.ecom_order_id,
    )
    db.add(order)
    await db.flush()

    for prod, qty, unit_price, cv_unit in items_out:
        db.add(OrderItem(
            order_id=order.id,
            product_id=prod.id,
            quantity=qty,
            unit_price_inr=unit_price // qty,
            cv_per_unit=prod.cv,
        ))

    await write_audit(db, current_user.id, "create_order", "Order", order.id,
                      new_value={"order_ref": order.order_ref, "amount_inr": total_amount}, request=request)
    return order


@router.get("/", response_model=dict)
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    cycle_id: Optional[int] = None,
    distributor_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_viewer),
):
    q = select(Order)
    if cycle_id:
        q = q.where(Order.cycle_id == cycle_id)
    if distributor_id:
        q = q.where(Order.distributor_id == distributor_id)
    if status_filter:
        q = q.where(Order.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [OrderOut.model_validate(o) for o in items]}


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db), _: AdminUser = Depends(require_viewer)):
    o = await db.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    return o


@router.post("/{order_id}/verify", response_model=OrderOut)
async def verify_order(
    order_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_finance),
):
    from datetime import datetime, timezone
    o = await db.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if o.status != OrderStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Order is already {o.status}")
    o.status = OrderStatus.VERIFIED
    o.verified_at = datetime.now(tz=timezone.utc)
    await write_audit(db, current_user.id, "verify_order", "Order", o.id,
                      old_value={"status": "pending"}, new_value={"status": "verified"}, request=request)
    return o


@router.post("/bulk-verify")
async def bulk_verify_orders(
    order_ids: list[int],
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_finance),
):
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc)
    verified = []
    for oid in order_ids:
        o = await db.get(Order, oid)
        if o and o.status == OrderStatus.PENDING:
            o.status = OrderStatus.VERIFIED
            o.verified_at = now
            verified.append(oid)
    await write_audit(db, current_user.id, "bulk_verify_orders",
                      new_value={"order_ids": verified}, request=request)
    return {"verified_count": len(verified), "order_ids": verified}
