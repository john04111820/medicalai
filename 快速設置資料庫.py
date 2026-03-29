"""
快速設置資料庫配置工具
"""

import os

print("=" * 60)
print("資料庫配置快速設置")
print("=" * 60)

# 檢查是否已有 .env 文件
env_file = '.env'
if os.path.exists(env_file):
    print("\n⚠️  發現現有的 .env 文件")
    choice = input("是否要更新資料庫配置？(y/n): ").strip().lower()
    if choice != 'y':
        print("已取消操作")
        exit()

print("\n請輸入您的 MySQL 資料庫配置：")
print("(直接按 Enter 使用預設值)")

db_host = input("\nMySQL 主機地址 [預設: localhost]: ").strip() or "localhost"
db_user = input("MySQL 使用者名稱 [預設: root]: ").strip() or "root"
db_password = input("MySQL 密碼: ").strip()
db_name = input("資料庫名稱 [預設: medical_db]: ").strip() or "medical_db"

# 讀取現有的 GEMINI_API_KEY（如果存在）
gemini_key = ""
if os.path.exists(env_file):
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('GEMINI_API_KEY='):
                    gemini_key = line.split('=', 1)[1].strip()
                    break
    except:
        pass

# 寫入 .env 文件
try:
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write("# MySQL 資料庫配置\n")
        f.write(f"DB_HOST={db_host}\n")
        f.write(f"DB_USER={db_user}\n")
        f.write(f"DB_PASSWORD={db_password}\n")
        f.write(f"DB_NAME={db_name}\n")
        if gemini_key:
            f.write(f"\n# Gemini API Key\n")
            f.write(f"GEMINI_API_KEY={gemini_key}\n")
    
    print("\n" + "=" * 60)
    print("✅ 配置已保存到 .env 文件")
    print("=" * 60)
    print(f"\n配置內容：")
    print(f"  DB_HOST={db_host}")
    print(f"  DB_USER={db_user}")
    print(f"  DB_PASSWORD={'*' * len(db_password) if db_password else '(空)'}")
    print(f"  DB_NAME={db_name}")
    
    print("\n下一步：")
    print("1. 確認 MySQL 服務正在運行")
    print("2. 確認資料庫已創建（如果不存在，請執行以下 SQL）：")
    print(f"   CREATE DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    print("3. 執行 'python 檢查預約功能.py' 來測試連接")
    print("4. 啟動應用程式：python app.py")
    
except Exception as e:
    print(f"\n❌ 寫入文件失敗: {e}")

