from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.connection import get_db
from db.models import (
    TaxTracking, TdsStatement, CoinBalance,
    Distributor, AdminUser
)
from api.deps import require_finance, require_viewer
from schemas.models import TdsReportRow, WalletBalanceOut
from config import get_settings

settings = get_settings()
router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/tds-report", response_model=dict)
async def tds_report(
    financial_year: str = Query(..., description="e.g. 2025-26"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_finance),
):
    q = (
        select(TaxTracking, Distributor)
        .join(Distributor, Distributor.id == TaxTracking.distributor_id)
        .where(TaxTracking.financial_year == financial_year)
        .where(TaxTracking.tds_deducted_inr > 0)
    )
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).all()

    items = [
        TdsReportRow(
            distributor_id=row.Distributor.id,
            distributor_name=row.Distributor.full_name,
            pan_number=row.Distributor.pan_number,
            financial_year=row.TaxTracking.financial_year,
            gross_income_inr=row.TaxTracking.gross_income_inr,
            tds_deducted_inr=row.TaxTracking.tds_deducted_inr,
            net_income_inr=row.TaxTracking.gross_income_inr - row.TaxTracking.tds_deducted_inr,
        )
        for row in rows
    ]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/gst-flags", response_model=dict)
async def gst_flags(
    financial_year: str = Query(..., description="e.g. 2025-26"),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_finance),
):
    """Return distributors whose FY income crossed the GST registration threshold."""
    threshold = settings.GST_REGISTRATION_THRESHOLD_INR
    rows = (await db.execute(
        select(TaxTracking, Distributor)
        .join(Distributor, Distributor.id == TaxTracking.distributor_id)
        .where(TaxTracking.financial_year == financial_year)
        .where(TaxTracking.gross_income_inr >= threshold)
    )).all()

    return {
        "threshold_inr": threshold,
        "financial_year": financial_year,
        "count": len(rows),
        "distributors": [
            {
                "distributor_id": r.Distributor.distributor_id,
                "name": r.Distributor.full_name,
                "gross_income_inr": r.TaxTracking.gross_income_inr,
                "gstin": r.Distributor.gstin,
                "gstin_registered": bool(r.Distributor.gstin),
            }
            for r in rows
        ],
    }


@router.get("/wallet/{distributor_id}", response_model=WalletBalanceOut)
async def wallet(
    distributor_id: int,
    financial_year: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_viewer),
):
    ba = await db.get(Distributor, distributor_id)
    if not ba:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Distributor not found")

    coins = (await db.execute(
        select(CoinBalance).where(CoinBalance.distributor_id == distributor_id)
    )).scalar_one_or_none()

    from datetime import datetime, timezone
    def _fy(dt):
        y = dt.year
        return f"{y}-{str(y+1)[2:]}" if dt.month >= 4 else f"{y-1}-{str(y)[2:]}"

    fy = financial_year or _fy(datetime.now(tz=timezone.utc))

    tax = (await db.execute(
        select(TaxTracking).where(
            TaxTracking.distributor_id == distributor_id,
            TaxTracking.financial_year == fy,
        )
    )).scalar_one_or_none()

    gst_required = (tax.gross_income_inr >= settings.GST_REGISTRATION_THRESHOLD_INR) if tax else False

    return WalletBalanceOut(
        distributor_id=distributor_id,
        green_coins=coins.green_coins if coins else 0,
        green_coins_lifetime=coins.green_coins_lifetime if coins else 0,
        yellow_coins=coins.yellow_coins if coins else 0,
        blue_coins=coins.blue_coins if coins else 0,
        fy_gross_inr=tax.gross_income_inr if tax else 0,
        fy_tds_inr=tax.tds_deducted_inr if tax else 0,
        gst_required=gst_required,
    )
