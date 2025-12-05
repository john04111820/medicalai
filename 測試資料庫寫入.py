"""
測試資料庫寫入功能
用於診斷預約資料無法寫入資料庫的問題
"""

import os
import sys
from dotenv import load_dotenv
import pymysql
from datetime import datetime, timedelta

# 載入環境變數
basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')
load_dotenv(env_path)

print("=" * 60)
print("資料庫寫入測試工具")
print("=" * 60)

# 讀取配置
db_host = os.getenv('DB_HOST', 'localhost')
db_user = os.getenv('DB_USER', 'root')
db_password = os.getenv('DB_PASSWORD', '')
db_name = os.getenv('DB_NAME', 'medical_db')

print(f"\n資料庫配置：")
print(f"  Host: {db_host}")
print(f"  User: {db_user}")
print(f"  Password: {'*' * len(db_password) if db_password else '(空)'}")
print(f"  Database: {db_name}")

# 測試連接
print("\n[1] 測試資料庫連接...")
try:
    connection = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name,
        charset='utf8mb4'
    )
    print("  ✅ 資料庫連接成功")
except Exception as e:
    print(f"  ❌ 資料庫連接失敗: {e}")
    sys.exit(1)

# 檢查資料表
print("\n[2] 檢查資料表...")
try:
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES LIKE 'medical_appointments'")
        table_exists = cursor.fetchone()
        if not table_exists:
            print("  ❌ 資料表 'medical_appointments' 不存在")
            print("  💡 正在創建資料表...")
            
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS medical_appointments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                patient_name VARCHAR(100) NOT NULL,
                patient_phone VARCHAR(20) NOT NULL,
                department VARCHAR(100) NOT NULL,
                doctor_name VARCHAR(100) NOT NULL,
                appointment_date DATE NOT NULL,
                appointment_time TIME NOT NULL,
                symptoms TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_username (username),
                INDEX idx_appointment_date (appointment_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            cursor.execute(create_table_sql)
            connection.commit()
            print("  ✅ 資料表已創建")
        else:
            print("  ✅ 資料表 'medical_appointments' 存在")
            
        # 檢查表結構
        cursor.execute("DESCRIBE medical_appointments")
        columns = cursor.fetchall()
        print(f"  ✅ 資料表包含 {len(columns)} 個欄位")
        
except Exception as e:
    print(f"  ❌ 檢查資料表時發生錯誤: {e}")
    connection.close()
    sys.exit(1)

# 測試寫入
print("\n[3] 測試資料寫入...")
try:
    with connection.cursor() as cursor:
        # 準備測試資料
        test_data = {
            'username': 'test_user',
            'patient_name': '測試病患',
            'patient_phone': '0912345678',
            'department': '內科',
            'doctor_name': '測試醫師',
            'appointment_date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'appointment_time': '10:00'
        }
        
        sql = """
        INSERT INTO medical_appointments 
        (username, patient_name, patient_phone, department, doctor_name, 
         appointment_date, appointment_time, symptoms, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, 'pending')
        """
        
        print(f"  正在插入測試資料...")
        print(f"    病患: {test_data['patient_name']}")
        print(f"    科別: {test_data['department']}")
        print(f"    日期: {test_data['appointment_date']}")
        print(f"    時間: {test_data['appointment_time']}")
        
        cursor.execute(sql, (
            test_data['username'],
            test_data['patient_name'],
            test_data['patient_phone'],
            test_data['department'],
            test_data['doctor_name'],
            test_data['appointment_date'],
            test_data['appointment_time']
        ))
        
        appointment_id = cursor.lastrowid
        connection.commit()
        
        print(f"  ✅ 資料寫入成功！")
        print(f"  ✅ 插入的記錄 ID: {appointment_id}")
        
        # 驗證資料
        cursor.execute("SELECT * FROM medical_appointments WHERE id = %s", (appointment_id,))
        result = cursor.fetchone()
        if result:
            print(f"  ✅ 資料驗證成功，記錄已存在")
            
            # 清理測試資料
            cursor.execute("DELETE FROM medical_appointments WHERE id = %s", (appointment_id,))
            connection.commit()
            print(f"  ✅ 測試資料已清理")
        else:
            print(f"  ⚠️  警告：資料寫入後無法查詢到")
            
except pymysql.Error as e:
    print(f"  ❌ 資料庫錯誤: {e}")
    print(f"  錯誤代碼: {e.args[0]}")
    print(f"  錯誤訊息: {e.args[1]}")
    connection.rollback()
except Exception as e:
    print(f"  ❌ 發生錯誤: {e}")
    import traceback
    traceback.print_exc()
    connection.rollback()

# 檢查權限
print("\n[4] 檢查資料庫權限...")
try:
    with connection.cursor() as cursor:
        cursor.execute("SHOW GRANTS")
        grants = cursor.fetchall()
        print(f"  ✅ 當前使用者權限：")
        for grant in grants:
            print(f"    {grant[0]}")
except Exception as e:
    print(f"  ⚠️  無法檢查權限: {e}")

connection.close()

print("\n" + "=" * 60)
print("測試完成")
print("=" * 60)
print("\n如果測試失敗，請檢查：")
print("1. MySQL 服務是否正在運行")
print("2. 資料庫使用者是否有 INSERT 權限")
print("3. 資料表結構是否正確")
print("4. 資料庫連接配置是否正確")

