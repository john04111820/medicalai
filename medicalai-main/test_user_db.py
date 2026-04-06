import sqlite3
import os
from werkzeug.security import check_password_hash

DB_FILE = 'medical_appointments.db'

def test_user_db():
    print(f"Testing database: {DB_FILE}")
    if not os.path.exists(DB_FILE):
        print("Database file not found!")
        return

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Check if users table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        print("[FAIL] users table does not exist")
        return
    print("[PASS] users table exists")

    # 2. Insert test user
    test_user = {
        'name': 'Test User',
        'phone': '0912345678',
        'identity_id': 'A123456789',
        'username': 'testuser',
        'password': 'password123'
    }
    
    # Clean up first
    cursor.execute("DELETE FROM users WHERE username = ?", (test_user['username'],))
    conn.commit()

    try:
        from werkzeug.security import generate_password_hash
        hashed = generate_password_hash(test_user['password'])
        
        cursor.execute("""
            INSERT INTO users (name, phone, identity_id, username, password_hash)
            VALUES (?, ?, ?, ?, ?)
        """, (test_user['name'], test_user['phone'], test_user['identity_id'], test_user['username'], hashed))
        conn.commit()
        print("[PASS] Inserted test user")
        
        # 3. Verify inserted data
        row = cursor.execute("SELECT * FROM users WHERE username = ?", (test_user['username'],)).fetchone()
        if row:
            print(f"[PASS] User found in DB: ID={row['id']}, Name={row['name']}")
            if row['name'] == test_user['name'] and row['phone'] == test_user['phone'] and row['identity_id'] == test_user['identity_id']:
                print("[PASS] User data fields match")
            else:
                 print(f"[FAIL] Data mismatch: {dict(row)}")
            
            if check_password_hash(row['password_hash'], test_user['password']):
                 print("[PASS] Password hash verified")
            else:
                 print("[FAIL] Password hash check failed")

        else:
            print("[FAIL] Could not find inserted user")

    except Exception as e:
        print(f"[FAIL] Error inserting/verifying user: {e}")
    finally:
        # Clean up
        cursor.execute("DELETE FROM users WHERE username = ?", (test_user['username'],))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    test_user_db()
