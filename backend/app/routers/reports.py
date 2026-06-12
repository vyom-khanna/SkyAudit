import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import Anomaly, School, District, Notice, PulseEvent, AnomalyStatus
from app.schemas import NationalSummary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/national/summary", response_model=NationalSummary)
def get_national_summary(db: Session = Depends(get_db)):
    """National dashboard numbers."""
    total_verified = (
        db.query(func.count(School.udise_code.distinct()))
        .filter(School.last_verified_at != None)
        .scalar()
        or 0
    )

    total_flagged = (
        db.query(func.count(Anomaly.id.distinct()))
        .filter(Anomaly.status != AnomalyStatus.resolved)
        .scalar()
        or 0
    )

    total_ghost = (
        db.query(func.count(Anomaly.id))
        .filter(Anomaly.anomaly_type == "ghost_school")
        .scalar()
        or 0
    )

    total_funds = (
        db.query(func.coalesce(func.sum(Anomaly.funds_at_risk_inr), 0))
        .filter(Anomaly.status != AnomalyStatus.resolved)
        .scalar()
        or 0.0
    )

    most_flagged = (
        db.query(District.district_name, func.count(Anomaly.id).label("cnt"))
        .join(School, District.district_code == School.district_code)
        .join(Anomaly, School.udise_code == Anomaly.udise_code)
        .group_by(District.district_name)
        .order_by(desc("cnt"))
        .first()
    )

    most_improved = (
        db.query(District.district_name)
        .order_by(desc(District.accountability_score))
        .filter(District.accountability_score > 70)
        .first()
    )

    return NationalSummary(
        total_schools_verified=int(total_verified),
        total_flagged=int(total_flagged),
        total_ghost_schools=int(total_ghost),
        total_funds_at_risk_inr=float(total_funds),
        most_flagged_district=most_flagged[0] if most_flagged else "N/A",
        most_improved_district=most_improved[0] if most_improved else "N/A",
        last_updated=datetime.utcnow(),
    )


# Deleted district PDF report endpoint


@router.get("/weekly/{state_code}")
def get_weekly_state_report(state_code: str, db: Session = Depends(get_db)):
    """Weekly state summary — new anomalies, resolved, funds at risk."""
    from datetime import timedelta

    week_ago = datetime.utcnow() - timedelta(days=7)

    new_anomalies = (
        db.query(Anomaly)
        .join(School, Anomaly.udise_code == School.udise_code)
        .join(District, School.district_code == District.district_code)
        .filter(
            District.state_code == state_code,
            Anomaly.detected_at >= week_ago,
        )
        .all()
    )

    resolved_anomalies = (
        db.query(Anomaly)
        .join(School, Anomaly.udise_code == School.udise_code)
        .join(District, School.district_code == District.district_code)
        .filter(
            District.state_code == state_code,
            Anomaly.resolved_at >= week_ago,
            Anomaly.status == AnomalyStatus.resolved,
        )
        .all()
    )

    total_new_funds = sum(a.funds_at_risk_inr for a in new_anomalies)
    state_name_row = (
        db.query(District.state_name)
        .filter(District.state_code == state_code)
        .first()
    )
    state_name = state_name_row[0] if state_name_row else state_code

    top_5 = sorted(new_anomalies, key=lambda a: a.funds_at_risk_inr, reverse=True)[:5]

    return {
        "state_code": state_code,
        "state_name": state_name,
        "week_ending": datetime.utcnow().isoformat(),
        "new_anomalies": len(new_anomalies),
        "resolved_anomalies": len(resolved_anomalies),
        "total_funds_newly_flagged_inr": float(total_new_funds),
        "top_cases": [
            {
                "anomaly_id": a.id,
                "udise_code": a.udise_code,
                "type": a.anomaly_type.value,
                "severity": a.severity.value,
                "funds_at_risk_inr": a.funds_at_risk_inr,
                "description": a.description[:200] if a.description else "",
                "satellite_url": a.satellite_before_url,
            }
            for a in top_5
        ],
    }


# PDF generation helper removed
