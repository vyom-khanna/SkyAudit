from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import School, Verification, Anomaly, Notice, SatelliteCapture, District
from app.schemas import (
    SchoolOut, SchoolProfile, VerificationOut, AnomalyOut,
    NoticeOut, SatelliteCaptureOut, ModuleResult, CommunityFlag
)
from app.services.anomaly_engine import run_all_modules
from app.routers.auth import get_current_officer

router = APIRouter(prefix="/schools", tags=["schools"])


@router.get("/{udise_code}", response_model=SchoolProfile)
def get_school_profile(udise_code: str, db: Session = Depends(get_db)):
    """Full school profile with all 7 module scores, anomalies, and notice history."""
    school = db.query(School).filter(School.udise_code == udise_code).first()
    if not school:
        raise HTTPException(status_code=404, detail=f"School {udise_code} not found")

    verifications = (
        db.query(Verification)
        .filter(Verification.udise_code == udise_code)
        .order_by(Verification.module_id)
        .all()
    )

    anomalies = (
        db.query(Anomaly)
        .filter(Anomaly.udise_code == udise_code)
        .order_by(Anomaly.detected_at.desc())
        .all()
    )

    anomaly_ids = [a.id for a in anomalies]
    notices = (
        db.query(Notice)
        .filter(Notice.anomaly_id.in_(anomaly_ids))
        .order_by(Notice.sent_at.desc())
        .all()
        if anomaly_ids
        else []
    )

    latest_capture = (
        db.query(SatelliteCapture)
        .filter(SatelliteCapture.udise_code == udise_code)
        .order_by(SatelliteCapture.capture_date.desc())
        .first()
    )

    module_results = [
        ModuleResult(
            module_id=v.module_id,
            module_name=v.module_name,
            status=v.status,
            confidence=v.confidence_score,
            reported_value=v.reported_value or "",
            verified_value=v.verified_value or "",
            discrepancy_amount_inr=v.discrepancy_amount_inr,
            evidence_url=v.evidence_url,
            satellite_image_url=v.satellite_image_url,
            summary=v.verified_value or "",
        )
        for v in verifications
    ]

    # Compute accountability score from verifications
    status_penalty = {"ghost": 1.0, "anomaly": 0.70, "pending": 0.30, "verified": 0.0}
    weights = {1: 0.25, 2: 0.20, 3: 0.15, 4: 0.15, 5: 0.10, 6: 0.10, 7: 0.05}
    total_penalty = sum(
        weights.get(v.module_id, 0) * status_penalty.get(v.status.value if v.status else "pending", 0.3)
        for v in verifications
    )
    accountability_score = round((1.0 - total_penalty) * 100, 2)

    is_ghost = any(
        v.status and v.status.value == "ghost" and v.module_id == 1
        for v in verifications
    )

    return SchoolProfile(
        school=SchoolOut.model_validate(school),
        accountability_score=accountability_score,
        module_results=module_results,
        anomalies=[AnomalyOut.model_validate(a) for a in anomalies],
        notices=[NoticeOut.model_validate(n) for n in notices],
        latest_satellite=SatelliteCaptureOut.model_validate(latest_capture) if latest_capture else None,
        is_ghost=is_ghost,
    )


@router.get("/{udise_code}/satellite", response_model=dict)
def get_school_satellite(udise_code: str, db: Session = Depends(get_db)):
    """Latest satellite capture + before/after if construction grant exists."""
    school = db.query(School).filter(School.udise_code == udise_code).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    captures = (
        db.query(SatelliteCapture)
        .filter(SatelliteCapture.udise_code == udise_code)
        .order_by(SatelliteCapture.capture_date.desc())
        .limit(5)
        .all()
    )

    # Find construction anomaly for before/after
    construction_anomaly = (
        db.query(Anomaly)
        .filter(
            Anomaly.udise_code == udise_code,
            Anomaly.anomaly_type == "construction_fraud",
        )
        .first()
    )

    return {
        "udise_code": udise_code,
        "captures": [SatelliteCaptureOut.model_validate(c) for c in captures],
        "before_url": construction_anomaly.satellite_before_url if construction_anomaly else None,
        "after_url": construction_anomaly.satellite_after_url if construction_anomaly else None,
        "has_construction_grant": construction_anomaly is not None,
    }


@router.get("/{udise_code}/verification", response_model=List[VerificationOut])
def get_school_verifications(udise_code: str, db: Session = Depends(get_db)):
    """All 7 module verification results for this school."""
    school = db.query(School).filter(School.udise_code == udise_code).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    verifications = (
        db.query(Verification)
        .filter(Verification.udise_code == udise_code)
        .order_by(Verification.module_id)
        .all()
    )
    return [VerificationOut.model_validate(v) for v in verifications]


@router.post("/{udise_code}/flag", status_code=status.HTTP_201_CREATED)
def flag_school(udise_code: str, flag: CommunityFlag, db: Session = Depends(get_db)):
    """Community flagging — creates a pending verification task."""
    school = db.query(School).filter(School.udise_code == udise_code).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    if flag.reporter_type not in ("parent", "teacher", "journalist", "ngo", "citizen"):
        raise HTTPException(
            status_code=422,
            detail="reporter_type must be one of: parent, teacher, journalist, ngo, citizen",
        )

    if len(flag.details) < 10:
        raise HTTPException(status_code=422, detail="Please provide at least 10 characters of details")

    # Create a pending anomaly record with community source
    from app.models import Anomaly, AnomalyType, AnomalySeverity, AnomalyStatus
    anomaly = Anomaly(
        udise_code=udise_code,
        anomaly_type=AnomalyType.ghost_school,  # placeholder — will be determined on verification
        severity=AnomalySeverity.medium,
        confidence=0.3,  # low confidence until satellite-verified
        description=(
            f"Community flag by {flag.reporter_type}: {flag.reason}. "
            f"Details: {flag.details[:500]}"
        ),
        funds_at_risk_inr=0.0,
        detected_at=datetime.utcnow(),
        status=AnomalyStatus.new,
        evidence_json={
            "source": "community_flag",
            "reporter_type": flag.reporter_type,
            "reason": flag.reason,
            "contact": flag.contact or "",
        },
    )
    db.add(anomaly)
    db.commit()
    db.refresh(anomaly)

    return {
        "message": "Flag submitted successfully. Satellite verification will be triggered within 5 days.",
        "anomaly_id": anomaly.id,
        "udise_code": udise_code,
    }


@router.post("/{udise_code}/verify", status_code=status.HTTP_202_ACCEPTED)
def trigger_verification(
    udise_code: str,
    db: Session = Depends(get_db),
    officer=Depends(get_current_officer),
):
    """Manually trigger full verification for a school (admin/testing use)."""
    school = db.query(School).filter(School.udise_code == udise_code).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    try:
        result = run_all_modules(udise_code, db)
        return {"message": "Verification complete", "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(exc)}")
