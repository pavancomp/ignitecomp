from datetime import date
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.connection import get_db
from db.models import (
    Order, OrderItem, OrderStatus, OrderType,
    Distributor, DistributorStatus, Product, CoinBalance, AdminUser, Cycle
)
from api.deps import require_admin, write_audit
from integrations.fetcher import fetch_ecom_orders, fetch_new_distributors

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/ecom-orders")
async def sync_ecom_orders(
    cycle_id: int = Query(...),
    since: date = Query(default=None),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_admin),
):
    cycle = await db.get(Cycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    since_date = since or cycle.start_date
    raw_orders = await fetch_ecom_orders(since_date)

    created = 0
    skipped = 0

    for raw in raw_orders:
        ecom_id = raw["ecom_order_id"]
        existing = (await db.execute(
            select(Order).where(Order.ecom_order_id == ecom_id)
        )).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        ba = (await db.execute(
            select(Distributor).where(Distributor.distributor_id == raw["distributor_ref"])
        )).scalar_one_or_none()
        if not ba:
            skipped += 1
            continue

        total_amount = 0
        total_cv = 0
        items_data = []

        for item in raw.get("items", []):
            prod = (await db.execute(
                select(Product).where(Product.sku == item["sku"])
            )).scalar_one_or_none()
            if not prod:
                continue
            line_amount = prod.ba_price_inr * item["quantity"]
            line_cv = prod.cv * item["quantity"]
            total_amount += line_amount
            total_cv += line_cv
            items_data.append((prod, item["quantity"]))

        order = Order(
            order_ref=f"ORD-{uuid.uuid4().hex[:10].upper()}",
            distributor_id=ba.id,
            cycle_id=cycle_id,
            order_type=OrderType.BA_PURCHASE,
            status=OrderStatus.PENDING,
            amount_inr=total_amount or raw.get("amount_inr", 0),
            cv_total=total_cv,
            order_date=date.fromisoformat(raw["order_date"]) if isinstance(raw["order_date"], str) else raw["order_date"],
            ecom_order_id=ecom_id,
        )
        db.add(order)
        await db.flush()

        for prod, qty in items_data:
            db.add(OrderItem(
                order_id=order.id,
                product_id=prod.id,
                quantity=qty,
                unit_price_inr=prod.ba_price_inr,
                cv_per_unit=prod.cv,
            ))

        created += 1

    await write_audit(db, current_user.id, "sync_ecom_orders",
                      new_value={"created": created, "skipped": skipped}, request=request)
    return {"created": created, "skipped": skipped}


@router.post("/crm-distributors")
async def sync_crm_distributors(
    since: date = Query(default=None),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_admin),
):
    since_date = since or date.today()
    raw_bas = await fetch_new_distributors(since_date)

    created = 0
    skipped = 0

    for raw in raw_bas:
        existing = (await db.execute(
            select(Distributor).where(
                (Distributor.distributor_id == raw["distributor_id"]) |
                (Distributor.email == raw["email"])
            )
        )).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        ba = Distributor(
            distributor_id=raw["distributor_id"],
            full_name=raw["full_name"],
            email=raw["email"],
            phone=raw.get("phone", "0000000000"),
            pan_number=raw.get("pan_number"),
            joined_date=date.fromisoformat(raw["joined_date"]) if raw.get("joined_date") else date.today(),
            status=DistributorStatus.PENDING_KYC,
            crm_id=raw.get("crm_id"),
        )
        db.add(ba)
        await db.flush()
        db.add(CoinBalance(distributor_id=ba.id))
        created += 1

    await write_audit(db, current_user.id, "sync_crm_distributors",
                      new_value={"created": created, "skipped": skipped}, request=request)
    return {"created": created, "skipped": skipped}
