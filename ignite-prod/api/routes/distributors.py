"""Distributor CRUD + tracking center activation."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.connection import get_db
from db.models import Distributor, TrackingCenter, TreePosition, CoinBalance, DistributorStatus, AdminUser, PlanConfig
from api.deps import require_admin, require_finance, require_viewer, write_audit
from schemas.models import DistributorCreate, DistributorUpdate, DistributorOut
from engine.tree import place_center, place_triple_header

router = APIRouter(prefix="/distributors", tags=["distributors"])


@router.get("/", response_model=dict)
async def list_distributors(
    page: int=Query(1,ge=1), page_size: int=Query(50,ge=1,le=200),
    status: Optional[str]=None, search: Optional[str]=None,
    db: AsyncSession=Depends(get_db), _: AdminUser=Depends(require_viewer),
):
    q = select(Distributor).where(Distributor.distributor_id!="ROOT")
    if status: q = q.where(Distributor.status==status)
    if search: q = q.where(Distributor.full_name.ilike(f"%{search}%") | Distributor.email.ilike(f"%{search}%"))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(q.offset((page-1)*page_size).limit(page_size))).scalars().all()
    return {"total": total, "page": page, "page_size": page_size, "items": [DistributorOut.model_validate(d) for d in items]}


@router.post("/", response_model=DistributorOut, status_code=201)
async def create_distributor(
    body: DistributorCreate, request: Request,
    db: AsyncSession=Depends(get_db), current_user: AdminUser=Depends(require_admin),
):
    if (await db.execute(select(Distributor).where((Distributor.distributor_id==body.distributor_id)|(Distributor.email==body.email)))).scalar_one_or_none():
        raise HTTPException(409, "Distributor ID or email exists")
    ba = Distributor(**body.model_dump(), status=DistributorStatus.PENDING_KYC, joined_date=body.joined_date or date.today())
    db.add(ba); await db.flush()
    db.add(CoinBalance(distributor_id=ba.id))
    await write_audit(db, current_user.id, "create_distributor", "Distributor", ba.id, new_value={"id": ba.distributor_id}, request=request)
    return ba


@router.get("/{distributor_id}", response_model=DistributorOut)
async def get_distributor(distributor_id: int, db: AsyncSession=Depends(get_db), _: AdminUser=Depends(require_viewer)):
    ba = await db.get(Distributor, distributor_id)
    if not ba: raise HTTPException(404, "Not found")
    return ba


@router.patch("/{distributor_id}", response_model=DistributorOut)
async def update_distributor(
    distributor_id: int, body: DistributorUpdate, request: Request,
    db: AsyncSession=Depends(get_db), current_user: AdminUser=Depends(require_admin),
):
    ba = await db.get(Distributor, distributor_id)
    if not ba: raise HTTPException(404, "Not found")
    old = {k: str(getattr(ba, k)) for k in body.model_dump(exclude_none=True)}
    for f, v in body.model_dump(exclude_none=True).items(): setattr(ba, f, v)
    await write_audit(db, current_user.id, "update_distributor", "Distributor", ba.id, old_value=old, new_value=body.model_dump(exclude_none=True), request=request)
    return ba


@router.get("/{distributor_id}/centers")
async def get_centers(distributor_id: int, db: AsyncSession=Depends(get_db), _: AdminUser=Depends(require_viewer)):
    ba = await db.get(Distributor, distributor_id)
    if not ba: raise HTTPException(404, "Not found")
    centers = (await db.execute(select(TrackingCenter).where(TrackingCenter.distributor_id==distributor_id).order_by(TrackingCenter.center_number))).scalars().all()
    result = []
    for c in centers:
        pos = await db.get(TreePosition, c.position_id) if c.position_id else None
        result.append({"center_id": c.id, "center_number": c.center_number, "position_id": c.position_id, "depth": pos.depth if pos else None, "is_active": c.is_active, "activated_at": c.activated_at})
    return {"distributor_id": distributor_id, "center_count": len(centers), "centers": result}


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
    """
    Activate 1, 2, or 3 tracking centers for a BA.
    - center_count=1: single center, normal BFS placement
    - center_count=3: full triple-header (C2+C3 auto-placed under C1)
    Note: center_count=2 creates C1 + C2 (left child) only.
    """
    ba = await db.get(Distributor, distributor_id)
    if not ba: raise HTTPException(404, "Distributor not found")

    # Check existing centers
    existing = (await db.execute(select(func.count()).select_from(TrackingCenter).where(TrackingCenter.distributor_id==distributor_id))).scalar_one()
    if existing > 0: raise HTTPException(409, "Distributor already has tracking centers")

    plan = await db.get(PlanConfig, 1)
    max_centers = plan.max_centers_per_ba if plan else 3
    if center_count > max_centers: raise HTTPException(400, f"Plan allows max {max_centers} centers")

    if center_count == 3:
        centers = await place_triple_header(db, distributor_id, sponsor_position_id, preferred_leg)
    elif center_count == 2:
        c1 = await place_center(db, distributor_id, 1, sponsor_position_id, preferred_leg)
        c2_pos = TreePosition(parent_id=c1.position_id, leg="left", depth=0)
        db.add(c2_pos); await db.flush()
        c2 = TrackingCenter(distributor_id=distributor_id, center_number=2, position_id=c2_pos.id, is_active=True)
        db.add(c2); await db.flush()
        centers = [c1, c2]
    else:
        c1 = await place_center(db, distributor_id, 1, sponsor_position_id, preferred_leg)
        centers = [c1]

    # Activate BA
    if ba.status == DistributorStatus.PENDING_KYC: ba.status = DistributorStatus.ACTIVE

    await write_audit(db, current_user.id, "activate_centers", "TrackingCenter", distributor_id, new_value={"center_count": len(centers), "center_ids": [c.id for c in centers]}, request=request)
    return {"success": True, "center_count": len(centers), "centers": [{"center_id": c.id, "center_number": c.center_number, "position_id": c.position_id} for c in centers]}


@router.get("/tree/nodes")
async def get_tree_nodes(
    cycle_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_viewer),
):
    """Return the full tree for visualization. Includes CV data if cycle_id provided."""
    positions = (await db.execute(select(TreePosition))).scalars().all()
    centers = (await db.execute(select(TrackingCenter))).scalars().all()
    bas = (await db.execute(select(Distributor))).scalars().all()

    center_by_pos = {c.position_id: c for c in centers}
    ba_by_id = {b.id: b for b in bas}

    result = []
    for pos in positions:
        c = center_by_pos.get(pos.id)
        ba = ba_by_id.get(c.distributor_id) if c else None
        node = {
            "position_id": pos.id, "parent_id": pos.parent_id,
            "leg": pos.leg.value if pos.leg else None, "depth": pos.depth,
            "distributor_id": ba.id if ba else None,
            "distributor_name": ba.full_name if ba else None,
            "distributor_ref": ba.distributor_id if ba else None,
            "center_id": c.id if c else None,
            "center_number": c.center_number if c else None,
            "is_active": c.is_active if c else False,
        }
        result.append(node)
    return result
