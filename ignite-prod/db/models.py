"""
Ignite DB Models — India market, all amounts in INR (₹).
v2: adds TrackingCenter; CommissionLedger + CarryForward keyed per center.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional
import enum

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Enum, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint, Index, func
)
from sqlalchemy.orm import relationship
from db.connection import Base


class CycleStatus(str, enum.Enum):
    OPEN = "open"; PROCESSING = "processing"; CLOSED = "closed"; APPROVED = "approved"; CANCELLED = "cancelled"

class DistributorStatus(str, enum.Enum):
    ACTIVE = "active"; INACTIVE = "inactive"; TERMINATED = "terminated"; PENDING_KYC = "pending_kyc"

class OrderType(str, enum.Enum):
    BA_PURCHASE = "ba_purchase"; RETAIL = "retail"; AUTOSHIP = "autoship"

class OrderStatus(str, enum.Enum):
    PENDING = "pending"; VERIFIED = "verified"; REJECTED = "rejected"

class LegSide(str, enum.Enum):
    LEFT = "left"; RIGHT = "right"

class UserRole(str, enum.Enum):
    ADMIN = "admin"; FINANCE = "finance"; VIEWER = "viewer"


# ── Config ─────────────────────────────────────────────────────────────────

class PlanConfig(Base):
    __tablename__ = "plan_config"
    id = Column(Integer, primary_key=True, default=1)
    cv_per_step = Column(Integer, nullable=False, default=1800)
    flush_ratio = Column(Numeric(5,2), nullable=False, default=Decimal("3.0"))
    tds_rate = Column(Numeric(5,4), nullable=False, default=Decimal("0.0500"))
    tds_threshold_inr = Column(BigInteger, nullable=False, default=15000)
    gst_threshold_inr = Column(BigInteger, nullable=False, default=2000000)
    inr_rounding = Column(Integer, nullable=False, default=500)
    coin_lifetime_cap = Column(Integer, nullable=False, default=12)
    yellow_coin_step_interval = Column(Integer, nullable=False, default=6)
    first_step_half_rate = Column(Boolean, nullable=False, default=True)
    cycle_type = Column(String(10), nullable=False, default="weekly")
    max_centers_per_ba = Column(Integer, nullable=False, default=3)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class RankConfig(Base):
    __tablename__ = "rank_config"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rank_name = Column(String(50), nullable=False, unique=True)
    min_cumulative_steps = Column(Integer, nullable=False, default=0)
    min_direct_cv = Column(Integer, nullable=False, default=0)
    min_retail_cv_annual = Column(Integer, nullable=False, default=0)
    min_consecutive_months = Column(Integer, nullable=False, default=0)
    step_rate_inr = Column(BigInteger, nullable=False)
    max_weekly_steps = Column(Integer, nullable=True)
    matching_bonus_levels = Column(Integer, nullable=False, default=0)
    maintenance_bonus_inr = Column(BigInteger, nullable=False, default=0)
    maintenance_hold_months = Column(Integer, nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    ba_price_inr = Column(BigInteger, nullable=False)
    retail_price_inr = Column(BigInteger, nullable=False)
    cv = Column(Integer, nullable=False)
    coins_awarded = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)


# ── Distributor / tree ─────────────────────────────────────────────────────

class Distributor(Base):
    __tablename__ = "distributors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    distributor_id = Column(String(20), nullable=False, unique=True)
    full_name = Column(String(200), nullable=False)
    email = Column(String(254), nullable=False, unique=True)
    phone = Column(String(15), nullable=False)
    pan_number = Column(String(10), nullable=True)
    gstin = Column(String(15), nullable=True)
    bank_account = Column(String(18), nullable=True)
    ifsc_code = Column(String(11), nullable=True)
    status = Column(Enum(DistributorStatus), nullable=False, default=DistributorStatus.PENDING_KYC)
    sponsor_id = Column(Integer, ForeignKey("distributors.id"), nullable=True)
    joined_date = Column(Date, nullable=False, default=date.today)
    crm_id = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sponsor = relationship("Distributor", remote_side=[id], backref="downlines")
    centers = relationship("TrackingCenter", back_populates="distributor", order_by="TrackingCenter.center_number")
    ranks = relationship("DistributorRank", back_populates="distributor")
    coin_balance = relationship("CoinBalance", back_populates="distributor", uselist=False)


class TreePosition(Base):
    """One row per tracking center (each center is its own tree node)."""
    __tablename__ = "tree_positions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("tree_positions.id"), nullable=True)
    leg = Column(Enum(LegSide), nullable=True)
    depth = Column(Integer, nullable=False, default=0)
    path = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parent = relationship("TreePosition", remote_side=[id], backref="children")
    center = relationship("TrackingCenter", back_populates="position", uselist=False)

    __table_args__ = (
        UniqueConstraint("parent_id", "leg", name="uq_tree_parent_leg"),
    )


# ── Tracking Center (NEW) ──────────────────────────────────────────────────

class TrackingCenter(Base):
    """
    Each BA owns 1–3 tracking centers. Each is an independent earning unit
    in the binary tree with its own legs, carry-forward, and commissions.

    center_number: 1 = primary, 2 = left child of C1, 3 = right child of C1
    """
    __tablename__ = "tracking_centers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=False)
    center_number = Column(Integer, nullable=False)          # 1, 2, or 3
    position_id = Column(Integer, ForeignKey("tree_positions.id"), nullable=True, unique=True)
    is_active = Column(Boolean, nullable=False, default=True)
    activated_at = Column(DateTime(timezone=True), server_default=func.now())

    distributor = relationship("Distributor", back_populates="centers")
    position = relationship("TreePosition", back_populates="center")
    commissions = relationship("CommissionLedger", back_populates="center")
    carry_forwards = relationship("DistributorCarryForward", back_populates="center")

    __table_args__ = (
        UniqueConstraint("distributor_id", "center_number", name="uq_center_dist_num"),
        Index("ix_center_distributor", "distributor_id"),
    )


# ── Cycle & orders ─────────────────────────────────────────────────────────

class Cycle(Base):
    __tablename__ = "cycles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_code = Column(String(20), nullable=False, unique=True)
    cycle_type = Column(String(10), nullable=False, default="weekly")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(Enum(CycleStatus), nullable=False, default=CycleStatus.OPEN)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    total_payout_inr = Column(BigInteger, nullable=False, default=0)
    total_tds_inr = Column(BigInteger, nullable=False, default=0)
    distributor_count = Column(Integer, nullable=False, default=0)
    center_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    orders = relationship("Order", back_populates="cycle")
    commissions = relationship("CommissionLedger", back_populates="cycle")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_ref = Column(String(50), nullable=False, unique=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=False)
    center_id = Column(Integer, ForeignKey("tracking_centers.id"), nullable=True)
    cycle_id = Column(Integer, ForeignKey("cycles.id"), nullable=True)
    order_type = Column(Enum(OrderType), nullable=False, default=OrderType.BA_PURCHASE)
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    amount_inr = Column(BigInteger, nullable=False)
    cv_total = Column(Integer, nullable=False, default=0)
    ecom_order_id = Column(String(100), nullable=True)
    order_date = Column(Date, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    distributor = relationship("Distributor")
    cycle = relationship("Cycle", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price_inr = Column(BigInteger, nullable=False)
    cv_per_unit = Column(Integer, nullable=False)
    order = relationship("Order", back_populates="items")
    product = relationship("Product")


# ── Commission ledger (keyed per center) ───────────────────────────────────

class CommissionLedger(Base):
    """
    One row per tracking center per cycle.
    Payout to BA = SUM(net_payable_inr) across all their active centers.
    """
    __tablename__ = "commission_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    center_id = Column(Integer, ForeignKey("tracking_centers.id"), nullable=False)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=False)  # denorm for easy query
    cycle_id = Column(Integer, ForeignKey("cycles.id"), nullable=False)
    rank_at_cycle = Column(String(50), nullable=True)
    steps_earned = Column(Integer, nullable=False, default=0)
    lifetime_steps_after = Column(Integer, nullable=False, default=0)

    step_commission_inr = Column(BigInteger, nullable=False, default=0)
    green_coin_income_inr = Column(BigInteger, nullable=False, default=0)
    matching_bonus_inr = Column(BigInteger, nullable=False, default=0)
    maintenance_bonus_inr = Column(BigInteger, nullable=False, default=0)
    gross_commission_inr = Column(BigInteger, nullable=False, default=0)
    tds_deducted_inr = Column(BigInteger, nullable=False, default=0)
    net_payable_inr = Column(BigInteger, nullable=False, default=0)

    left_cv_carry_out = Column(Integer, nullable=False, default=0)
    right_cv_carry_out = Column(Integer, nullable=False, default=0)
    yellow_coins_earned = Column(Integer, nullable=False, default=0)
    green_coins_converted = Column(Integer, nullable=False, default=0)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    center = relationship("TrackingCenter", back_populates="commissions")
    distributor = relationship("Distributor")
    cycle = relationship("Cycle", back_populates="commissions")

    __table_args__ = (
        UniqueConstraint("center_id", "cycle_id", name="uq_ledger_center_cycle"),
        Index("ix_ledger_distributor_cycle", "distributor_id", "cycle_id"),
    )


class DistributorCarryForward(Base):
    """Carry-forward per center per cycle."""
    __tablename__ = "distributor_carry_forward"

    id = Column(Integer, primary_key=True, autoincrement=True)
    center_id = Column(Integer, ForeignKey("tracking_centers.id"), nullable=False)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=False)  # denorm
    cycle_id = Column(Integer, ForeignKey("cycles.id"), nullable=False)
    left_cv_carry = Column(Integer, nullable=False, default=0)
    right_cv_carry = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    center = relationship("TrackingCenter", back_populates="carry_forwards")

    __table_args__ = (
        UniqueConstraint("center_id", "cycle_id", name="uq_carry_center_cycle"),
    )


class DistributorRank(Base):
    __tablename__ = "distributor_ranks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=False)
    rank_name = Column(String(50), nullable=False)
    achieved_at = Column(Date, nullable=False)
    cycle_id = Column(Integer, ForeignKey("cycles.id"), nullable=True)
    cumulative_steps = Column(Integer, nullable=False, default=0)
    distributor = relationship("Distributor", back_populates="ranks")
    __table_args__ = (Index("ix_dist_rank_distributor", "distributor_id"),)


# ── Coins ──────────────────────────────────────────────────────────────────

class CoinBalance(Base):
    __tablename__ = "coin_balances"
    id = Column(Integer, primary_key=True, autoincrement=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=False, unique=True)
    green_coins = Column(Integer, nullable=False, default=0)
    green_coins_lifetime = Column(Integer, nullable=False, default=0)
    yellow_coins = Column(Integer, nullable=False, default=0)
    blue_coins = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    distributor = relationship("Distributor", back_populates="coin_balance")


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=False)
    center_id = Column(Integer, ForeignKey("tracking_centers.id"), nullable=True)
    cycle_id = Column(Integer, ForeignKey("cycles.id"), nullable=False)
    coin_type = Column(String(10), nullable=False)
    delta = Column(Integer, nullable=False)
    reason = Column(String(100), nullable=True)
    inr_value = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Tax & compliance ────────────────────────────────────────────────────────

class TaxTracking(Base):
    __tablename__ = "tax_tracking"
    id = Column(Integer, primary_key=True, autoincrement=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=False)
    financial_year = Column(String(9), nullable=False)
    gross_income_inr = Column(BigInteger, nullable=False, default=0)
    tds_deducted_inr = Column(BigInteger, nullable=False, default=0)
    gst_required = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (UniqueConstraint("distributor_id", "financial_year", name="uq_tax_dist_fy"),)


class TdsStatement(Base):
    __tablename__ = "tds_statements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    distributor_id = Column(Integer, ForeignKey("distributors.id"), nullable=False)
    financial_year = Column(String(9), nullable=False)
    pan_number = Column(String(10), nullable=True)
    gross_income_inr = Column(BigInteger, nullable=False, default=0)
    tds_deducted_inr = Column(BigInteger, nullable=False, default=0)
    tds_rate = Column(Numeric(5,4), nullable=False, default=Decimal("0.0500"))
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("distributor_id", "financial_year", name="uq_tds_stmt_dist_fy"),)


# ── Audit & admin ──────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    actor_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("ix_audit_created", "created_at"),)


class SystemEvent(Base):
    __tablename__ = "system_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_type = Column(String(80), nullable=False)
    payload = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="info")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(254), nullable=False, unique=True)
    hashed_password = Column(String(200), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.VIEWER)
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
