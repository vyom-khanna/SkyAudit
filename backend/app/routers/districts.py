from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import School, District, Anomaly, Verification, AnomalySeverity
from app.schemas import DistrictOut, SchoolPin, AnomalyOut, DistrictRanking

router = APIRouter(prefix="/districts", tags=["districts"])


@router.get("/rankings", response_model=List[DistrictRanking])
def get_district_rankings(
    state: Optional[str] = Query(None, description="Filter by state code"),
    sort_by: str = Query("accountability_score", description="Sort field"),
    limit: int = Query(100, ge=1, le=823),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """National ranking of all districts, sortable and filterable."""
    query = db.query(District)
    if state:
        query = query.filter(District.state_code == state)

    if sort_by == "accountability_score":
        query = query.order_by(desc(District.accountability_score))
    elif sort_by == "flagged_schools":
        query = query.order_by(desc(District.flagged_schools))
    else:
        query = query.order_by(desc(District.accountability_score))

    all_districts = query.all()
    total = len(all_districts)
    paged = all_districts[offset: offset + limit]

    rankings = []
    for idx, district in enumerate(paged):
        rank = offset + idx + 1

        # Ghost count
        ghost_count = (
            db.query(func.count(Anomaly.id))
            .join(School, Anomaly.udise_code == School.udise_code)
            .filter(
                School.district_code == district.district_code,
                Anomaly.anomaly_type == "ghost_school",
            )
            .scalar()
            or 0
        )

        # Funds at risk
        funds_at_risk = (
            db.query(func.coalesce(func.sum(Anomaly.funds_at_risk_inr), 0))
            .join(School, Anomaly.udise_code == School.udise_code)
            .filter(School.district_code == district.district_code)
            .scalar()
            or 0.0
        )

        # Unresolved notices
        from app.models import Notice
        unresolved = (
            db.query(func.count(Notice.id))
            .join(Anomaly, Notice.anomaly_id == Anomaly.id)
            .join(School, Anomaly.udise_code == School.udise_code)
            .filter(
                School.district_code == district.district_code,
                Notice.response_received == False,
            )
            .scalar()
            or 0
        )

        rankings.append(
            DistrictRanking(
                rank=rank,
                district_code=district.district_code,
                district_name=district.district_name,
                state_name=district.state_name,
                accountability_score=district.accountability_score,
                ghost_count=ghost_count,
                funds_at_risk=float(funds_at_risk),
                unresolved_notices=unresolved,
                trend="stable",  # computed from history in production
            )
        )

    return rankings


@router.get("/{district_code}", response_model=dict)
def get_district_profile(district_code: str, db: Session = Depends(get_db)):
    """Full district profile with accountability score and breakdown."""
    district = db.query(District).filter(District.district_code == district_code).first()
    if not district:
        raise HTTPException(status_code=404, detail=f"District {district_code} not found")

    # Anomaly counts by type
    from app.models import AnomalyType, AnomalyStatus
    anomaly_counts = {}
    for atype in AnomalyType:
        count = (
            db.query(func.count(Anomaly.id))
            .join(School, Anomaly.udise_code == School.udise_code)
            .filter(
                School.district_code == district_code,
                Anomaly.anomaly_type == atype,
            )
            .scalar()
            or 0
        )
        anomaly_counts[atype.value] = count

    # Module aggregate scores
    module_stats = {}
    for module_id in range(1, 8):
        total = db.query(func.count(Verification.id)).join(
            School, Verification.udise_code == School.udise_code
        ).filter(
            School.district_code == district_code,
            Verification.module_id == module_id,
        ).scalar() or 0

        anomalous = db.query(func.count(Verification.id)).join(
            School, Verification.udise_code == School.udise_code
        ).filter(
            School.district_code == district_code,
            Verification.module_id == module_id,
            Verification.status.in_(["anomaly", "ghost"]),
        ).scalar() or 0

        module_stats[module_id] = {
            "total": total,
            "anomalous": anomalous,
            "pct_ok": round((total - anomalous) / max(total, 1) * 100, 1),
        }

    # National rank
    all_districts_scored = (
        db.query(District).order_by(desc(District.accountability_score)).all()
    )
    rank = next(
        (i + 1 for i, d in enumerate(all_districts_scored) if d.district_code == district_code),
        None,
    )
    total_districts = len(all_districts_scored)

    # Funds at risk
    total_funds = (
        db.query(func.coalesce(func.sum(Anomaly.funds_at_risk_inr), 0))
        .join(School, Anomaly.udise_code == School.udise_code)
        .filter(School.district_code == district_code)
        .scalar()
        or 0.0
    )

    return {
        "district": DistrictOut.model_validate(district),
        "accountability_score": district.accountability_score,
        "national_rank": rank,
        "total_districts": total_districts,
        "anomaly_counts": anomaly_counts,
        "module_stats": module_stats,
        "total_funds_at_risk_inr": float(total_funds),
        "trend": "stable",
    }


@router.get("/{district_code}/schools", response_model=List[SchoolPin])
def get_district_schools(
    district_code: str,
    status: Optional[str] = Query(None, description="Filter by verification status"),
    module: Optional[int] = Query(None, description="Filter by module ID"),
    severity: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """All schools in district with pin data for map, filterable."""
    district = db.query(District).filter(District.district_code == district_code).first()
    if not district:
        raise HTTPException(status_code=404, detail="District not found")

    schools_query = db.query(School).filter(School.district_code == district_code)
    schools = schools_query.offset(offset).limit(limit).all()

    pins = []
    for school in schools:
        if school.latitude is None or school.longitude is None:
            continue

        # Get worst anomaly status for this school
        worst_anomaly = (
            db.query(Anomaly)
            .filter(Anomaly.udise_code == school.udise_code)
            .order_by(
                desc(
                    func.case(
                        (Anomaly.severity == AnomalySeverity.critical, 4),
                        (Anomaly.severity == AnomalySeverity.high, 3),
                        (Anomaly.severity == AnomalySeverity.medium, 2),
                        else_=1,
                    )
                )
            )
            .first()
        )

        pin_status = "verified"
        pin_severity = None
        has_anomaly = False

        if worst_anomaly:
            has_anomaly = True
            pin_status = worst_anomaly.anomaly_type.value
            pin_severity = worst_anomaly.severity.value

        if status and pin_status != status:
            continue
        if severity and pin_severity != severity:
            continue

        pins.append(
            SchoolPin(
                udise_code=school.udise_code,
                name=school.name,
                latitude=school.latitude,
                longitude=school.longitude,
                accountability_score=None,
                status=pin_status,
                has_anomaly=has_anomaly,
                severity=pin_severity,
            )
        )

    return pins


@router.get("/{district_code}/anomalies", response_model=List[AnomalyOut])
def get_district_anomalies(
    district_code: str,
    sort_by: str = Query("detected_at"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """All anomalies in district, sorted."""
    district = db.query(District).filter(District.district_code == district_code).first()
    if not district:
        raise HTTPException(status_code=404, detail="District not found")

    query = (
        db.query(Anomaly)
        .join(School, Anomaly.udise_code == School.udise_code)
        .filter(School.district_code == district_code)
    )

    if sort_by == "funds_at_risk":
        query = query.order_by(desc(Anomaly.funds_at_risk_inr))
    elif sort_by == "severity":
        query = query.order_by(desc(Anomaly.severity))
    else:
        query = query.order_by(desc(Anomaly.detected_at))

    anomalies = query.offset(offset).limit(limit).all()
    return [AnomalyOut.model_validate(a) for a in anomalies]
