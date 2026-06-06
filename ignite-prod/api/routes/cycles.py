from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.connection import get_db, AsyncSessionLocal
from db.models import Cycle, CycleStatus, CommissionLedger, TrackingCenter, AdminUser, SystemEvent
from api.deps import require_admin, require_finance, require_viewer, write_audit
from schemas.models import CycleCreate, CycleOut, CommissionOut
from engine.cycle_runner import run_cycle_close

router = APIRouter(prefix="/cycles", tags=["cycles"])


@router.post("/", response_model=CycleOut, status_code=201)
async def create_cycle(body: CycleCreate, request: Request,
                       db: AsyncSession = Depends(get_db),
                       current_user: AdminUser = Depends(require_admin)):
    if (await db.execute(
        select(Cycle).where(Cycle.cycle_code == body.cycle_code)
    )).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Cycle code already exists")
    cycle = Cycle(cycle_code=body.cycle_code, cycle_type=body.cycle_type,
                  start_date=body.start_date, end_date=body.end_date,
                  status=CycleStatus.OPEN)
    db.add(cycle); await db.flush()
    await write_audit(db, current_user.id, "create_cycle", "Cycle", cycle.id,
                      new_value={"cycle_code": cycle.cycle_code}, request=request)
    return cycle


@router.get("/", response_model=dict)
async def list_cycles(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                      db: AsyncSession = Depends(get_db), _: AdminUser = Depends(require_viewer)):
    q = select(Cycle).order_by(Cycle.start_date.desc())
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [CycleOut.model_validate(c) for c in items]}


@router.get("/{cycle_id}", response_model=CycleOut)
async def get_cycle(cycle_id: int, db: AsyncSession = Depends(get_db),
                    _: AdminUser = Depends(require_viewer)):
    c = await db.get(Cycle, cycle_id)
    if not c: raise HTTPException(status_code=404, detail="Cycle not found")
    return c


@router.post("/{cycle_id}/close", status_code=202)
async def close_cycle(
    cycle_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_admin),
):
    """
    Trigger commission engine for this cycle.
    Returns 202 immediately. Engine runs in background.
    Poll GET /cycles/{id} — status goes open → closed when done.
    If it fails, status resets to open so you can retry.
    """
    cycle = await db.get(Cycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    if cycle.status not in (CycleStatus.OPEN,):
        raise HTTPException(
            status_code=400,
            detail=f"Cycle is '{cycle.status}' — must be 'open' to close"
        )

    # Log intent — no status change here (avoids DB enum migration dependency)
    await write_audit(db, current_user.id, "cycle_close_initiated",
                      "Cycle", cycle_id, request=request)

    # Spawn background engine run
    background_tasks.add_task(
        run_cycle_close,
        cycle_id=cycle_id,
        actor_id=current_user.id,
        session_factory=AsyncSessionLocal,
    )

    return {
        "message": "Commission engine started. Poll GET /cycles/{} for status.".format(cycle_id),
        "cycle_id": cycle_id,
        "poll_url": f"/api/v1/cycles/{cycle_id}",
    }


@router.post("/{cycle_id}/approve", response_model=CycleOut)
async def approve_cycle(cycle_id: int, request: Request,
                        db: AsyncSession = Depends(get_db),
                        current_user: AdminUser = Depends(require_finance)):
    cycle = await db.get(Cycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    if cycle.status != CycleStatus.CLOSED:
        raise HTTPException(status_code=400,
                            detail=f"Cycle must be 'closed' before approval. Currently: {cycle.status}")
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
    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = []
    for r in rows:
        d = CommissionOut.model_validate(r).model_dump()
        if r.center_id:
            center = await db.get(TrackingCenter, r.center_id)
            d["center_number"] = center.center_number if center else None
        items.append(d)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{cycle_id}/events")
async def cycle_events(cycle_id: int, db: AsyncSession = Depends(get_db),
                       _: AdminUser = Depends(require_viewer)):
    """Returns system events for this cycle — useful for debugging failures."""
    import json
    rows = (await db.execute(
        select(SystemEvent)
        .where(SystemEvent.payload.contains(f'"cycle_id": {cycle_id}'))
        .order_by(SystemEvent.created_at.desc())
        .limit(20)
    )).scalars().all()
    return [{"event_type": e.event_type, "status": e.status,
             "payload": json.loads(e.payload) if e.payload else None,
             "created_at": e.created_at} for e in rows]
