import requests
import json

BASE_URL = "http://localhost:8000"

def main():
    print("Logging in as demo officer...")
    login_res = requests.post(f"{BASE_URL}/auth/login", data={
        "username": "demo@skyaudit.in",
        "password": "demo1234"
    })
    
    if login_res.status_code != 200:
        print(f"Login failed: {login_res.status_code} - {login_res.text}")
        return
        
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful! Token acquired.")

    # Let's find a ghost school UDISE code by querying backend anomalies
    print("Fetching anomalies list...")
    anomalies_res = requests.get(f"{BASE_URL}/anomalies/", headers=headers, params={"limit": 10})
    if anomalies_res.status_code != 200:
        print(f"Failed to fetch anomalies: {anomalies_res.text}")
        return
        
    anomalies = anomalies_res.json()
    ghost_schools = [a for a in anomalies if a["anomaly_type"] == "ghost_school"]
    
    if not ghost_schools:
        print("No ghost schools found in the database. Using fallback school '09140010001'")
        udise_code = "09140010001"
    else:
        udise_code = ghost_schools[0]["udise_code"]
        print(f"Found ghost school with UDISE: {udise_code}")

    print(f"Triggering manual verification for UDISE {udise_code}...")
    verify_res = requests.post(f"{BASE_URL}/schools/{udise_code}/verify", headers=headers)
    
    print(f"Response Status: {verify_res.status_code}")
    print(f"Response Body: {json.dumps(verify_res.json(), indent=2)}")

if __name__ == "__main__":
    main()
