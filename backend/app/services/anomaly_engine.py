"""
Anomaly Engine: orchestrates all 7 verification modules for a school or district.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    School, District, Verification, Anomaly, PulseEvent,
    VerificationStatus, AnomalyType, AnomalySeverity, AnomalyStatus,
)
from app.services import (
    ghost_detector,
    construction_tracker,
    enrollment_checker,
    meal_verifier,
    outcome_authenticator,
    teacher_presence,
    budget_efficiency,
)
from app.ml.building_detector import detect_building_at_coordinate, estimate_capacity
from app.services.notice_generator import generate_notice

logger = logging.getLogger(__name__)

# Module weights for unified AccountabilityScore
MODULE_WEIGHTS = {
    1: 0.25,  # Ghost
    2: 0.20,  # Construction
    3: 0.15,  # Enrollment
    4: 0.15,  # Meals
    5: 0.10,  # Outcomes
    6: 0.10,  # Teachers
    7: 0.05,  # Budget
}

STATUS_PENALTY = {
    "ghost": 1.0,
    "anomaly": 0.70,
    "pending": 0.30,
    "verified": 0.0,
}

SEVERITY_THRESHOLDS = {
    "critical": 0.80,
    "high": 0.60,
    "medium": 0.40,
    "low": 0.20,
}


def run_all_modules(udise_code: str, db: Session) -> Dict[str, Any]:
    """
    Run all 7 modules for a single school and persist results.

    Returns full school verification report.
    """
    school = db.query(School).filter(School.udise_code == udise_code).first()
    if not school:
        raise ValueError(f"School {udise_code} not found")

    district = db.query(District).filter(
        District.district_code == school.district_code
    ).first()

    school_row = _school_to_dict(school, district)

    # ── Module 1: Ghost Detection ──────────────────────────────────────────
    building_result = detect_building_at_coordinate(
        school.latitude or 0, school.longitude or 0
    )
    building_result["estimated_capacity"] = estimate_capacity(
        building_result.get("footprint_sqm", 0)
    )

    m1 = ghost_detector.run(school_row, mdm_data=None)

    # ── Module 2: Construction Tracking ───────────────────────────────────
    grants = _fetch_grants(udise_code, db)
    m2 = construction_tracker.run(school_row, grants)

    # ── Module 3: Enrollment Check ─────────────────────────────────────────
    district_ceiling_ratio = _get_district_ceiling_ratio(school.district_code, db)
    m3 = enrollment_checker.run(school_row, building_result, district_ceiling_ratio)

    # ── Module 4: Meal Verification ────────────────────────────────────────
    verified_enrollment = (
        building_result.get("estimated_capacity", school.reported_enrollment)
        if m3.get("status") == "anomaly"
        else school.reported_enrollment
    )
    mdm_data = _fetch_mdm(udise_code, db)
    m4 = meal_verifier.run(school_row, mdm_data, verified_enrollment)

    # ── Module 5: Outcome Authentication ──────────────────────────────────
    board_results = _fetch_board_results(udise_code, db)
    aser_data = _fetch_aser(school.district_code, db)
    m5 = outcome_authenticator.run(
        school_row, board_results, aser_data, district_std=0.12
    )

    # ── Module 6: Teacher Presence ─────────────────────────────────────────
    cag_findings = _fetch_cag(school.district_code, db)
    m6 = teacher_presence.run(
        school_row,
        module_results=[m1, m2, m3, m4, m5],
        cag_findings=cag_findings,
    )

    # ── Module 7: Budget Efficiency (district-level) ───────────────────────
    expenditure = _fetch_expenditure(school.district_code, db)
    verified_outcomes = {
        "pass_rate": float(board_results.get("reported_pass_rate", 0.6)) if board_results else 0.6,
        "aser_score": float(aser_data.get("pct_can_read_std2", 0.5)) if aser_data else 0.5,
        "nas_score": 0.55,
    }
    m7 = budget_efficiency.run(
        district_data={"district_code": school.district_code,
                       "district_name": district.district_name if district else "",
                       "verified_enrollment": verified_enrollment},
        verified_outcomes=verified_outcomes,
        expenditure_data=expenditure,
    )

    module_results = [m1, m2, m3, m4, m5, m6, m7]

    # ── Compute Accountability Score ──────────────────────────────────────
    accountability_score = _compute_accountability_score(module_results)

    # ── Persist verifications ─────────────────────────────────────────────
    _save_verifications(udise_code, module_results, db)

    # ── Create anomaly records ────────────────────────────────────────────
    anomalies_created = _create_anomalies(school, module_results, db)

    # ── Update school last_verified_at ─────────────────────────────────────
    school.last_verified_at = datetime.utcnow()
    db.commit()

    # ── Emit pulse events ─────────────────────────────────────────────────
    for anomaly in anomalies_created:
        _emit_pulse_event(anomaly, school, district, db)

    # ── Trigger notices for critical anomalies ────────────────────────────
    for anomaly in anomalies_created:
        if anomaly.severity == AnomalySeverity.critical:
            try:
                generate_notice(anomaly.id, db)
            except Exception as exc:
                logger.error(f"Notice generation failed for anomaly {anomaly.id}: {exc}")

    return {
        "udise_code": udise_code,
        "school_name": school.name,
        "district": school.district_code,
        "accountability_score": round(accountability_score, 2),
        "module_results": module_results,
        "anomalies_detected": len(anomalies_created),
        "is_ghost": m1.get("status") == "ghost",
        "verified_at": datetime.utcnow().isoformat(),
    }


def run_district(district_code: str, db: Session) -> Dict[str, Any]:
    """
    Run all modules for every school in a district; update district score.
    """
    schools = db.query(School).filter(School.district_code == district_code).all()
    if not schools:
        raise ValueError(f"No schools found for district {district_code}")

    results = []
    total_score = 0.0
    ghost_count = 0
    flagged_count = 0

    for school in schools:
        try:
            result = run_all_modules(school.udise_code, db)
            results.append(result)
            total_score += result["accountability_score"]
            if result["is_ghost"]:
                ghost_count += 1
            if result["anomalies_detected"] > 0:
                flagged_count += 1
        except Exception as exc:
            logger.error(f"Module run failed for {school.udise_code}: {exc}")

    district = db.query(District).filter(District.district_code == district_code).first()
    if district:
        district.accountability_score = total_score / max(len(results), 1)
        district.verified_schools = len(results)
        district.flagged_schools = flagged_count
        district.last_updated = datetime.utcnow()
        db.commit()

    return {
        "district_code": district_code,
        "schools_processed": len(results),
        "accountability_score": round(total_score / max(len(results), 1), 2),
        "ghost_schools": ghost_count,
        "flagged_schools": flagged_count,
        "processed_at": datetime.utcnow().isoformat(),
    }


def run_scheduled(db: Session) -> Dict[str, Any]:
    """
    Called by scheduler every 5 days (Sentinel-2 cadence).
    Re-runs schools whose satellite imagery may have refreshed.
    """
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=5)

    stale_schools = (
        db.query(School)
        .filter(
            (School.last_verified_at == None) | (School.last_verified_at < cutoff)
        )
        .limit(200)
        .all()
    )

    processed = 0
    new_anomalies = 0
    for school in stale_schools:
        try:
            result = run_all_modules(school.udise_code, db)
            new_anomalies += result["anomalies_detected"]
            processed += 1
        except Exception as exc:
            logger.error(f"Scheduled run failed for {school.udise_code}: {exc}")

    return {
        "processed": processed,
        "new_anomalies": new_anomalies,
        "run_at": datetime.utcnow().isoformat(),
    }


# ── Internal helpers ─────────────────────────────────────────────────────────

def _school_to_dict(school: School, district: Optional[District]) -> Dict[str, Any]:
    return {
        "udise_code": school.udise_code,
        "name": school.name,
        "latitude": school.latitude,
        "longitude": school.longitude,
        "reported_enrollment": school.reported_enrollment,
        "reported_teachers": school.reported_teachers,
        "reported_building_exists": school.reported_building_exists,
        "reported_kitchen_exists": school.reported_kitchen_exists,
        "reported_meals_daily": school.reported_meals_daily,
        "district_code": school.district_code,
        "district_name": district.district_name if district else "",
        "state_name": district.state_name if district else "",
        "infrastructure_score": 0.5,
        "per_child_spend": 8000.0,
        "district_poverty_index": 0.5,
        "historical_pass_rate_3yr": 0.6,
    }


def _compute_accountability_score(module_results: List[Dict]) -> float:
    """
    Aggregate module results into a single 0-100 score.
    Higher = better (fewer anomalies).
    """
    total_penalty = 0.0
    for result in module_results:
        mid = result.get("module_id", 0)
        status = result.get("status", "pending")
        weight = MODULE_WEIGHTS.get(mid, 0)
        penalty = STATUS_PENALTY.get(status, 0.30)
        total_penalty += weight * penalty

    return round((1.0 - total_penalty) * 100, 2)


def _classify_severity(module_results: List[Dict]) -> AnomalySeverity:
    ghost = any(r.get("status") == "ghost" for r in module_results)
    anomaly_count = sum(1 for r in module_results if r.get("status") == "anomaly")
    max_confidence = max((r.get("confidence", 0) for r in module_results), default=0)

    if ghost or (anomaly_count >= 3 and max_confidence > 0.8):
        return AnomalySeverity.critical
    if anomaly_count >= 2 or max_confidence > 0.75:
        return AnomalySeverity.high
    if anomaly_count == 1 and max_confidence > 0.5:
        return AnomalySeverity.medium
    return AnomalySeverity.low


def _module_to_anomaly_type(module_id: int) -> AnomalyType:
    mapping = {
        1: AnomalyType.ghost_school,
        2: AnomalyType.construction_fraud,
        3: AnomalyType.enrollment_inflation,
        4: AnomalyType.meal_fraud,
        5: AnomalyType.outcome_manipulation,
        6: AnomalyType.teacher_absence,
        7: AnomalyType.budget_misuse,
    }
    return mapping.get(module_id, AnomalyType.ghost_school)


def _save_verifications(
    udise_code: str, module_results: List[Dict], db: Session
) -> None:
    # Delete existing verifications for this school
    db.query(Verification).filter(Verification.udise_code == udise_code).delete()

    for result in module_results:
        v = Verification(
            udise_code=udise_code,
            module_id=result["module_id"],
            module_name=result["module_name"],
            status=VerificationStatus(result["status"]),
            confidence_score=float(result.get("confidence", 0)),
            reported_value=str(result.get("reported_value", "")),
            verified_value=str(result.get("verified_value", "")),
            discrepancy_amount_inr=result.get("discrepancy_amount_inr"),
            satellite_image_url=result.get("satellite_image_url"),
            evidence_url=result.get("evidence_url"),
            verified_at=datetime.utcnow(),
            data_source="schooltruth_engine_v1",
        )
        db.add(v)
    db.commit()


def _create_anomalies(
    school: School, module_results: List[Dict], db: Session
) -> List[Anomaly]:
    created = []
    anomalous = [r for r in module_results if r["status"] in ("anomaly", "ghost")]

    if not anomalous:
        return created

    severity = _classify_severity(anomalous)

    for result in anomalous:
        anomaly = Anomaly(
            udise_code=school.udise_code,
            anomaly_type=_module_to_anomaly_type(result["module_id"]),
            severity=severity,
            confidence=float(result.get("confidence", 0.5)),
            description=result.get("summary", ""),
            funds_at_risk_inr=float(result.get("discrepancy_amount_inr") or 0),
            detected_at=datetime.utcnow(),
            status=AnomalyStatus.new,
            satellite_before_url=result.get("satellite_image_url"),
            satellite_after_url=result.get("evidence_url"),
            evidence_json={
                "module_id": result["module_id"],
                "reported_value": result.get("reported_value"),
                "verified_value": result.get("verified_value"),
            },
        )
        db.add(anomaly)
        db.flush()
        created.append(anomaly)

    db.commit()
    return created


def _emit_pulse_event(
    anomaly: Anomaly, school: School, district: Optional[District], db: Session
) -> None:
    type_labels = {
        AnomalyType.ghost_school: "GHOST SCHOOL",
        AnomalyType.construction_fraud: "CONSTRUCTION FRAUD",
        AnomalyType.enrollment_inflation: "ENROLLMENT INFLATION",
        AnomalyType.meal_fraud: "MEAL FRAUD",
        AnomalyType.outcome_manipulation: "OUTCOME MANIPULATION",
        AnomalyType.teacher_absence: "TEACHER ABSENCE",
        AnomalyType.budget_misuse: "BUDGET MISUSE",
    }
    label = type_labels.get(anomaly.anomaly_type, "ANOMALY")

    event = PulseEvent(
        anomaly_id=anomaly.id,
        event_type=anomaly.anomaly_type.value,
        headline=f"{label} detected at {school.name}",
        summary=anomaly.description[:300] if anomaly.description else "",
        funds_mentioned_inr=anomaly.funds_at_risk_inr,
        school_name=school.name,
        district_name=district.district_name if district else school.district_code,
        state_name=district.state_name if district else "",
        satellite_url=anomaly.satellite_before_url,
        created_at=datetime.utcnow(),
        is_published=True,
    )
    db.add(event)
    db.commit()


# ── Stub data fetchers (connect to ingestion tables in production) ────────────

def _fetch_grants(udise_code: str, db: Session) -> List[Dict]:
    return []


def _fetch_mdm(udise_code: str, db: Session) -> Optional[Dict]:
    return None


def _fetch_board_results(udise_code: str, db: Session) -> Optional[Dict]:
    return None


def _fetch_aser(district_code: str, db: Session) -> Optional[Dict]:
    return None


def _fetch_cag(district_code: str, db: Session) -> List[Dict]:
    return []


def _fetch_expenditure(district_code: str, db: Session) -> Dict:
    return {"total_budget_inr": 50_000_000, "verified_enrollment": 5000}


def _get_district_ceiling_ratio(district_code: str, db: Session) -> float:
    return 1.05  # slight inflation is normal
