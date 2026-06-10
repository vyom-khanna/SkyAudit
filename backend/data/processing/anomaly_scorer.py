"""
Seed script: generates full demo dataset for Sitapur district (UP) with
500 schools, realistic anomaly distribution, pulse events, notices, and officer accounts.
"""
import os
import sys
import random
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal, init_db
from app.models import (
    School, District, Verification, Anomaly, Notice, SatelliteCapture,
    PulseEvent, Officer,
    ManagementType, VerificationStatus, AnomalyType, AnomalySeverity, AnomalyStatus,
)
from app.routers.auth import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

rng = random.Random(42)
np_rng = np.random.default_rng(42)

DISTRICT_CODE = "09071"
DISTRICT_NAME = "Sitapur"
STATE_CODE = "09"
STATE_NAME = "Uttar Pradesh"

N_SCHOOLS = 500
BASE_UDISE = 91400100001

# Distribution:  65% green | 20% yellow | 10% orange | 5% red
SCHOOL_STATUS_DIST = [
    ("green", 0.65),
    ("yellow", 0.20),
    ("orange", 0.10),
    ("red", 0.05),
]

MODULE_NAMES = {
    1: "Ghost School Detection",
    2: "Construction Verification",
    3: "Enrollment Verification",
    4: "Mid-Day Meal Verification",
    5: "Learning Outcome Verification",
    6: "Teacher Presence Verification",
    7: "Budget Efficiency Analysis",
}

BLOCKS = [
    "Sitapur", "Reusa", "Mishrikh", "Biswan", "Tambaur",
    "Mahmoodabad", "Laharpur", "Hargaon", "Pisawan", "Sidhauli",
    "Kasmanda", "Rampur Mathura", "Khairabad", "Machrehta", "Parsendi",
]


def _random_coords(seed: int) -> tuple:
    """Generate plausible coordinates within Sitapur district."""
    rng_local = random.Random(seed)
    lat = rng_local.uniform(27.10, 27.85)
    lng = rng_local.uniform(80.45, 81.30)
    return round(lat, 6), round(lng, 6)


def _school_category(idx: int) -> str:
    """Assign school to a category based on distribution."""
    thresholds = []
    cumulative = 0.0
    for cat, prob in SCHOOL_STATUS_DIST:
        cumulative += prob
        thresholds.append((cat, cumulative))

    val = rng.random()
    for cat, threshold in thresholds:
        if val <= threshold:
            return cat
    return "green"


def _make_school(idx: int, category: str) -> School:
    udise = str(BASE_UDISE + idx).zfill(11)
    lat, lng = _random_coords(idx)
    block = rng.choice(BLOCKS)

    if category in ("red",):
        enrollment = rng.randint(150, 400)
        capacity_actual = rng.randint(0, 50)
        teachers = rng.randint(2, 6)
        meals = enrollment  # claiming full ghost enrollment
        building = True  # ghost: reports building but none exists
    elif category == "orange":
        enrollment = rng.randint(100, 350)
        capacity_actual = int(enrollment * rng.uniform(0.40, 0.70))
        teachers = rng.randint(3, 8)
        meals = enrollment
        building = True
    elif category == "yellow":
        enrollment = rng.randint(60, 200)
        capacity_actual = int(enrollment * rng.uniform(0.75, 0.95))
        teachers = rng.randint(2, 7)
        meals = enrollment
        building = True
    else:  # green
        enrollment = rng.randint(40, 180)
        capacity_actual = int(enrollment * rng.uniform(1.0, 1.5))
        teachers = max(1, int(enrollment / rng.uniform(25, 40)))
        meals = enrollment
        building = True

    return School(
        udise_code=udise,
        name=f"Govt Primary School {block} {idx + 1}",
        district_code=DISTRICT_CODE,
        block=block,
        latitude=lat,
        longitude=lng,
        reported_enrollment=enrollment,
        reported_teachers=teachers,
        reported_building_exists=building,
        reported_kitchen_exists=rng.random() > 0.2,
        reported_meals_daily=meals,
        management_type=ManagementType.government,
        created_at=datetime.utcnow() - timedelta(days=rng.randint(100, 800)),
        last_verified_at=datetime.utcnow() - timedelta(days=rng.randint(0, 10)),
    )


