"""
預約功能診斷和修復工具
"""

import os
import sys

print("=" * 60)
print("預約功能診斷工具")
print("=" * 60)

# 檢查 .env 文件
print("\n[1] 檢查環境變數配置...")
env_file = '.env'
if not os.path.exists(env_file):
    print("  ❌ .env 文件不存在")
    print("  📝 這可能是預約功能無法使用的主要原因")
    print("\n💡 請執行 'python 快速設置資料庫.py' 來設置資料庫配置")
    print("   或手動創建 .env 文件並添加資料庫配置")
    sys.exit(1)
else:
    print("  ✅ .env 文件存在")
    # 檢查配置
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        db_host = os.getenv('DB_HOST', 'localhost')
        db_user = os.getenv('DB_USER', 'root')
        db_password = os.getenv('DB_PASSWORD', '')
        db_name = os.getenv('DB_NAME', 'medical_db')
        
        print(f"  DB_HOST: {db_host}")
        print(f"  DB_USER: {db_user}")
        print(f"  DB_PASSWORD: {'*' * len(db_password) if db_password else '(空)'}")
        print(f"  DB_NAME: {db_name}")
    except ImportError:
        print("  ❌ python-dotenv 未安裝，請執行: pip install python-dotenv")
        sys.exit(1)

# 測試資料庫連接
print("\n[2] 測試資料庫連接...")
try:
    import pymysql
    
    connection = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name,
        charset='utf8mb4'
    )
    print("  ✅ 資料庫連接成功")
    
    # 檢查資料表
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES LIKE 'medical_appointments'")
        table_exists = cursor.fetchone()
        if table_exists:
            print("  ✅ 資料表 'medical_appointments' 存在")
        else:
            print("  ⚠️  資料表 'medical_appointments' 不存在")
            print("  💡 應用程式啟動時會自動創建")
    
    connection.close()
    
except ImportError:
    print("  ❌ pymysql 未安裝")
    print("  💡 請執行: pip install pymysql")
    sys.exit(1)
except pymysql.Error as e:
    print(f"  ❌ 資料庫連接失敗: {e}")
    print("\n可能的解決方法：")
    print("  1. 確認 MySQL 服務正在運行")
    print("  2. 確認資料庫已創建：")
    print(f"     CREATE DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    print("  3. 確認使用者名稱和密碼正確")
    print("  4. 確認使用者有足夠權限")
except Exception as e:
    print(f"  ❌ 發生錯誤: {e}")

# 檢查 Flask 應用
print("\n[3] 檢查 Flask 應用程式...")
try:
    from app import app
    print("  ✅ Flask 應用程式載入成功")
except Exception as e:
    print(f"  ❌ Flask 應用程式載入失敗: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("診斷完成")
print("=" * 60)
print("\n下一步：")
print("1. 如果資料庫連接成功，請啟動應用程式：python app.py")
print("2. 在瀏覽器中訪問 http://localhost:5000")
print("3. 登入後嘗試使用預約功能")
print("4. 如果仍有問題，請查看應用程式的錯誤日誌")

