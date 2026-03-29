"""
SQLite 資料庫初始化腳本
創建符合預約表單格式的 SQLite 資料庫
"""
import sqlite3
import os
from datetime import datetime

# 資料庫檔案路徑
DB_FILE = 'medical_appointments.db'

print("=" * 60)
print("SQLite 資料庫初始化")
print("=" * 60)

# 如果資料庫已存在，先備份
if os.path.exists(DB_FILE):
    backup_file = f"{DB_FILE}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n[注意] 資料庫檔案已存在，正在備份為: {backup_file}")
    import shutil
    shutil.copy2(DB_FILE, backup_file)

# 連接資料庫（如果不存在會自動創建）
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

print(f"\n[1] 連接資料庫: {DB_FILE}")

# 創建資料表
create_table_sql = """
CREATE TABLE IF NOT EXISTS medical_appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(100) NOT NULL,
    patient_id VARCHAR(50),
    patient_name VARCHAR(100) NOT NULL,
    patient_phone VARCHAR(20) NOT NULL,
    department VARCHAR(100) NOT NULL,
    doctor_name VARCHAR(100) NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    symptoms TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

create_users_table_sql = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    identity_id VARCHAR(20) NOT NULL UNIQUE,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

try:
    cursor.execute(create_table_sql)
    print("[成功] 資料表 'medical_appointments' 已創建")

    cursor.execute(create_users_table_sql)
    print("[成功] 資料表 'users' 已創建")
    
    # 創建索引以提高查詢效能
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON medical_appointments(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointment_date ON medical_appointments(appointment_date)")
    print("[成功] 索引已創建")
    
    # 提交變更
    conn.commit()
    
    # 驗證表結構
    cursor.execute("PRAGMA table_info(medical_appointments)")
    columns = cursor.fetchall()
    print(f"\n[2] 資料表結構驗證:")
    print(f"    共 {len(columns)} 個欄位:")
    for col in columns:
        print(f"      - {col[1]} ({col[2]})")
    
    # 測試插入一筆測試資料
    print("\n[3] 測試資料插入...")
    test_data = (
        'test_user',
        'P12345',
        '測試病患',
        '0912345678',
        '內科',
        '測試醫師',
        '2025-12-10',
        '10:00',
        '測試症狀描述',
        'pending'
    )
    
    insert_sql = """
    INSERT INTO medical_appointments 
    (username, patient_id, patient_name, patient_phone, department, doctor_name, 
     appointment_date, appointment_time, symptoms, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    cursor.execute(insert_sql, test_data)
    test_id = cursor.lastrowid
    conn.commit()
    print(f"[成功] 測試資料已插入 (ID: {test_id})")
    
    # 驗證資料
    cursor.execute("SELECT * FROM medical_appointments WHERE id = ?", (test_id,))
    result = cursor.fetchone()
    if result:
        print(f"[成功] 資料驗證成功")
        print(f"      病患: {result[2]}, 科別: {result[4]}, 日期: {result[6]}")
    
    # 刪除測試資料
    cursor.execute("DELETE FROM medical_appointments WHERE id = ?", (test_id,))
    conn.commit()
    print(f"[成功] 測試資料已清除")
    
    print("\n" + "=" * 60)
    print("[完成] SQLite 資料庫初始化成功！")
    print(f"資料庫檔案位置: {os.path.abspath(DB_FILE)}")
    print("=" * 60)
    
except Exception as e:
    print(f"\n[錯誤] 初始化失敗: {e}")
    conn.rollback()
finally:
    conn.close()