def _make_verifications(school: School, category: str) -> list:
    """Create 7 module verification records for a school."""
    verifications = []

    module_statuses = _decide_module_statuses(category)

    for module_id, status in module_statuses.items():
        enrollment = school.reported_enrollment

        if status == "ghost":
            reported_val = f"Building exists, {enrollment} students enrolled"
            verified_val = "No building detected within 100m radius"
            discrepancy = enrollment * 220 * 8.17 + school.reported_teachers * 350_000
            sat_url = _demo_satellite_url(school.latitude, school.longitude, "before")
        elif status == "anomaly":
            if module_id == 3:
                capacity = int(enrollment * rng.uniform(0.30, 0.65))
                reported_val = f"{enrollment} students enrolled"
                verified_val = f"~{capacity} estimated capacity from building size"
                discrepancy = max(0, enrollment - capacity) * 220 * 8.17
            elif module_id == 4:
                excess = int(enrollment * rng.uniform(0.3, 1.5))
                reported_val = f"{enrollment + excess} meals/day claimed"
                verified_val = f"{enrollment} verified students"
                discrepancy = excess * 220 * 8.17
            elif module_id == 5:
                reported_val = f"{rng.uniform(0.90, 0.99):.0%} pass rate"
                verified_val = f"Predicted {rng.uniform(0.45, 0.65):.0%} based on characteristics"
                discrepancy = None
            else:
                reported_val = f"Reported value for module {module_id}"
                verified_val = f"Anomaly detected in module {module_id}"
                discrepancy = rng.uniform(50000, 500000)
            sat_url = None
        else:
            reported_val = _generic_reported(module_id, school)
            verified_val = "Consistent with satellite/census data"
            discrepancy = None
            sat_url = None

        verifications.append(Verification(
            udise_code=school.udise_code,
            module_id=module_id,
            module_name=MODULE_NAMES[module_id],
            status=VerificationStatus(status),
            confidence_score=round(rng.uniform(0.72, 0.97), 3),
            reported_value=reported_val,
            verified_value=verified_val,
            discrepancy_amount_inr=discrepancy,
            satellite_image_url=sat_url,
            evidence_url=sat_url,
            verified_at=datetime.utcnow() - timedelta(days=rng.randint(0, 5)),
            data_source="schooltruth_seed_v1",
        ))

    return verifications


def _decide_module_statuses(category: str) -> dict:
    """Return module_id → status mapping for a school category."""
    if category == "red":
        return {
            1: "ghost", 2: "anomaly", 3: "anomaly",
            4: "anomaly", 5: "pending", 6: "anomaly", 7: "pending",
        }
    if category == "orange":
        flagged_modules = rng.sample([2, 3, 4, 5, 6], k=rng.randint(2, 3))
        return {m: ("anomaly" if m in flagged_modules else "verified") for m in range(1, 8)}
    if category == "yellow":
        flagged_module = rng.choice([3, 4, 5, 6])
        return {m: ("anomaly" if m == flagged_module else "verified") for m in range(1, 8)}
    # green
    return {m: "verified" for m in range(1, 8)}


def _generic_reported(module_id: int, school: School) -> str:
    mapping = {
        1: f"Building exists, {school.reported_enrollment} students",
        2: "No construction grants on record",
        3: f"{school.reported_enrollment} students enrolled",
        4: f"{school.reported_meals_daily} meals/day",
        5: f"{rng.uniform(0.55, 0.80):.0%} pass rate",
        6: f"{school.reported_teachers} teachers on roll",
        7: "Within district budget norms",
    }
    return mapping.get(module_id, "Reported value")


