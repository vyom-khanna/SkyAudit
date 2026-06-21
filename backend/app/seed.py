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
import pandas as pd

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

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

N_SCHOOLS = 15
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


def _random_coords(seed: int, category: str) -> tuple:
    """Generate plausible coordinates within Sitapur district that hash deterministically to correct footprints."""
    rng_local = random.Random(seed)
    attempts = 0
    while attempts < 1000:
        lat = round(rng_local.uniform(27.10, 27.85), 6)
        lng = round(rng_local.uniform(80.45, 81.30), 6)
        
        # Calculate the fallback detection hash seed
        hseed = int(hashlib.md5(f"{lat:.4f}{lng:.4f}".encode()).hexdigest(), 16) % 100
        if category == "red":
            if hseed <= 25:
                return lat, lng
        else:
            if hseed > 25:
                return lat, lng
        attempts += 1
    
    # Fallback default
    lat = round(rng_local.uniform(27.10, 27.85), 6)
    lng = round(rng_local.uniform(80.45, 81.30), 6)
    return lat, lng


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
    lat, lng = _random_coords(idx, category)
    block = rng.choice(BLOCKS)

    if category in ("red",):
        # Ghost: reported building = True, but footprint = 0
        enrollment = rng.randint(150, 400)
        teachers = rng.randint(2, 6)
        meals = enrollment
        building = True
    elif category == "orange":
        # Orange: Capacity discrepancy >50% OR Teacher absence >50% OR Mid-day meal claims >130%
        factor = rng.choice(["capacity", "teacher", "meals"])
        
        if factor == "capacity":
            # Capacity discrepancy > 50% (enrollment > capacity * 1.50)
            hseed = int(hashlib.md5(f"{lat:.4f}{lng:.4f}".encode()).hexdigest(), 16) % 100
            footprint = hseed * 3.0
            capacity = int(footprint * 0.7)
            enrollment = int(capacity * rng.uniform(1.6, 2.2))
            teachers = max(1, int(enrollment / 30))
            meals = enrollment
            building = True
        elif factor == "teacher":
            # Teacher absence > 50% (measured via teacher-student ratio > 45:1)
            enrollment = rng.randint(150, 350)
            teachers = 1  # 1 teacher for 150-350 students -> ratio > 45:1
            meals = enrollment
            building = True
        else:
            # meals claimed > 130% of enrollment
            enrollment = rng.randint(100, 250)
            hseed = int(hashlib.md5(f"{lat:.4f}{lng:.4f}".encode()).hexdigest(), 16) % 100
            footprint = hseed * 3.0
            capacity = int(footprint * 0.7)
            enrollment = min(enrollment, capacity)
            teachers = max(1, int(enrollment / 30))
            meals = int(enrollment * rng.uniform(1.35, 1.6))
            building = True
    elif category == "yellow":
        # Yellow: minor discrepancies (10-50% mismatch)
        factor = rng.choice(["capacity", "teacher", "meals"])
        if factor == "capacity":
            # Capacity discrepancy 10% - 50%
            hseed = int(hashlib.md5(f"{lat:.4f}{lng:.4f}".encode()).hexdigest(), 16) % 100
            footprint = hseed * 3.0
            capacity = int(footprint * 0.7)
            enrollment = int(capacity * rng.uniform(1.15, 1.45))
            teachers = max(1, int(enrollment / 30))
            meals = enrollment
            building = True
        elif factor == "teacher":
            # Teacher ratio slightly off (e.g. ratio between 35:1 and 45:1)
            enrollment = rng.randint(80, 200)
            teachers = max(1, int(enrollment / 40))
            meals = enrollment
            building = True
        else:
            # meals 110% to 130%
            enrollment = rng.randint(60, 180)
            hseed = int(hashlib.md5(f"{lat:.4f}{lng:.4f}".encode()).hexdigest(), 16) % 100
            footprint = hseed * 3.0
            capacity = int(footprint * 0.7)
            enrollment = min(enrollment, capacity)
            teachers = max(1, int(enrollment / 30))
            meals = int(enrollment * rng.uniform(1.12, 1.28))
            building = True
    else:  # green
        # Green: no anomalies (< 10% mismatch)
        enrollment = rng.randint(40, 180)
        hseed = int(hashlib.md5(f"{lat:.4f}{lng:.4f}".encode()).hexdigest(), 16) % 100
        footprint = hseed * 3.0
        capacity = int(footprint * 0.7)
        enrollment = min(enrollment, int(capacity * 0.9))
        teachers = max(1, int(enrollment / 30))
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
    """Create 7 module verification records for a school based on its actual metrics."""
    verifications = []
    
    # 1. Detect footprint via deterministic hash
    hseed = int(hashlib.md5(f"{school.latitude:.4f}{school.longitude:.4f}".encode()).hexdigest(), 16) % 100
    if hseed > 25:
        building_exists = True
        footprint = hseed * 3.0
    else:
        building_exists = False
        footprint = 0.0
        
    estimated_capacity = int(footprint * 0.7)
    sat_url = _demo_satellite_url(school.latitude, school.longitude, "before")

    for module_id in range(1, 8):
        discrepancy = None
        
        if module_id == 1:
            # Ghost School
            is_ghost = school.reported_building_exists and (not building_exists or footprint < 20)
            if is_ghost:
                status = "ghost"
                reported_val = f"Building exists, {school.reported_enrollment} students enrolled"
                verified_val = f"No building detected or footprint critically small ({footprint:.0f} sqm) within 100m"
                discrepancy = school.reported_enrollment * 220 * 8.17 + school.reported_teachers * 350_000
            else:
                status = "verified"
                reported_val = f"Building exists, {school.reported_enrollment} students"
                verified_val = f"Building detected ({footprint:.0f} sqm footprint)"
                
        elif module_id == 2:
            # Construction
            status = "verified"
            reported_val = "No construction grants on record"
            verified_val = "Consistent with satellite/census data"
            
        elif module_id == 3:
            # Enrollment
            if not building_exists:
                status = "anomaly"
                reported_val = f"{school.reported_enrollment} students enrolled"
                verified_val = "0 — no building exists"
                discrepancy = school.reported_enrollment * 220 * 8.17
            else:
                capacity_ratio = school.reported_enrollment / max(estimated_capacity, 1)
                if capacity_ratio > 1.10:
                    status = "anomaly"
                    reported_val = f"{school.reported_enrollment} students"
                    verified_val = f"≈{estimated_capacity} capacity (building size)"
                    excess = max(0, school.reported_enrollment - estimated_capacity)
                    discrepancy = excess * 220 * 8.17 + excess * 1200
                else:
                    status = "verified"
                    reported_val = f"{school.reported_enrollment} students enrolled"
                    verified_val = f"Consistent with building capacity (~{estimated_capacity})"
                    
        elif module_id == 4:
            # Meals
            meals_ratio = school.reported_meals_daily / max(school.reported_enrollment, 1)
            if meals_ratio > 1.10:
                status = "anomaly"
                reported_val = f"{school.reported_meals_daily} meals/day"
                verified_val = f"{school.reported_enrollment} meals/day (= verified students)"
                excess = school.reported_meals_daily - school.reported_enrollment
                discrepancy = excess * 220 * 8.17
            else:
                status = "verified"
                reported_val = f"{school.reported_meals_daily} meals/day"
                verified_val = f"Consistent with {school.reported_enrollment} verified students"
                
        elif module_id == 5:
            # Outcomes
            status = "verified"
            reported_val = f"{rng.uniform(0.65, 0.80):.0%} pass rate"
            verified_val = "Consistent with satellite/census data"
            
        elif module_id == 6:
            # Teachers
            teacher_ratio = school.reported_enrollment / max(school.reported_teachers, 1)
            if teacher_ratio > 35:
                status = "anomaly"
                reported_val = f"{school.reported_teachers} teachers, {school.reported_enrollment} students"
                verified_val = f"High-risk composite score (ratio {teacher_ratio:.0f}:1)"
            else:
                status = "verified"
                reported_val = f"{school.reported_teachers} teachers, {school.reported_enrollment} students"
                verified_val = "Risk score acceptable"
                
        else: # module_id == 7
            status = "verified"
            reported_val = "Within district budget norms"
            verified_val = "Consistent with satellite/census data"

        verifications.append(Verification(
            udise_code=school.udise_code,
            module_id=module_id,
            module_name=MODULE_NAMES[module_id],
            status=VerificationStatus(status),
            confidence_score=round(rng.uniform(0.72, 0.97), 3),
            reported_value=reported_val,
            verified_value=verified_val,
            discrepancy_amount_inr=discrepancy,
            satellite_image_url=sat_url if module_id in (1, 2, 3) else None,
            evidence_url=sat_url if module_id in (1, 2, 3) else None,
            verified_at=datetime.utcnow() - timedelta(days=rng.randint(0, 5)),
            data_source="skyaudit_seed_v1",
        ))

    return verifications


