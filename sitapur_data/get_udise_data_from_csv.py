import csv
import os
import urllib.request
import urllib.parse
import json
import time

# Get path relative to the script location
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_file = os.path.join(script_dir, 'ALLAHABAD_schools.csv')

print(f"Target CSV file: {csv_file}")

def geocode_nominatim(query):
    """Fetch lat/long for a query string using Nominatim OpenStreetMap API."""
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        'q': query,
        'format': 'json',
        'limit': 1
    })
    
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'SkyAudit-Geocoder-Agent/1.0 (contact: support@skyaudit.in)'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            if data:
                return data[0]['lat'], data[0]['lon']
    except Exception as e:
        print(f"API request failed for query '{query}': {e}")
    return None, None

def run_geocoding():
    if not os.path.exists(csv_file):
        print(f"Error: File '{csv_file}' does not exist.")
        return

    # Read existing records
    records = []
    fieldnames = []
    with open(csv_file, mode='r', encoding='utf-8', errors='ignore') as infile:
        reader = csv.DictReader(infile)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        for row in reader:
            records.append(row)

    if not fieldnames:
        print("Error: No headers found in the CSV.")
        return

    # Ensure latitude and longitude columns exist in header
    if 'latitude' not in fieldnames:
        fieldnames.append('latitude')
    if 'longitude' not in fieldnames:
        fieldnames.append('longitude')

    # Mapping of potential columns
    udise_col = next((f for f in fieldnames if f.strip().lower() in ('udise code', 'udise_code')), 'UDISE Code')
    name_col = next((f for f in fieldnames if f.strip().lower() in ('school name', 'school_name', 'name')), 'School Name')
    district_col = next((f for f in fieldnames if f.strip().lower() == 'district'), 'District')
    block_col = next((f for f in fieldnames if f.strip().lower() == 'block'), 'Block')
    state_col = next((f for f in fieldnames if f.strip().lower() == 'state'), 'State')
    pin_col = next((f for f in fieldnames if f.strip().lower() in ('pin code', 'pincode', 'pin_code')), 'PIN Code')

    print(f"Starting geocoding process for {len(records)} records...")
    print("This script will save progress incrementally after every successfully geocoded school.")
    print("Press Ctrl+C to pause the script at any time; your progress will be saved.")

    success_count = 0
    skipped_count = 0
    failed_count = 0

    try:
        for index, row in enumerate(records):
            # Check if lat/long are already present and valid
            existing_lat = row.get('latitude')
            existing_lng = row.get('longitude')
            
            def is_valid(val):
                if not val: return False
                try:
                    f = float(val)
                    return f != 0.0
                except ValueError:
                    return False

            if is_valid(existing_lat) and is_valid(existing_lng):
                skipped_count += 1
                continue

            school_name = row.get(name_col, '').strip()
            block = row.get(block_col, '').strip()
            district = row.get(district_col, '').strip()
            state = row.get(state_col, '').strip()
            pincode = row.get(pin_col, '').strip()

            if not school_name:
                continue

            # Build queries (Primary and Fallbacks)
            queries = [
                f"{school_name}, {block}, {district}, {state}, {pincode}, India",
                f"{school_name}, {district}, {state}, India",
                f"{school_name}, {block}, {district}, India"
            ]

            lat, lng = None, None
            for q in queries:
                print(f"[{index+1}/{len(records)}] Geocoding: {q}")
                lat, lng = geocode_nominatim(q)
                
                # Respect Nominatim API rate limit (max 1 request/second)
                time.sleep(1.0)
                
                if lat and lng:
                    break

            if lat and lng:
                row['latitude'] = lat
                row['longitude'] = lng
                success_count += 1
                print(f"-> SUCCESS: lat={lat}, lng={lng}")
                
                # Save incrementally after every success
                with open(csv_file, mode='w', encoding='utf-8', newline='') as outfile:
                    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(records)
            else:
                failed_count += 1
                print("-> FAILED to locate school.")

            # Log status periodically
            if (success_count + failed_count) % 10 == 0:
                print(f"--- Status: {success_count} geocoded, {skipped_count} skipped, {failed_count} failed ---")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Saving final progress...")

    finally:
        # Save final state
        with open(csv_file, mode='w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        
        print("\n--- Final Summary ---")
        print(f"Successfully Geocoded: {success_count}")
        print(f"Skipped (already exist): {skipped_count}")
        print(f"Failed to find: {failed_count}")
        print(f"CSV file updated at: {csv_file}")

if __name__ == "__main__":
    run_geocoding()