def _demo_satellite_url(lat: float, lng: float, image_type: str = "latest") -> str:
    delta = 0.003
    bbox = f"{lng-delta},{lat-delta},{lng+delta},{lat+delta}"
    return (
        f"https://services.sentinel-hub.com/ogc/wms/demo"
        f"?REQUEST=GetMap&BBOX={bbox}&CRS=EPSG:4326"
        f"&LAYERS=TRUE_COLOR&FORMAT=image/jpeg&WIDTH=400&HEIGHT=400"
        f"&TIME=2024-01-01/2024-03-31"
    )


def _make_anomaly(school: School, category: str) -> Anomaly:
    """Create a single anomaly record for anomalous schools."""
    if category == "red":
        atype = AnomalyType.ghost_school
        severity = AnomalySeverity.critical
        funds = school.reported_enrollment * 220 * 8.17 + school.reported_teachers * 350_000
        description = (
            f"Satellite imagery detects no building at {school.name}. "
            f"School claims {school.reported_enrollment} students and "
            f"{school.reported_teachers} teachers. "
            f"Estimated ₹{funds/100_000:.1f}L in annual public funds at risk."
        )
    elif category == "orange":
        atype = rng.choice([
            AnomalyType.enrollment_inflation,
            AnomalyType.construction_fraud,
            AnomalyType.meal_fraud,
        ])
        severity = AnomalySeverity.high
        funds = school.reported_enrollment * rng.uniform(0.3, 0.6) * 220 * 8.17
        description = (
            f"Significant discrepancy detected at {school.name}: "
            f"{atype.value.replace('_', ' ')} anomaly with "
            f"₹{funds/100_000:.1f}L at risk."
        )
    else:
        atype = rng.choice([AnomalyType.meal_fraud, AnomalyType.outcome_manipulation])
        severity = AnomalySeverity.medium
        funds = rng.uniform(50_000, 200_000)
        description = (
            f"Minor discrepancy at {school.name}: "
            f"{atype.value.replace('_', ' ')} flagged for review."
        )

    detected_days_ago = rng.randint(1, 90)
    detected_at = datetime.utcnow() - timedelta(days=detected_days_ago)

    status = AnomalyStatus.new
    notice_sent_at = None
    response_due_at = None

    if detected_days_ago > 3:
        status = AnomalyStatus.noticed
        notice_sent_at = detected_at + timedelta(days=2)
        response_due_at = notice_sent_at + timedelta(days=30)

    if detected_days_ago > 40 and rng.random() > 0.6:
        status = AnomalyStatus.acknowledged

    if detected_days_ago > 60 and rng.random() > 0.7:
        status = AnomalyStatus.resolved

    lat, lng = school.latitude, school.longitude
    return Anomaly(
        udise_code=school.udise_code,
        anomaly_type=atype,
        severity=severity,
        confidence=round(rng.uniform(0.65, 0.96), 3),
        description=description,
        funds_at_risk_inr=round(funds, 2),
        detected_at=detected_at,
        status=status,
        notice_sent_at=notice_sent_at,
        response_due_at=response_due_at,
        resolved_at=datetime.utcnow() - timedelta(days=rng.randint(1, 10)) if status == AnomalyStatus.resolved else None,
        satellite_before_url=_demo_satellite_url(lat, lng, "before") if category == "red" else None,
        satellite_after_url=_demo_satellite_url(lat, lng, "after") if category == "red" else None,
        evidence_json={"seed": True, "category": category},
    )


def _make_notice(anomaly: Anomaly, escalation_level: int) -> Notice:
    sent_at = anomaly.notice_sent_at or datetime.utcnow() - timedelta(days=20)
    recipient = {1: "DEO", 2: "State", 3: "Ministry"}[escalation_level]

    return Notice(
        anomaly_id=anomaly.id,
        sent_to=recipient,
        sent_at=sent_at,
        response_deadline=sent_at + timedelta(days=30),
        response_received=anomaly.status == AnomalyStatus.resolved,
        response_text=(
            "Inspection conducted. Building under repair." if anomaly.status == AnomalyStatus.resolved else None
        ),
        cc_list=[f"deo-{DISTRICT_CODE}@education.gov.in"],
        escalation_level=escalation_level,
    )


