import requests
import re

BASE_URL = "http://127.0.0.1:5000"

def verify_refactor():
    s = requests.Session()
    
    # 1. Register a new user
    username = "verify_refactor_user"
    password = "password123"
    name = "Refactor Test Name"
    phone = "0999888777"
    identity_id = "R123456789"
    
    print(f"Registering user: {username}")
    res = s.post(f"{BASE_URL}/register", data={
        "username": username,
        "password": password,
        "name": name,
        "phone": phone,
        "identity_id": identity_id
    })
    
    if "註冊成功" not in res.text and "已存在" not in res.text:
        print("[FAIL] Registration failed")
        # try login anyway in case it existed
    
    # 2. Login
    print(f"Logging in user: {username}")
    res = s.post(f"{BASE_URL}/login", data={
        "username": username,
        "password": password
    })
    
    if "醫療AI聊天助手" not in res.text and "home" not in res.url:
        print("[FAIL] Login failed")
        return

    # 3. Get Appointment Page
    print("Fetching appointment page...")
    res = s.get(f"{BASE_URL}/appointment")
    
    # 4. Check for auto-filled data
    # We look for value="Refactor Test Name" and readonly
    if f'value="{name}"' in res.text:
        print("[PASS] User name is auto-filled")
    else:
        print("[FAIL] User name NOT found in appointment page")
        
    if f'value="{phone}"' in res.text:
        print("[PASS] User phone is auto-filled")
    else:
        print("[FAIL] User phone NOT found in appointment page")
        
    if 'readonly' in res.text and 'cursor: not-allowed' in res.text:
        print("[PASS] Fields seem to be readonly")
    else:
        print("[WARNING] Readonly attribute might be missing")

if __name__ == "__main__":
    try:
        verify_refactor()
    except Exception as e:
        print(f"Verification failed with connection error (server might be reloading or down): {e}")
