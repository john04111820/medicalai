import os

print("="*50)
print("  Azure MySQL 資料庫設定助手")
print("="*50)

# 您的資料庫資訊
config = {
    "DB_HOST": "my-sql-db-sever-02.mysql.database.azure.com",
    "DB_USER": "master2",
    "DB_PASSWORD": "A123456789!",
    "DB_NAME": "AIMySQl"
}

# 讀取現有的 .env (為了保留 Gemini Key)
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '.env')
existing_content = ""

if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        existing_content = f.read()

# 準備新的內容
new_lines = []
# 保留原本的 GEMINI_API_KEY
for line in existing_content.splitlines():
    if line.startswith("GEMINI_API_KEY"):
        new_lines.append(line)

# 加入資料庫設定
new_lines.append("")
new_lines.append("# Azure MySQL 設定")
for key, value in config.items():
    new_lines.append(f"{key}={value}")

# 寫回檔案
try:
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(new_lines))
    
    print(f"\n✅ 設定檔更新成功！已寫入 Azure 資料庫資訊。")
    print(f"檔案位置: {env_path}")
    print("-" * 50)
    print("👉 請繼續進行下一步：更新 app.py 以支援 Azure SSL 連線")
    print("-" * 50)

except Exception as e:
    print(f"❌ 寫入檔案失敗: {e}")