def _make_pulse_event(anomaly: Anomaly, school: School) -> PulseEvent:
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
    funds_l = anomaly.funds_at_risk_inr / 100_000

    return PulseEvent(
        anomaly_id=anomaly.id,
        event_type=anomaly.anomaly_type.value,
        headline=f"{label} detected at {school.name}",
        summary=anomaly.description[:250],
        funds_mentioned_inr=anomaly.funds_at_risk_inr,
        school_name=school.name,
        district_name=DISTRICT_NAME,
        state_name=STATE_NAME,
        satellite_url=anomaly.satellite_before_url,
        created_at=anomaly.detected_at + timedelta(hours=rng.randint(1, 6)),
        is_published=True,
    )


def _seed_all_up_districts(db) -> None:
    """Seed accountability scores for all 75 UP districts."""
    from data.ingestion.census_loader import _generate_synthetic_census
    census_df = _generate_synthetic_census()

    for _, row in census_df.iterrows():
        code = row["district_code"]
        name = row["district_name"]

        # Skip if already seeded
        existing = db.query(District).filter(District.district_code == code).first()
        if existing:
            continue

        # Realistic score distribution: mean=52, std=18, clipped 15-90
        score = float(np.clip(np_rng.normal(52, 18), 15, 90))
        n_schools = rng.randint(400, 1800)
        verified = int(n_schools * rng.uniform(0.3, 0.9))
        flagged = int(verified * rng.uniform(0.05, 0.35))

        district = District(
            district_code=code,
            district_name=name,
            state_code=STATE_CODE,
            state_name=STATE_NAME,
            total_schools=n_schools,
            verified_schools=verified,
            flagged_schools=flagged,
            accountability_score=round(score, 2),
            last_updated=datetime.utcnow() - timedelta(days=rng.randint(0, 7)),
        )
        db.add(district)

    db.commit()
    logger.info("Seeded all UP districts")


def _seed_officers(db) -> None:
    """Create 3 sample officer accounts."""
    officers_data = [
        {
            "email": "deo@sitapur.education.up.gov.in",
            "name": "Rajesh Kumar (DEO Sitapur)",
            "role": "DEO",
            "district_code": DISTRICT_CODE,
            "state_code": STATE_CODE,
            "password": "schooltruth2024",
        },
        {
            "email": "state.education@up.gov.in",
            "name": "Priya Sharma (State Education)",
            "role": "State",
            "district_code": None,
            "state_code": STATE_CODE,
            "password": "schooltruth2024",
        },
        {
            "email": "demo@schooltruth.in",
            "name": "Demo User (Full Access)",
            "role": "Ministry",
            "district_code": None,
            "state_code": None,
            "password": "demo1234",
        },
    ]

    for o in officers_data:
        existing = db.query(Officer).filter(Officer.email == o["email"]).first()
        if existing:
            existing.hashed_password = hash_password(o["password"])
            existing.name = o["name"]
            existing.role = o["role"]
            existing.district_code = o.get("district_code")
            existing.state_code = o.get("state_code")
            continue
        officer = Officer(
            email=o["email"],
            name=o["name"],
            role=o["role"],
            district_code=o.get("district_code"),
            state_code=o.get("state_code"),
            hashed_password=hash_password(o["password"]),
            last_login=None,
        )
        db.add(officer)

    db.commit()
    logger.info("Seeded 3 officer accounts")


