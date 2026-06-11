from datetime import datetime, date
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, EmailStr, validator
from app.models import (
    ManagementType, VerificationStatus, AnomalyType,
    AnomalySeverity, AnomalyStatus
)


# ── School schemas ──────────────────────────────────────────────────────────

class SchoolBase(BaseModel):
    name: str
    district_code: str
    block: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reported_enrollment: int = 0
    reported_teachers: int = 0
    reported_building_exists: bool = False
    reported_kitchen_exists: bool = False
    reported_meals_daily: int = 0
    management_type: ManagementType = ManagementType.government


class SchoolCreate(SchoolBase):
    udise_code: str


class SchoolOut(SchoolBase):
    udise_code: str
    created_at: datetime
    last_verified_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SchoolPin(BaseModel):
    udise_code: str
    name: str
    latitude: float
    longitude: float
    accountability_score: Optional[float] = None
    status: Optional[str] = "pending"
    has_anomaly: bool = False
    severity: Optional[str] = None

    class Config:
        from_attributes = True


# ── District schemas ────────────────────────────────────────────────────────

class DistrictBase(BaseModel):
    district_name: str
    state_code: str
    state_name: str


class DistrictOut(DistrictBase):
    district_code: str
    total_schools: int
    verified_schools: int
    flagged_schools: int
    accountability_score: float
    last_updated: datetime

    class Config:
        from_attributes = True


class DistrictRanking(BaseModel):
    rank: int
    district_code: str
    district_name: str
    state_name: str
    accountability_score: float
    ghost_count: int
    funds_at_risk: float
    unresolved_notices: int
    trend: str  # "improving" | "declining" | "stable"


# ── Verification schemas ────────────────────────────────────────────────────

class ModuleResult(BaseModel):
    module_id: int
    module_name: str
    status: VerificationStatus
    confidence: float
    reported_value: str
    verified_value: str
    discrepancy_amount_inr: Optional[float] = None
    evidence_url: Optional[str] = None
    satellite_image_url: Optional[str] = None
    summary: str


class VerificationOut(BaseModel):
    id: int
    udise_code: str
    module_id: int
    module_name: str
    status: VerificationStatus
    confidence_score: float
    reported_value: str
    verified_value: str
    discrepancy_amount_inr: Optional[float] = None
    satellite_image_url: Optional[str] = None
    evidence_url: Optional[str] = None
    verified_at: datetime
    data_source: str

    class Config:
        from_attributes = True


# ── Anomaly schemas ─────────────────────────────────────────────────────────

class AnomalyOut(BaseModel):
    id: int
    udise_code: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    confidence: float
    description: str
    funds_at_risk_inr: float
    detected_at: datetime
    status: AnomalyStatus
    notice_sent_at: Optional[datetime] = None
    response_due_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    satellite_before_url: Optional[str] = None
    satellite_after_url: Optional[str] = None
    evidence_json: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class AnomalyStatusUpdate(BaseModel):
    status: AnomalyStatus
    response_text: Optional[str] = None
    evidence_url: Optional[str] = None


class AnomalyFilter(BaseModel):
    state: Optional[str] = None
    anomaly_type: Optional[str] = None
    status: Optional[str] = None
    min_funds: Optional[float] = None
    district_code: Optional[str] = None
    severity: Optional[str] = None


# ── Notice schemas ──────────────────────────────────────────────────────────

class NoticeOut(BaseModel):
    id: int
    anomaly_id: int
    sent_to: str
    sent_at: datetime
    response_deadline: datetime
    response_received: bool
    response_text: Optional[str] = None
    cc_list: List[str]
    escalation_level: int

    class Config:
        from_attributes = True


# ── Satellite schemas ───────────────────────────────────────────────────────

class SatelliteCaptureOut(BaseModel):
    id: int
    udise_code: str
    capture_date: date
    image_url: str
    ndbi_score: float
    building_detected: bool
    building_confidence: float
    building_footprint_sqm: Optional[float] = None
    source: str

    class Config:
        from_attributes = True


# ── Pulse schemas ───────────────────────────────────────────────────────────

class PulseEventOut(BaseModel):
    id: int
    anomaly_id: int
    event_type: str
    headline: str
    summary: str
    funds_mentioned_inr: float
    school_name: str
    district_name: str
    state_name: str
    satellite_url: Optional[str] = None
    created_at: datetime
    is_published: bool

    class Config:
        from_attributes = True


# ── Officer schemas ─────────────────────────────────────────────────────────

class OfficerLogin(BaseModel):
    email: EmailStr
    password: str


class OfficerOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    district_code: Optional[str] = None
    state_code: Optional[str] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


# ── Community flag schemas ──────────────────────────────────────────────────

class CommunityFlag(BaseModel):
    reason: str
    reporter_type: str  # parent/teacher/journalist/ngo/citizen
    details: str
    contact: Optional[str] = None


# ── Full school profile response ────────────────────────────────────────────

class SchoolProfile(BaseModel):
    school: SchoolOut
    accountability_score: float
    module_results: List[ModuleResult]
    anomalies: List[AnomalyOut]
    notices: List[NoticeOut]
    latest_satellite: Optional[SatelliteCaptureOut] = None
    is_ghost: bool = False


# ── National summary ────────────────────────────────────────────────────────

class NationalSummary(BaseModel):
    total_schools_verified: int
    total_flagged: int
    total_ghost_schools: int
    total_funds_at_risk_inr: float
    most_flagged_district: str
    most_improved_district: str
    last_updated: datetime


# ── WhatsApp ────────────────────────────────────────────────────────────────

class WhatsAppInbound(BaseModel):
    From: str
    Body: str
    MessageSid: Optional[str] = None
    NumMedia: Optional[str] = "0"
