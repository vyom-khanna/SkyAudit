import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# Set environment variables for GEE (simulating docker environment)
os.environ["GOOGLE_EARTH_ENGINE_KEY"] = "backend/gee-private-key.json"
os.environ["GEE_SERVICE_ACCOUNT_EMAIL"] = "skyaudit-satellite@skyaudit-earth-engine.iam.gserviceaccount.com"

from app.services.satellite import get_sentinel2_image, _init_ee

def main():
    print("Initializing Earth Engine inside the satellite service...")
    initialized = _init_ee()
    print(f"Service GEE Initialization: {initialized}")
    
    if not initialized:
        print("Initialization failed! Cannot test get_sentinel2_image.")
        return

    print("Calling get_sentinel2_image at coordinates (27.57, 80.68) for Jan 2024...")
    try:
        res = get_sentinel2_image(
            lat=27.57,
            lng=80.68,
            date_start="2024-01-01",
            date_end="2024-01-31"
        )
        print("Call completed successfully!")
        print(f"Image URL: {res.get('image_url')}")
        print(f"NDBI Value: {res.get('ndbi')}")
        print(f"Source: {res.get('source')}")
    except Exception as e:
        print(f"Call failed with error: {e}")

if __name__ == "__main__":
    main()