def run_seed():
    """Main seed function — runs all steps in order."""
    logger.info("=== SchoolTruth Seed Script Starting ===")
    init_db()
    db = SessionLocal()

    try:
        # ── Step 1: Sitapur district ──────────────────────────────────────
        sitapur = db.query(District).filter(District.district_code == DISTRICT_CODE).first()
        if not sitapur:
            sitapur = District(
                district_code=DISTRICT_CODE,
                district_name=DISTRICT_NAME,
                state_code=STATE_CODE,
                state_name=STATE_NAME,
                total_schools=N_SCHOOLS,
                verified_schools=0,
                flagged_schools=0,
                accountability_score=0.0,
                last_updated=datetime.utcnow(),
            )
            db.add(sitapur)
            db.commit()
        logger.info(f"District {DISTRICT_NAME} ready")

        # ── Step 2: All UP districts ──────────────────────────────────────
        _seed_all_up_districts(db)

        # ── Step 3: 500 schools ───────────────────────────────────────────
        categories = []
        for i in range(N_SCHOOLS):
            categories.append(_school_category(i))

        schools_created = 0
        anomalies_created = 0
        notices_created = 0
        pulse_created = 0

        for i, category in enumerate(categories):
            udise = str(BASE_UDISE + i).zfill(11)

            existing_school = db.query(School).filter(School.udise_code == udise).first()
            if existing_school:
                school = existing_school
            else:
                school = _make_school(i, category)
                db.add(school)
                db.flush()
                schools_created += 1

            # Verifications
            existing_v = db.query(Verification).filter(
                Verification.udise_code == udise
            ).first()
            if not existing_v:
                verifications = _make_verifications(school, category)
                for v in verifications:
                    db.add(v)

            # Anomalies for non-green schools
            if category != "green":
                existing_a = db.query(Anomaly).filter(
                    Anomaly.udise_code == udise
                ).first()
                if not existing_a:
                    anomaly = _make_anomaly(school, category)
                    db.add(anomaly)
                    db.flush()
                    anomalies_created += 1

                    # Notice
                    if anomaly.notice_sent_at:
                        escalation = (
                            3 if (datetime.utcnow() - anomaly.detected_at).days > 90
                            else 2 if (datetime.utcnow() - anomaly.detected_at).days > 60
                            else 1
                        )
                        notice = _make_notice(anomaly, escalation)
                        db.add(notice)
                        notices_created += 1

                    # Pulse event
                    event = _make_pulse_event(anomaly, school)
                    db.add(event)
                    pulse_created += 1

            if i % 100 == 0:
                db.commit()
                logger.info(f"Progress: {i}/{N_SCHOOLS} schools processed")

        db.commit()

        # ── Step 4: Satellite captures ────────────────────────────────────
        ghost_schools = [
            s for s, c in zip(
                db.query(School).filter(School.district_code == DISTRICT_CODE).all(),
                categories,
            )
            if c == "red"
        ]
        for school in ghost_schools[:25]:
            from datetime import date
            cap = SatelliteCapture(
                udise_code=school.udise_code,
                capture_date=date.today() - timedelta(days=rng.randint(1, 5)),
                image_url=_demo_satellite_url(school.latitude, school.longitude),
                ndbi_score=round(rng.uniform(-0.15, 0.01), 4),  # negative = no building
                building_detected=False,
                building_confidence=round(rng.uniform(0.82, 0.97), 3),
                building_footprint_sqm=0.0,
                source="sentinel2",
            )
            db.add(cap)
        db.commit()

        # ── Step 5: Update Sitapur district score ─────────────────────────
        green_pct = categories.count("green") / N_SCHOOLS
        sitapur.accountability_score = round(green_pct * 100 * 0.85 + 10, 2)
        sitapur.verified_schools = N_SCHOOLS
        sitapur.flagged_schools = anomalies_created
        sitapur.last_updated = datetime.utcnow()
        db.commit()

        # ── Step 6: Officer accounts ──────────────────────────────────────
        _seed_officers(db)

        logger.info("=== Seed Complete ===")
        logger.info(f"  Schools created:    {schools_created}")
        logger.info(f"  Anomalies created:  {anomalies_created}")
        logger.info(f"  Notices created:    {notices_created}")
        logger.info(f"  Pulse events:       {pulse_created}")
        logger.info(f"  Categories: green={categories.count('green')} "
                    f"yellow={categories.count('yellow')} "
                    f"orange={categories.count('orange')} "
                    f"red={categories.count('red')}")
        logger.info(f"\nDemo login: demo@schooltruth.in / demo1234")

    except Exception as exc:
        db.rollback()
        logger.error(f"Seed failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
