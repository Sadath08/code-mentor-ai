import requests
import json

BASE_URL = "http://localhost:8000"
USER_EMAIL = "arjun@example.com"
USER_PWD = "password123"

def test_login():
    print(f"Testing login for {USER_EMAIL}...")
    try:
        resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": USER_EMAIL, "password": USER_PWD}
        )
        if resp.status_code == 200:
            data = resp.json()
            user_id = data["user"]["id"]
            print(f"✅ Login successful! User ID: {user_id}")
            return user_id, data["access_token"]
        else:
            print(f"❌ Login failed: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ Error during login test: {e}")
    return None, None

def test_analytics(user_id):
    print(f"Testing analytics for {user_id}...")
    try:
        resp = requests.get(f"{BASE_URL}/api/analytics/dashboard/{user_id}")
        if resp.status_code == 200:
            data = resp.json()
            print("✅ Analytics retrieved successfully.")
            print(f"Top Errors: {[p['concept'] for p in data.get('error_patterns', [])]}")
        else:
            print(f"❌ Analytics failed: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"❌ Error during analytics test: {e}")

if __name__ == "__main__":
    uid, token = test_login()
    if uid:
        test_analytics(uid)
