"""
Binary tree engine — v2 with tracking center support.
"""
from collections import deque
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from db.models import TrackingCenter, TreePosition, Order, OrderStatus, OrderType


async def place_center(db, distributor_id, center_number, sponsor_position_id, preferred_leg=None):
    pos = await _bfs_place(db, sponsor_position_id, preferred_leg)
    c = TrackingCenter(distributor_id=distributor_id, center_number=center_number, position_id=pos.id, is_active=True)
    db.add(c); await db.flush(); return c


async def place_triple_header(db, distributor_id, sponsor_position_id, preferred_leg=None):
    c1_pos = await _bfs_place(db, sponsor_position_id, preferred_leg)
    c1 = TrackingCenter(distributor_id=distributor_id, center_number=1, position_id=c1_pos.id, is_active=True)
    db.add(c1); await db.flush()

    c2_pos = TreePosition(parent_id=c1_pos.id, leg="left", depth=c1_pos.depth+1, path=f"{c1_pos.path or c1_pos.id}.{c1_pos.id}")
    db.add(c2_pos); await db.flush()
    c2 = TrackingCenter(distributor_id=distributor_id, center_number=2, position_id=c2_pos.id, is_active=True)
    db.add(c2)

    c3_pos = TreePosition(parent_id=c1_pos.id, leg="right", depth=c1_pos.depth+1, path=f"{c1_pos.path or c1_pos.id}.{c1_pos.id}")
    db.add(c3_pos); await db.flush()
    c3 = TrackingCenter(distributor_id=distributor_id, center_number=3, position_id=c3_pos.id, is_active=True)
    db.add(c3); await db.flush()
    return [c1, c2, c3]


async def _bfs_place(db, start_position_id, preferred_leg=None):
    if preferred_leg in ("left", "right"):
        taken = (await db.execute(select(TreePosition).where(TreePosition.parent_id==start_position_id, TreePosition.leg==preferred_leg))).scalar_one_or_none()
        if not taken:
            parent = await db.get(TreePosition, start_position_id)
            pos = TreePosition(parent_id=start_position_id, leg=preferred_leg, depth=(parent.depth+1) if parent else 1, path=f"{parent.path}.{start_position_id}" if parent and parent.path else str(start_position_id))
            db.add(pos); await db.flush(); return pos

    queue = deque([start_position_id]); visited = set()
    while queue:
        cur = queue.popleft()
        if cur in visited: continue
        visited.add(cur)
        children = (await db.execute(select(TreePosition).where(TreePosition.parent_id==cur))).scalars().all()
        taken_legs = {c.leg for c in children}
        for leg in ("left","right"):
            if leg not in taken_legs:
                parent = await db.get(TreePosition, cur)
                pos = TreePosition(parent_id=cur, leg=leg, depth=(parent.depth+1) if parent else 1, path=f"{parent.path}.{cur}" if parent and parent.path else str(cur))
                db.add(pos); await db.flush(); return pos
        for child in children: queue.append(child.id)
    raise RuntimeError(f"No open slot from {start_position_id}")


async def get_leg_cv(db, position_id, cycle_id):
    children = (await db.execute(select(TreePosition).where(TreePosition.parent_id==position_id))).scalars().all()
    left_pos  = next((c for c in children if c.leg=="left"),  None)
    right_pos = next((c for c in children if c.leg=="right"), None)
    left_cv  = await _subtree_cv(db, left_pos.id,  cycle_id) if left_pos  else 0
    right_cv = await _subtree_cv(db, right_pos.id, cycle_id) if right_pos else 0
    return left_cv, right_cv


async def _subtree_cv(db, root_pos_id, cycle_id):
    center_ids = await _subtree_center_ids(db, root_pos_id)
    if not center_ids: return 0
    dist_ids = [r[0] for r in (await db.execute(select(TrackingCenter.distributor_id).where(TrackingCenter.id.in_(center_ids)))).all()]
    if not dist_ids: return 0
    result = await db.execute(select(func.sum(Order.cv_total)).where(Order.distributor_id.in_(dist_ids), Order.cycle_id==cycle_id, Order.status==OrderStatus.VERIFIED, Order.order_type==OrderType.BA_PURCHASE))
    return result.scalar_one_or_none() or 0


async def _subtree_center_ids(db, root_pos_id):
    ids = []; queue = deque([root_pos_id])
    while queue:
        pos_id = queue.popleft()
        c = (await db.execute(select(TrackingCenter).where(TrackingCenter.position_id==pos_id))).scalar_one_or_none()
        if c: ids.append(c.id)
        for cid in (await db.execute(select(TreePosition.id).where(TreePosition.parent_id==pos_id))).scalars().all():
            queue.append(cid)
    return ids


async def calculate_matching_bonus(db, position_id, cycle_id, rank_name, rank_table, commission_map):
    rank_row = next((r for r in rank_table if r.name==rank_name), None)
    if not rank_row or rank_row.matching_bonus_levels==0: return 0
    levels = rank_row.matching_bonus_levels
    level_rates = [0.10] + [0.01]*(levels-1)
    total = 0; cur_pos = position_id
    for idx in range(levels):
        children = (await db.execute(select(TreePosition).where(TreePosition.parent_id==cur_pos))).scalars().all()
        if not children: break
        strong = max(children, key=lambda ch: 0, default=None)
        max_cv = -1
        for ch in children:
            cv = await _subtree_cv(db, ch.id, cycle_id)
            if cv > max_cv: max_cv, strong = cv, ch
        if not strong: break
        c = (await db.execute(select(TrackingCenter).where(TrackingCenter.position_id==strong.id))).scalar_one_or_none()
        if c: total += int(commission_map.get(c.id, 0) * level_rates[idx])
        cur_pos = strong.id
    return total
