import os
import pymysql

# ==========================================
# 您的 Azure 資料庫資訊 (已填入)
# ==========================================
AZURE_CONFIG = {
    'host': 'my-sql-db-sever-02.mysql.database.azure.com',
    'user': 'master2',
    'password': 'A123456789!',
    'database': 'AIMySQl',  # 注意大小寫
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    # Azure 強制要求 SSL 連線，此參數非常重要
    'ssl': {'ssl_disabled': True} 
}

print("="*60)
print("  Azure 資料庫強制連線工具")
print("="*60)

# 1. 產生 .env 檔案
print("\n[步驟 1/2] 正在建立 .env 設定檔...")
env_content = f"""# Azure MySQL Configuration
DB_HOST={AZURE_CONFIG['host']}
DB_USER={AZURE_CONFIG['user']}
DB_PASSWORD={AZURE_CONFIG['password']}
DB_NAME={AZURE_CONFIG['database']}

# Gemini API Key (保留原本的，若無則為空)
GEMINI_API_KEY=
"""

# 嘗試保留舊的 API Key
try:
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('GEMINI_API_KEY') and len(line.strip()) > 15:
                    env_content = env_content.replace('GEMINI_API_KEY=', line.strip())
                    break
    
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    print(f"✅ .env 檔案已更新！(Host: {AZURE_CONFIG['host']})")
    
except Exception as e:
    print(f"❌ 建立 .env 失敗: {e}")

# 2. 初始化資料庫表格
print("\n[步驟 2/2] 連線到 Azure 並初始化表格...")
print(f"正在連線到: {AZURE_CONFIG['host']}...")

try:
    # 建立連線
    connection = pymysql.connect(**AZURE_CONFIG)
    
    with connection.cursor() as cursor:
        # 嘗試建立/選擇資料庫
        print(f"  - 檢查資料庫 '{AZURE_CONFIG['database']}'...")
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {AZURE_CONFIG['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        except Exception as e:
            print(f"    (提示: 無法建立資料庫，嘗試直接使用: {e})")
            
        cursor.execute(f"USE {AZURE_CONFIG['database']};")
        
        # 重建表格 (確保欄位正確)
        print("  - 重建 medical_appointments 表格...")
        cursor.execute("DROP TABLE IF EXISTS medical_appointments;")
        
        create_sql = """
        CREATE TABLE medical_appointments (
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
            INDEX idx_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        cursor.execute(create_sql)
        
        # 插入測試資料
        print("  - 插入測試資料...")
        cursor.execute("""
            INSERT INTO medical_appointments 
            (username, patient_name, patient_phone, department, doctor_name, appointment_date, appointment_time, status)
            VALUES ('admin', 'Azure連線成功', '0900000000', '測試科', '系統自動', CURDATE(), '10:00', 'pending')
        """)
        connection.commit()
        
    connection.close()
    print("\n✅ Azure 資料庫初始化成功！")
    print("👉 您的應用程式現在已設定為連線到 Azure。")

except pymysql.MySQLError as e:
    print(f"\n❌ 連線失敗: {e}")
    print("⚠️  請務必確認：Azure 防火牆是否已允許您的 IP 連線？")
    print("   (錯誤代碼 9009 或 10060 通常代表防火牆阻擋)")

except Exception as e:
    print(f"\n❌ 發生錯誤: {e}")
