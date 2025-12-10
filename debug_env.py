import os
from dotenv import load_dotenv

# 1. 找出 app.py 所在的真正路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '.env')

print("="*50)
print(f"程式執行目錄: {os.getcwd()}")
print(f"預期 .env 路徑: {env_path}")
print("="*50)

# 2. 檢查檔案是否存在
if os.path.exists(env_path):
    print("✅ 找到 .env 檔案了！")
    
    # 3. 嘗試讀取內容 (不印出完整金鑰，只印前幾碼)
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        print("檔案內容預覽:")
        print(content[:15] + "...")
        
    # 4. 載入環境變數
    load_dotenv(env_path)
    api_key = os.getenv("GEMINI_API_KEY")
    
    if api_key:
        print(f"\n✅ 環境變數載入成功！Key 前綴: {api_key[:5]}")
    else:
        print("\n❌ 檔案存在，但讀取不到 GEMINI_API_KEY。請檢查 .env 內容格式。")
        print("正確格式應為: GEMINI_API_KEY=你的金鑰")
else:
    print("❌ 找不到 .env 檔案！")
    print("請確認：")
    print("1. 檔案名稱是否剛好是 '.env' (前面有點，後面沒有 txt)")
    print("2. 檔案是否跟 app.py 在同一個資料夾")
    
    # 列出目前資料夾的所有檔案
    print("\n目前資料夾內的檔案:")
    for f in os.listdir(current_dir):
        print(f" - {f}")

print("="*50)