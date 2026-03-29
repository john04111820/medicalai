"""測試 SQLite 資料庫連接"""
import sqlite3
import os

DB_FILE = 'medical_appointments.db'

print("=" * 60)
print("測試 SQLite 資料庫連接")
print("=" * 60)

if not os.path.exists(DB_FILE):
    print(f"[錯誤] 資料庫檔案不存在: {DB_FILE}")
    print("請先執行 init_sqlite_db.py 初始化資料庫")
    exit(1)

try:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print(f"[成功] 已連接到資料庫: {DB_FILE}")
    
    # 檢查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='medical_appointments'")
    table = cursor.fetchone()
    
    if table:
        print("[成功] 資料表 'medical_appointments' 存在")
        
        # 查看表結構
        cursor.execute("PRAGMA table_info(medical_appointments)")
        columns = cursor.fetchall()
        print(f"\n資料表結構 ({len(columns)} 個欄位):")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # 查看記錄數
        cursor.execute("SELECT COUNT(*) as count FROM medical_appointments")
        count = cursor.fetchone()['count']
        print(f"\n現有記錄數: {count}")
        
        if count > 0:
            # 顯示最新 3 筆記錄
            cursor.execute("SELECT * FROM medical_appointments ORDER BY id DESC LIMIT 3")
            records = cursor.fetchall()
            print("\n最新 3 筆記錄:")
            for record in records:
                print(f"  ID: {record['id']}, 病患: {record['patient_name']}, "
                      f"科別: {record['department']}, 日期: {record['appointment_date']}")
    else:
        print("[錯誤] 資料表 'medical_appointments' 不存在")
        print("請執行 init_sqlite_db.py 初始化資料庫")
    
    conn.close()
    print("\n[完成] 測試成功！")
    
except Exception as e:
    print(f"\n[錯誤] 測試失敗: {e}")

