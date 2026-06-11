import ee
import requests
from google.oauth2 import service_account


SERVICE_ACCOUNT = "skyaudit-satellite@skyaudit-earth-engine.iam.gserviceaccount.com"
KEY_FILE = "backend/gee-private-key.json"

credentials = ee.ServiceAccountCredentials(
    SERVICE_ACCOUNT,
    KEY_FILE
)

ee.Initialize(credentials)

point = ee.Geometry.Point([77.59, 28.67])

img = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(point)
    .filterDate("2025-01-01", "2025-01-31")
    .sort("CLOUDY_PIXEL_PERCENTAGE")
    .first()
)

url = img.getThumbURL({
    "region": point.buffer(5000).bounds(),
    "dimensions": 512,
    "bands": ["B4", "B3", "B2"],
    "min": 0,
    "max": 3000
})

print(url)