def _demo_satellite_url(lat: float, lng: float, image_type: str = "latest") -> str:
    urls = [
        "https://images.unsplash.com/photo-1502759683299-cdcd6974244f?auto=format&fit=crop&w=400&h=400&q=80",
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=400&h=400&q=80",
        "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?auto=format&fit=crop&w=400&h=400&q=80",
        "https://images.unsplash.com/photo-1524661135-423995f22d0b?auto=format&fit=crop&w=400&h=400&q=80",
        "https://images.unsplash.com/photo-1578328819058-b69f3a3b0f6b?auto=format&fit=crop&w=400&h=400&q=80"
    ]
    val = abs(lat or 0) + abs(lng or 0)
    if image_type == "before":
        val += 0.1
    elif image_type == "after":
        val += 0.2
    idx = int(val * 1000) % len(urls)
    return urls[idx]


def _make_anomaly(school: School, category: str) -> Anomaly:
    """Create a single anomaly record based on school metrics and coordinates."""
    # 1. Detect footprint via deterministic hash
    hseed = int(hashlib.md5(f"{school.latitude:.4f}{school.longitude:.4f}".encode()).hexdigest(), 16) % 100
    if hseed > 25:
        building_exists = True
        footprint = hseed * 3.0
    else:
        building_exists = False
        footprint = 0.0
        
    estimated_capacity = int(footprint * 0.7)

    # Calculate ratios
    capacity_ratio = school.reported_enrollment / max(estimated_capacity, 1) if building_exists else 0.0
    meals_ratio = school.reported_meals_daily / max(school.reported_enrollment, 1)
    teacher_ratio = school.reported_enrollment / max(school.reported_teachers, 1)

    is_ghost = school.reported_building_exists and (not building_exists or footprint < 20)

    if is_ghost:
        atype = AnomalyType.ghost_school
        severity = AnomalySeverity.critical
        funds = school.reported_enrollment * 220 * 8.17 + school.reported_teachers * 350_000
        description = (
            f"Satellite imagery detects no building or footprint critically small ({footprint:.0f} sqm) at {school.name} ({school.latitude:.4f}, {school.longitude:.4f}). "
            f"School claims {school.reported_enrollment} students and "
            f"{school.reported_teachers} teachers. "
            f"Estimated ₹{funds/100_000:.1f}L in annual public funds at risk."
        )
    elif capacity_ratio > 1.50 or teacher_ratio > 45 or meals_ratio > 1.30:
        severity = AnomalySeverity.high
        if capacity_ratio > 1.50:
            atype = AnomalyType.enrollment_inflation
            excess = max(0, school.reported_enrollment - estimated_capacity)
            funds = excess * 220 * 8.17
            description = (
                f"Significant discrepancy detected at {school.name} ({school.latitude:.4f}, {school.longitude:.4f}): "
                f"Enrollment inflation anomaly with ₹{funds/100_000:.1f}L at risk. "
                f"Reported enrollment {school.reported_enrollment} exceeds capacity {estimated_capacity}."
            )
        elif meals_ratio > 1.30:
            atype = AnomalyType.meal_fraud
            excess = max(0, school.reported_meals_daily - school.reported_enrollment)
            funds = excess * 220 * 8.17
            description = (
                f"Significant discrepancy detected at {school.name} ({school.latitude:.4f}, {school.longitude:.4f}): "
                f"Meal fraud anomaly with ₹{funds/100_000:.1f}L at risk. "
                f"Reported meals {school.reported_meals_daily} exceeds enrollment {school.reported_enrollment}."
            )
        else:
            atype = AnomalyType.teacher_absence
            funds = 0.0
            description = (
                f"Significant discrepancy detected at {school.name} ({school.latitude:.4f}, {school.longitude:.4f}): "
                f"Teacher absence anomaly with high student-teacher ratio ({teacher_ratio:.0f}:1)."
            )
    else:
        severity = AnomalySeverity.medium
        if capacity_ratio > 1.10:
            atype = AnomalyType.enrollment_inflation
            excess = max(0, school.reported_enrollment - estimated_capacity)
            funds = excess * 220 * 8.17
            description = (
                f"Minor discrepancy at {school.name} ({school.latitude:.4f}, {school.longitude:.4f}): "
                f"Enrollment inflation flagged for review."
            )
        elif meals_ratio > 1.10:
            atype = AnomalyType.meal_fraud
            excess = max(0, school.reported_meals_daily - school.reported_enrollment)
            funds = excess * 220 * 8.17
            description = (
                f"Minor discrepancy at {school.name} ({school.latitude:.4f}, {school.longitude:.4f}): "
                f"Meal fraud flagged for review."
            )
        else:
            atype = AnomalyType.teacher_absence
            funds = 0.0
            description = (
                f"Minor discrepancy at {school.name} ({school.latitude:.4f}, {school.longitude:.4f}): "
                f"Teacher absence flagged for review."
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
    sat_before = _demo_satellite_url(lat, lng, "before")
    sat_after = _demo_satellite_url(lat, lng, "after")

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
        satellite_before_url=sat_before,
        satellite_after_url=sat_after,
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
        headline=f"{label} detected at {school.name} ({school.latitude:.4f}, {school.longitude:.4f})",
        summary=anomaly.description[:250],
        funds_mentioned_inr=anomaly.funds_at_risk_inr,
        school_name=f"{school.name} ({school.latitude:.4f}, {school.longitude:.4f})",
        district_name=DISTRICT_NAME,
        state_name=STATE_NAME,
        satellite_url=anomaly.satellite_before_url,
        created_at=anomaly.detected_at + timedelta(hours=rng.randint(1, 6)),
        is_published=True,
    )


