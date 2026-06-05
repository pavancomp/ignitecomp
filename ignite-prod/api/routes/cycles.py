from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.connection import get_db, AsyncSessionLocal
from db.models import Cycle, CycleStatus, CommissionLedger, AdminUser
from api.deps import require_admin, require_finance, require_viewer, write_audit
from schemas.models import CycleCreate, CycleOut, CommissionOut
from engine.cycle_runner import run_cycle_close

router = APIRouter(prefix="/cycles", tags=["cycles"])


@router.post("/", response_model=CycleOut, status_code=201)
async def create_cycle(
    body: CycleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_admin),
):
    existing = (await db.execute(
        select(Cycle).where(Cycle.cycle_code == body.cycle_code)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Cycle code already exists")

    cycle = Cycle(
        cycle_code=body.cycle_code,
        cycle_type=body.cycle_type,
        start_date=body.start_date,
        end_date=body.end_date,
        status=CycleStatus.OPEN,
    )
    db.add(cycle)
    await db.flush()
    await write_audit(db, current_user.id, "create_cycle", "Cycle", cycle.id,
                      new_value={"cycle_code": cycle.cycle_code}, request=request)
    return cycle


@router.get("/", response_model=dict)
async def list_cycles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_viewer),
):
    q = select(Cycle).order_by(Cycle.start_date.desc())
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [CycleOut.model_validate(c) for c in items]}


@router.get("/{cycle_id}", response_model=CycleOut)
async def get_cycle(cycle_id: int, db: AsyncSession = Depends(get_db), _: AdminUser = Depends(require_viewer)):
    c = await db.get(Cycle, cycle_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return c


@router.post("/{cycle_id}/close", status_code=202)
async def close_cycle(
    cycle_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_admin),
):
    cycle = await db.get(Cycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    if cycle.status != CycleStatus.OPEN:
        raise HTTPException(status_code=400, detail=f"Cycle is {cycle.status} — must be OPEN to close")

    await write_audit(db, current_user.id, "cycle_close_initiated", "Cycle", cycle_id, request=request)

    background_tasks.add_task(
        run_cycle_close,
        cycle_id=cycle_id,
        actor_id=current_user.id,
        session_factory=AsyncSessionLocal,
    )
    return {"message": "Cycle close initiated. Poll GET /cycles/{cycle_id} for status.", "cycle_id": cycle_id}


@router.post("/{cycle_id}/approve", response_model=CycleOut)
async def approve_cycle(
    cycle_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_finance),
):
    cycle = await db.get(Cycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    if cycle.status != CycleStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Cycle must be CLOSED before approval")

    cycle.status = CycleStatus.APPROVED
    cycle.approved_at = datetime.now(tz=timezone.utc)
    cycle.approved_by = current_user.id
    await write_audit(db, current_user.id, "cycle_approved", "Cycle", cycle_id, request=request)
    return cycle


@router.get("/{cycle_id}/commissions", response_model=dict)
async def cycle_commissions(
    cycle_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_viewer),
):
    q = select(CommissionLedger).where(CommissionLedger.cycle_id == cycle_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [CommissionOut.model_validate(c) for c in items]}
