"""
Enrollment inflation detection using census ceilings and building capacity.
"""
import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Government school attendance rate assumption (RTE data)
GOVT_ATTENDANCE_RATE = 0.85

# Inflation threshold: schools reporting > 120% of capacity
INFLATION_THRESHOLD = 1.20


def compute_enrollment_ceiling(
    district_code: str,
    census_df: pd.DataFrame,
    udise_df: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Compute realistic maximum government school enrollment for a district.

    Logic:
    1. Get 6-14 age population from Census (projected to current year)
    2. Subtract private school enrollment from UDISE+
    3. Apply 85% government school attendance rate
    """
    # Census 6-14 population for district
    district_census = census_df[census_df["district_code"] == district_code]
    if district_census.empty:
        logger.warning(f"No census data for district {district_code}")
        return {"district_code": district_code, "ceiling": None, "error": "no_census_data"}

    school_age_pop = int(district_census.iloc[0].get("school_age_population_projected", 0))

    # Private school enrollment
    district_schools = udise_df[udise_df["district_code"] == district_code]
    private_enrollment = int(
        district_schools[district_schools["management_type"] == "private"]["reported_enrollment"]
        .sum()
    )
    aided_enrollment = int(
        district_schools[district_schools["management_type"] == "aided"]["reported_enrollment"]
        .sum()
    )

    available_for_govt = max(0, school_age_pop - private_enrollment - aided_enrollment)
    realistic_max = int(available_for_govt * GOVT_ATTENDANCE_RATE)

    total_govt_reported = int(
        district_schools[district_schools["management_type"] == "government"]["reported_enrollment"]
        .sum()
    )

    return {
        "district_code": district_code,
        "school_age_population": school_age_pop,
        "private_enrollment": private_enrollment,
        "aided_enrollment": aided_enrollment,
        "ceiling": realistic_max,
        "total_govt_reported": total_govt_reported,
        "district_inflation_ratio": (
            total_govt_reported / realistic_max if realistic_max > 0 else None
        ),
    }


def flag_inflated_schools(
    schools_df: pd.DataFrame,
    census_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Flag schools with suspicious enrollment.

    Checks:
    1. Reported enrollment > building capacity (from building detector)
    2. School in district exceeding census ceiling

    Returns schools_df with added columns:
        inflation_ratio, capacity_ratio, flagged_enrollment, flag_reason
    """
    district_ceilings: Dict[str, float] = {}

    for district_code in schools_df["district_code"].unique():
        ceiling_info = compute_enrollment_ceiling(district_code, census_df, schools_df)
        if ceiling_info.get("ceiling") and ceiling_info.get("total_govt_reported"):
            district_ceilings[district_code] = ceiling_info["district_inflation_ratio"] or 1.0
        else:
            district_ceilings[district_code] = 1.0

    def _compute_flags(row):
        reported = int(row.get("reported_enrollment", 0))
        capacity = int(row.get("estimated_capacity", 0))
        district_ratio = district_ceilings.get(row.get("district_code", ""), 1.0)

        # Ratio vs building capacity
        if capacity > 0:
            cap_ratio = reported / capacity
        else:
            cap_ratio = 3.0 if reported > 0 else 1.0

        # Composite inflation ratio
        inflation_ratio = max(cap_ratio, district_ratio)
        flagged = inflation_ratio > INFLATION_THRESHOLD

        flag_reason = ""
        if cap_ratio > INFLATION_THRESHOLD:
            flag_reason += f"exceeds_building_capacity({cap_ratio:.1f}x) "
        if district_ratio > INFLATION_THRESHOLD:
            flag_reason += f"district_ceiling_exceeded({district_ratio:.1f}x)"

        return pd.Series(
            {
                "capacity_ratio": round(cap_ratio, 2),
                "inflation_ratio": round(inflation_ratio, 2),
                "flagged_enrollment": flagged,
                "flag_reason": flag_reason.strip(),
            }
        )

    flags = schools_df.apply(_compute_flags, axis=1)
    return pd.concat([schools_df, flags], axis=1)


def compute_anomaly_score(
    reported: int,
    verified_capacity: int,
    district_ceiling_ratio: float,
) -> float:
    """
    Compute enrollment anomaly score 0-1.

    Weights:
    - Capacity ratio (how much does reported exceed building size): 60%
    - District ceiling ratio (how inflated is the district overall): 40%
    """
    if verified_capacity > 0:
        cap_ratio = reported / verified_capacity
    else:
        cap_ratio = 5.0 if reported > 50 else 1.0

    # Normalise: ratio 1→score 0, ratio 3→score 0.8, ratio 5+→score 1
    cap_score = min(1.0, max(0.0, (cap_ratio - 1.0) / 4.0))
    ceiling_score = min(1.0, max(0.0, (district_ceiling_ratio - 1.0) / 2.0))

    return round(cap_score * 0.6 + ceiling_score * 0.4, 3)