def _generate_synthetic_census() -> pd.DataFrame:
    """Generate realistic synthetic census data for UP districts."""
    up_districts = [
        ("09001", "Agra"), ("09002", "Aligarh"), ("09003", "Allahabad"),
        ("09004", "Ambedkar Nagar"), ("09005", "Amethi"), ("09006", "Amroha"),
        ("09007", "Auraiya"), ("09008", "Azamgarh"), ("09009", "Baghpat"),
        ("09010", "Bahraich"), ("09011", "Ballia"), ("09012", "Balrampur"),
        ("09013", "Banda"), ("09014", "Barabanki"), ("09015", "Bareilly"),
        ("09016", "Basti"), ("09017", "Bijnor"), ("09018", "Budaun"),
        ("09019", "Bulandshahr"), ("09020", "Chandauli"), ("09021", "Chitrakoot"),
        ("09022", "Deoria"), ("09023", "Etah"), ("09024", "Etawah"),
        ("09025", "Faizabad"), ("09026", "Farrukhabad"), ("09027", "Fatehpur"),
        ("09028", "Firozabad"), ("09029", "Gautam Buddha Nagar"), ("09030", "Ghaziabad"),
        ("09031", "Ghazipur"), ("09032", "Gonda"), ("09033", "Gorakhpur"),
        ("09034", "Hamirpur"), ("09035", "Hapur"), ("09036", "Hardoi"),
        ("09037", "Hathras"), ("09038", "Jalaun"), ("09039", "Jaunpur"),
        ("09040", "Jhansi"), ("09041", "Kannauj"), ("09042", "Kanpur Dehat"),
        ("09043", "Kanpur Nagar"), ("09044", "Kasganj"), ("09045", "Kaushambi"),
        ("09046", "Kheri"), ("09047", "Kushinagar"), ("09048", "Lalitpur"),
        ("09049", "Lucknow"), ("09050", "Maharajganj"), ("09051", "Mahoba"),
        ("09052", "Mainpuri"), ("09053", "Mathura"), ("09054", "Mau"),
        ("09055", "Meerut"), ("09056", "Mirzapur"), ("09057", "Moradabad"),
        ("09058", "Muzaffarnagar"), ("09059", "Pilibhit"), ("09060", "Pratapgarh"),
        ("09061", "Raebareli"), ("09062", "Rampur"), ("09063", "Saharanpur"),
        ("09064", "Sambhal"), ("09065", "Sant Kabir Nagar"), ("09066", "Sant Ravidas Nagar"),
        ("09067", "Shahjahanpur"), ("09068", "Shamli"), ("09069", "Shrawasti"),
        ("09070", "Siddharthnagar"), ("09071", "Sitapur"), ("09072", "Sonbhadra"),
        ("09073", "Sultanpur"), ("09074", "Unnao"), ("09075", "Varanasi"),
    ]

    current_year = datetime.utcnow().year
    years_elapsed = current_year - 2011  # CENSUS_YEAR
    growth_factor = (1 + 0.012) ** years_elapsed  # ANNUAL_GROWTH_RATE

    records = []
    for code, name in up_districts:
        pop_2011 = rng.randint(80_000, 350_000)
        projected = int(pop_2011 * growth_factor)
        records.append({
            "district_code": code,
            "district_name": name,
            "state_code": "09",
            "state_name": "Uttar Pradesh",
            "school_age_population_2011": pop_2011,
            "school_age_population_projected": projected,
            "projection_year": current_year,
            "growth_factor": round(growth_factor, 4),
        })

    return pd.DataFrame(records)


