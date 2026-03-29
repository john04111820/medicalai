import requests
import re

BASE_URL = "http://127.0.0.1:5000"

def verify_profile():
    s = requests.Session()
    
    # login
    username = "verify_refactor_user"
    password = "password123"
    
    print(f"Logging in user: {username}")
    res = s.post(f"{BASE_URL}/login", data={
        "username": username,
        "password": password
    })
    
    if "home" not in res.url and "醫療AI聊天助手" not in res.text:
        # Maybe user doesn't exist? Try to register first just in case used in previous session
        print("Login failed, trying register...")
        s.post(f"{BASE_URL}/register", data={
            "username": username,
            "password": password,
            "name": "ProfileTest",
            "phone": "0911222333",
            "identity_id": "A123456789"
        })
        res = s.post(f"{BASE_URL}/login", data={"username": username,"password": password})
    
    # 1. Access Profile
    print("Accessing profile page...")
    res = s.get(f"{BASE_URL}/profile")
    
    if res.status_code != 200:
        print(f"[FAIL] Profile page status code: {res.status_code}")
        return

    # 2. Check Masked ID
    # Expected masking for A123456789 -> A12***789
    expected_mask = "A12***789"
    if expected_mask in res.text:
        print(f"[PASS] Masked ID found: {expected_mask}")
    else:
        print(f"[WARNING] Masked ID not found. Response snippet: {res.text[:200]}...")

    # 3. Test Edit
    print("Testing profile update...")
    import random
    new_name = "ProfileTest Updated"
    new_phone = "0988777666"
    rand_id_suffix = random.randint(100000, 999999)
    new_id = f"A12{rand_id_suffix}"
    
    res = s.post(f"{BASE_URL}/profile", data={
        "name": new_name,
        "phone": new_phone,
        "identity_id": new_id
    })
    
    if "資料更新成功" in res.text:
        print("[PASS] Update successful message found")
    else:
        print("[FAIL] Update message not found")

    # Verify update persistent
    res = s.get(f"{BASE_URL}/profile")
    if new_name in res.text and new_phone in res.text:
        print("[PASS] Updated data persisted")
    else:
        print("[FAIL] Updated data not reflected")
        print(f"DEBUG: Response content:\n{res.text}")

if __name__ == "__main__":
    try:
        verify_profile()
    except Exception as e:
        print(f"Verification error: {e}")
