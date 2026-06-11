"""
Satellite imagery service using Google Earth Engine.
Falls back to cached URLs when EE is unavailable (demo mode).
"""
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

_EE_INITIALIZED = False

# Public Sentinel-2 tiles for demo fallback (real imagery locations in India)
DEMO_SATELLITE_URLS = [
    "https://earthengine.googleapis.com/v1/projects/earthengine-legacy/thumbnails/placeholder1",
    "https://storage.googleapis.com/gee-public/sentinel2_india_demo1.jpg",
    "https://storage.googleapis.com/gee-public/sentinel2_india_demo2.jpg",
]

FALLBACK_THUMBNAIL = (
    "https://services.sentinel-hub.com/ogc/wms/placeholder"
    "?REQUEST=GetMap&BBOX=80.9,26.8,81.1,27.0&CRS=EPSG:4326"
    "&LAYERS=TRUE_COLOR&FORMAT=image/jpeg&WIDTH=400&HEIGHT=400"
)


def _init_ee():
    """Initialise Earth Engine with service account credentials."""
    global _EE_INITIALIZED
    if _EE_INITIALIZED:
        return True

    key_file = os.getenv("GOOGLE_EARTH_ENGINE_KEY")
    if not key_file or not os.path.exists(key_file):
        logger.warning("EE key not found — running in demo/cache mode")
        return False

    try:
        import ee
        credentials = ee.ServiceAccountCredentials(
            email=os.getenv("GEE_SERVICE_ACCOUNT_EMAIL", ""),
            key_file=key_file,
        )
        ee.Initialize(credentials)
        _EE_INITIALIZED = True
        logger.info("Google Earth Engine initialised successfully")
        return True
    except Exception as exc:
        logger.error(f"Earth Engine init failed: {exc}")
        return False


def _ee_with_backoff(fn, max_retries: int = 4):
    """Execute an EE call with exponential backoff on quota errors."""
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            msg = str(exc).lower()
            if "quota" in msg or "rate" in msg or "429" in msg:
                wait = 2 ** attempt * 5
                logger.warning(f"EE quota hit, waiting {wait}s (attempt {attempt+1})")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("EE quota exceeded after retries")


def get_sentinel2_image(
    lat: float,
    lng: float,
    date_start: str,
    date_end: str,
) -> Dict[str, Any]:
    """
    Return least-cloudy Sentinel-2 composite clipped to 500m buffer.

    Returns dict with keys: image_url, ndbi, metadata, source
    Falls back to demo thumbnail if EE unavailable.
    """
    if not _init_ee():
        return _demo_image_response(lat, lng)

    try:
        import ee

        def _fetch():
            point = ee.Geometry.Point([lng, lat])
            region = point.buffer(500)

            collection = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterDate(date_start, date_end)
                .filterBounds(region)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
                .sort("CLOUDY_PIXEL_PERCENTAGE")
            )

            image = collection.first().clip(region)

            # Compute NDBI
            swir = image.select("B11")
            nir = image.select("B8")
            ndbi = swir.subtract(nir).divide(swir.add(nir)).rename("NDBI")
            ndbi_val = ndbi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=region,
                scale=20,
                maxPixels=1e6,
            ).getInfo().get("NDBI", 0.0)

            # Export thumbnail
            thumb_url = image.getThumbURL(
                {
                    "bands": ["B4", "B3", "B2"],
                    "min": 0,
                    "max": 3000,
                    "dimensions": 400,
                    "region": region,
                    "format": "jpg",
                }
            )

            return {
                "image_url": thumb_url,
                "ndbi": float(ndbi_val or 0.0),
                "source": "sentinel2",
                "metadata": {
                    "date_start": date_start,
                    "date_end": date_end,
                    "lat": lat,
                    "lng": lng,
                },
            }

        return _ee_with_backoff(_fetch)

    except Exception as exc:
        logger.error(f"Sentinel-2 fetch failed for ({lat},{lng}): {exc}")
        return _demo_image_response(lat, lng)


