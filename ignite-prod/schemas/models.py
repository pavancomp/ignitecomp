"""
Pydantic schemas — request / response models.
India-specific validation: PAN, IFSC, phone (Indian mobile numbers).
"""

import re
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# ── Validators ────────────────────────────────────────────────────────────

PAN_RE   = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
IFSC_RE  = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
PHONE_RE = re.compile(r"^[6-9]\d{9}$")     # Indian mobile: 6–9 prefix, 10 digits
GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


# ── Auth ──────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class RefreshRequest(BaseModel):
    refresh_token: str

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    model_config = {"from_attributes": True}


# ── Distributor ───────────────────────────────────────────────────────────

class DistributorCreate(BaseModel):
    distributor_id: str = Field(..., min_length=4, max_length=20)
    full_name: str = Field(..., min_length=2, max_length=200)
    email: str = Field(..., max_length=254)
    phone: str
    pan_number: Optional[str] = None
    gstin: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None
    sponsor_id: Optional[int] = None
    joined_date: Optional[date] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip().lstrip("+91").lstrip("0")
        if not PHONE_RE.match(v):
            raise ValueError("Phone must be a valid 10-digit Indian mobile number (6–9 prefix)")
        return v

    @field_validator("pan_number")
    @classmethod
    def validate_pan(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.upper().strip()
        if not PAN_RE.match(v):
            raise ValueError("PAN must be 10-character alphanumeric in format AAAAA9999A")
        return v

    @field_validator("ifsc_code")
    @classmethod
    def validate_ifsc(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.upper().strip()
        if not IFSC_RE.match(v):
            raise ValueError("IFSC must be 11 characters: 4 letters + 0 + 6 alphanumeric")
        return v

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.upper().strip()
        if not GSTIN_RE.match(v):
            raise ValueError("GSTIN format invalid")
        return v


class DistributorUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    pan_number: Optional[str] = None
    gstin: Optional[str] = None
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = None
    status: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lstrip("+91").lstrip("0")
        if not PHONE_RE.match(v):
            raise ValueError("Phone must be a valid 10-digit Indian mobile number")
        return v


class DistributorOut(BaseModel):
    id: int
    distributor_id: str
    full_name: str
    email: str
    phone: str
    pan_number: Optional[str]
    gstin: Optional[str]
    status: str
    sponsor_id: Optional[int]
    joined_date: Optional[date]
    created_at: Optional[datetime]
    model_config = {"from_attributes": True}


class TreePlacementRequest(BaseModel):
    distributor_id: int
    sponsor_position_id: int
    preferred_leg: Optional[str] = Field(None, pattern="^(left|right)$")


# ── Orders ────────────────────────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=1, le=100)

class OrderCreate(BaseModel):
    distributor_id: int
    cycle_id: Optional[int] = None
    order_type: str = "ba_purchase"
    items: list[OrderItemCreate] = Field(..., min_length=1)
    order_date: Optional[date] = None
    ecom_order_id: Optional[str] = None

class OrderOut(BaseModel):
    id: int
    order_ref: str
    distributor_id: int
    cycle_id: Optional[int]
    order_type: str
    status: str
    amount_inr: int
    cv_total: int
    order_date: date
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Cycles ────────────────────────────────────────────────────────────────

class CycleCreate(BaseModel):
    cycle_code: str = Field(..., min_length=3, max_length=20)
    cycle_type: str = Field("weekly", pattern="^(weekly|monthly)$")
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self

class CycleOut(BaseModel):
    id: int
    cycle_code: str
    cycle_type: str
    start_date: date
    end_date: date
    status: str
    total_payout_inr: int
    total_tds_inr: int
    distributor_count: int
    closed_at: Optional[datetime]
    approved_at: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Commission ledger ─────────────────────────────────────────────────────

class CommissionOut(BaseModel):
    id: int
    distributor_id: int
    cycle_id: int
    rank_at_cycle: Optional[str]
    steps_earned: int
    step_commission_inr: int
    green_coin_income_inr: int
    matching_bonus_inr: int
    maintenance_bonus_inr: int
    gross_commission_inr: int
    tds_deducted_inr: int
    net_payable_inr: int
    left_cv_carry_out: int
    right_cv_carry_out: int
    yellow_coins_earned: int
    green_coins_converted: int
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Compliance ────────────────────────────────────────────────────────────

class TdsReportRow(BaseModel):
    distributor_id: int
    distributor_name: str
    pan_number: Optional[str]
    financial_year: str
    gross_income_inr: int
    tds_deducted_inr: int
    net_income_inr: int

class WalletBalanceOut(BaseModel):
    distributor_id: int
    green_coins: int
    green_coins_lifetime: int
    yellow_coins: int
    blue_coins: int
    fy_gross_inr: int
    fy_tds_inr: int
    gst_required: bool


# ── Config ────────────────────────────────────────────────────────────────

class PlanConfigOut(BaseModel):
    cv_per_step: int
    flush_ratio: float
    tds_rate: float
    tds_threshold_inr: int
    gst_threshold_inr: int
    inr_rounding: int
    coin_lifetime_cap: int
    yellow_coin_step_interval: int
    first_step_half_rate: bool
    cycle_type: str
    model_config = {"from_attributes": True}

class PlanConfigUpdate(BaseModel):
    cv_per_step: Optional[int] = None
    flush_ratio: Optional[float] = None
    tds_threshold_inr: Optional[int] = None
    inr_rounding: Optional[int] = None
    coin_lifetime_cap: Optional[int] = None
    yellow_coin_step_interval: Optional[int] = None
    first_step_half_rate: Optional[bool] = None
    cycle_type: Optional[str] = None

class RankConfigOut(BaseModel):
    id: int
    rank_name: str
    min_cumulative_steps: int
    step_rate_inr: int
    max_weekly_steps: Optional[int]
    matching_bonus_levels: int
    maintenance_bonus_inr: int
    maintenance_hold_months: int
    sort_order: int
    model_config = {"from_attributes": True}

class RankConfigUpdate(BaseModel):
    step_rate_inr: Optional[int] = None
    max_weekly_steps: Optional[int] = None
    matching_bonus_levels: Optional[int] = None
    maintenance_bonus_inr: Optional[int] = None
    maintenance_hold_months: Optional[int] = None
    is_active: Optional[bool] = None


# ── Pagination ────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


# ── Tracking center ────────────────────────────────────────────────────────

class TrackingCenterOut(BaseModel):
    center_id: int
    center_number: int
    position_id: Optional[int]
    depth: Optional[int]
    is_active: bool
    activated_at: Optional[datetime]

class ActivateCentersRequest(BaseModel):
    sponsor_position_id: int
    center_count: int = Field(1, ge=1, le=3)
    preferred_leg: Optional[str] = Field(None, pattern="^(left|right)$")

class TreeNodeOut(BaseModel):
    position_id: int
    parent_id: Optional[int]
    leg: Optional[str]
    depth: int
    distributor_id: Optional[int]
    distributor_name: Optional[str]
    center_id: Optional[int]
    center_number: Optional[int]
    left_cv: Optional[int] = None
    right_cv: Optional[int] = None