def _seed_all_up_districts(db) -> None:
    """Seed accountability scores for all 75 UP districts."""
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
            "password": "skyaudit2024",
        },
        {
            "email": "state.education@up.gov.in",
            "name": "Priya Sharma (State Education)",
            "role": "State",
            "district_code": None,
            "state_code": STATE_CODE,
            "password": "skyaudit2024",
        },
        {
            "email": "demo@skyaudit.in",
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
    logger.info("=== SkyAudit Seed Script Starting ===")
    init_db()
    db = SessionLocal()

    try:
        # Clear existing tables to ensure a clean slate
        logger.info("Clearing existing data...")
        db.query(Notice).delete()
        db.query(PulseEvent).delete()
        db.query(SatelliteCapture).delete()
        db.query(Anomaly).delete()
        db.query(Verification).delete()
        db.query(School).delete()
        db.query(Officer).delete()
        db.query(District).delete()
        db.commit()

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
        from app.services.satellite import _init_ee, get_sentinel2_image
        ee_available = _init_ee()
        for school in ghost_schools[:25]:
            from datetime import date
            sat_url = None
            ndbi_score = None
            source_name = "demo"
            if ee_available:
                try:
                    img_res = get_sentinel2_image(
                        school.latitude, school.longitude,
                        (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d"),
                        datetime.utcnow().strftime("%Y-%m-%d")
                    )
                    sat_url = img_res.get("image_url")
                    ndbi_score = img_res.get("ndbi")
                    source_name = img_res.get("source")
                except Exception as e:
                    logger.warning(f"GEE call failed in SatelliteCapture seed for {school.udise_code}: {e}")
            
            if not sat_url:
                sat_url = _demo_satellite_url(school.latitude, school.longitude)
            if ndbi_score is None:
                ndbi_score = round(rng.uniform(-0.15, 0.01), 4)

            cap = SatelliteCapture(
                udise_code=school.udise_code,
                capture_date=date.today() - timedelta(days=rng.randint(1, 5)),
                image_url=sat_url,
                ndbi_score=ndbi_score,  # negative = no building
                building_detected=False,
                building_confidence=round(rng.uniform(0.82, 0.97), 3),
                building_footprint_sqm=0.0,
                source=source_name,
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
        logger.info(f"\nDemo login: demo@skyaudit.in / demo1234")

    except Exception as exc:
        db.rollback()
        logger.error(f"Seed failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
