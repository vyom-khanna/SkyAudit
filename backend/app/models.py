import enum
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    Date, ForeignKey, Enum, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from app.database import Base


class ManagementType(str, enum.Enum):
    government = "government"
    private = "private"
    aided = "aided"


class VerificationStatus(str, enum.Enum):
    verified = "verified"
    anomaly = "anomaly"
    ghost = "ghost"
    pending = "pending"


class AnomalyType(str, enum.Enum):
    ghost_school = "ghost_school"
    construction_fraud = "construction_fraud"
    enrollment_inflation = "enrollment_inflation"
    meal_fraud = "meal_fraud"
    outcome_manipulation = "outcome_manipulation"
    teacher_absence = "teacher_absence"
    budget_misuse = "budget_misuse"


class AnomalySeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AnomalyStatus(str, enum.Enum):
    new = "new"
    noticed = "noticed"
    acknowledged = "acknowledged"
    resolved = "resolved"
    disputed = "disputed"


class School(Base):
    __tablename__ = "schools"

    udise_code = Column(String(20), primary_key=True)
    name = Column(String(255), nullable=False)
    district_code = Column(String(20), ForeignKey("districts.district_code"), nullable=False)
    block = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    reported_enrollment = Column(Integer, default=0)
    reported_teachers = Column(Integer, default=0)
    reported_building_exists = Column(Boolean, default=False)
    reported_kitchen_exists = Column(Boolean, default=False)
    reported_meals_daily = Column(Integer, default=0)
    management_type = Column(Enum(ManagementType), default=ManagementType.government)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_verified_at = Column(DateTime, nullable=True)
    geom = Column(Geometry("POINT", srid=4326), nullable=True)

    district = relationship("District", back_populates="schools")
    verifications = relationship("Verification", back_populates="school")
    anomalies = relationship("Anomaly", back_populates="school")
    satellite_captures = relationship("SatelliteCapture", back_populates="school")

    __table_args__ = (
        Index("idx_schools_district", "district_code"),
    )


class District(Base):
    __tablename__ = "districts"

    district_code = Column(String(20), primary_key=True)
    district_name = Column(String(100), nullable=False)
    state_code = Column(String(10), nullable=False)
    state_name = Column(String(100), nullable=False)
    total_schools = Column(Integer, default=0)
    verified_schools = Column(Integer, default=0)
    flagged_schools = Column(Integer, default=0)
    accountability_score = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    schools = relationship("School", back_populates="district")

    __table_args__ = (Index("idx_districts_state", "state_code"),)


class Verification(Base):
    __tablename__ = "verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    udise_code = Column(String(20), ForeignKey("schools.udise_code"), nullable=False)
    module_id = Column(Integer, nullable=False)
    module_name = Column(String(100), nullable=False)
    status = Column(Enum(VerificationStatus), default=VerificationStatus.pending)
    confidence_score = Column(Float, default=0.0)
    reported_value = Column(String(500))
    verified_value = Column(String(500))
    discrepancy_amount_inr = Column(Float, nullable=True)
    satellite_image_url = Column(String(1000), nullable=True)
    evidence_url = Column(String(1000), nullable=True)
    verified_at = Column(DateTime, default=datetime.utcnow)
    data_source = Column(String(200))

    school = relationship("School", back_populates="verifications")

    __table_args__ = (
        Index("idx_verifications_udise", "udise_code"),
        Index("idx_verifications_module", "module_id"),
    )


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    udise_code = Column(String(20), ForeignKey("schools.udise_code"), nullable=False)
    anomaly_type = Column(Enum(AnomalyType), nullable=False)
    severity = Column(Enum(AnomalySeverity), default=AnomalySeverity.medium)
    confidence = Column(Float, default=0.0)
    description = Column(Text)
    funds_at_risk_inr = Column(Float, default=0.0)
    detected_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(AnomalyStatus), default=AnomalyStatus.new)
    notice_sent_at = Column(DateTime, nullable=True)
    response_due_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    satellite_before_url = Column(String(1000), nullable=True)
    satellite_after_url = Column(String(1000), nullable=True)
    evidence_json = Column(JSONB, default={})

    school = relationship("School", back_populates="anomalies")
    notices = relationship("Notice", back_populates="anomaly")
    pulse_events = relationship("PulseEvent", back_populates="anomaly")

    __table_args__ = (
        Index("idx_anomalies_udise", "udise_code"),
        Index("idx_anomalies_type", "anomaly_type"),
        Index("idx_anomalies_status", "status"),
        Index("idx_anomalies_detected", "detected_at"),
    )


class Notice(Base):
    __tablename__ = "notices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    anomaly_id = Column(Integer, ForeignKey("anomalies.id"), nullable=False)
    sent_to = Column(String(50))
    sent_at = Column(DateTime, default=datetime.utcnow)
    response_deadline = Column(DateTime)
    response_received = Column(Boolean, default=False)
    response_text = Column(Text, nullable=True)
    cc_list = Column(JSONB, default=[])
    escalation_level = Column(Integer, default=1)

    anomaly = relationship("Anomaly", back_populates="notices")

    __table_args__ = (Index("idx_notices_anomaly", "anomaly_id"),)


class SatelliteCapture(Base):
    __tablename__ = "satellite_captures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    udise_code = Column(String(20), ForeignKey("schools.udise_code"), nullable=False)
    capture_date = Column(Date, nullable=False)
    image_url = Column(String(1000))
    ndbi_score = Column(Float, default=0.0)
    building_detected = Column(Boolean, default=False)
    building_confidence = Column(Float, default=0.0)
    building_footprint_sqm = Column(Float, nullable=True)
    source = Column(String(50), default="sentinel2")

    school = relationship("School", back_populates="satellite_captures")

    __table_args__ = (
        Index("idx_satellite_udise", "udise_code"),
        Index("idx_satellite_date", "capture_date"),
    )


class PulseEvent(Base):
    __tablename__ = "pulse_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    anomaly_id = Column(Integer, ForeignKey("anomalies.id"), nullable=False)
    event_type = Column(String(100))
    headline = Column(String(300))
    summary = Column(Text)
    funds_mentioned_inr = Column(Float, default=0.0)
    school_name = Column(String(255))
    district_name = Column(String(100))
    state_name = Column(String(100))
    satellite_url = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_published = Column(Boolean, default=True)

    anomaly = relationship("Anomaly", back_populates="pulse_events")

    __table_args__ = (Index("idx_pulse_created", "created_at"),)


class Officer(Base):
    __tablename__ = "officers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    role = Column(String(50))
    district_code = Column(String(20), ForeignKey("districts.district_code"), nullable=True)
    state_code = Column(String(10), nullable=True)
    last_login = Column(DateTime, nullable=True)
    hashed_password = Column(String(500), nullable=False)

    __table_args__ = (Index("idx_officers_email", "email"),)