def get_before_after_images(
    lat: float,
    lng: float,
    grant_date: datetime,
) -> Tuple[Dict, Dict]:
    """
    Return before/after Sentinel-2 images relative to grant date.
    Before: 3 months before grant_date
    After:  12 months after grant_date
    """
    before_end = grant_date - timedelta(days=1)
    before_start = grant_date - timedelta(days=90)
    after_start = grant_date + timedelta(days=1)
    after_end = grant_date + timedelta(days=365)

    fmt = "%Y-%m-%d"
    before = get_sentinel2_image(lat, lng, before_start.strftime(fmt), before_end.strftime(fmt))
    after = get_sentinel2_image(lat, lng, after_start.strftime(fmt), after_end.strftime(fmt))
    return before, after


def compute_ndbi(lat: float, lng: float, image_date: str) -> float:
    """
    Compute NDBI = (SWIR - NIR) / (SWIR + NIR) for a location.
    Positive values indicate built-up area.
    """
    result = get_sentinel2_image(
        lat, lng,
        image_date,
        (datetime.strptime(image_date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d"),
    )
    return result.get("ndbi", 0.0)


def detect_building_change(
    before_result: Dict,
    after_result: Dict,
) -> Dict[str, Any]:
    """
    Compare NDBI scores to detect construction activity.
    Returns change_detected (bool) and change_magnitude (float).
    """
    ndbi_before = before_result.get("ndbi", 0.0)
    ndbi_after = after_result.get("ndbi", 0.0)
    magnitude = ndbi_after - ndbi_before

    return {
        "change_detected": magnitude > 0.05,
        "change_magnitude": float(magnitude),
        "ndbi_before": float(ndbi_before),
        "ndbi_after": float(ndbi_after),
    }


def export_thumbnail(lat: float, lng: float, zoom: int = 17) -> str:
    """
    Export a 400x400 thumbnail centred on coordinates.
    Returns public URL. Falls back to demo URL.
    """
    if not _init_ee():
        return _build_demo_thumbnail_url(lat, lng)

    try:
        import ee

        def _fetch():
            point = ee.Geometry.Point([lng, lat])
            region = point.buffer(300)
            image = (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterBounds(region)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
                .sort("CLOUDY_PIXEL_PERCENTAGE")
                .first()
                .clip(region)
            )
            return image.getThumbURL(
                {
                    "bands": ["B4", "B3", "B2"],
                    "min": 0,
                    "max": 3000,
                    "dimensions": 400,
                    "region": region,
                    "format": "jpg",
                }
            )

        return _ee_with_backoff(_fetch)
    except Exception as exc:
        logger.error(f"Thumbnail export failed: {exc}")
        return _build_demo_thumbnail_url(lat, lng)


def _build_demo_thumbnail_url(lat: float, lng: float) -> str:
    """Build a public Sentinel Hub WMS URL for demo (no auth needed for low-res)."""
    delta = 0.005
    bbox = f"{lng-delta},{lat-delta},{lng+delta},{lat+delta}"
    return (
        f"https://services.sentinel-hub.com/ogc/wms/demo"
        f"?REQUEST=GetMap&BBOX={bbox}&CRS=EPSG:4326"
        f"&LAYERS=TRUE_COLOR&FORMAT=image/jpeg&WIDTH=400&HEIGHT=400"
    )


def _demo_image_response(lat: float, lng: float) -> Dict[str, Any]:
    """Return a plausible demo response without hitting EE."""
    import hashlib, random
    seed = int(hashlib.md5(f"{lat}{lng}".encode()).hexdigest(), 16) % 100
    ndbi = round((seed - 50) / 200, 3)  # range roughly -0.25 to +0.25
    return {
        "image_url": _build_demo_thumbnail_url(lat, lng),
        "ndbi": ndbi,
        "source": "demo",
        "metadata": {"lat": lat, "lng": lng},
    }
