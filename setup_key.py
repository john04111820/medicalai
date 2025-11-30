import os

print("="*50)
print("  Gemini API 金鑰設定助手")
print("="*50)

# 1. 詢問金鑰
print("\n請貼上您的 Google Gemini API Key (以 AIza 開頭):")
key = input("> ").strip()

if not key:
    print("❌ 錯誤：未輸入金鑰，程式結束。")
    exit()

if not key.startswith("AIza"):
    print("⚠️ 警告：這看起來不像有效的 Gemini Key (通常以 AIza 開頭)")
    confirm = input("確定要繼續嗎？(y/n): ")
    if confirm.lower() != 'y':
        exit()

# 2. 寫入 .env 檔案
# 確保寫入到與此腳本相同的目錄
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '.env')

try:
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(f"GEMINI_API_KEY={key}")
    
    print(f"\n✅ 成功建立設定檔！")
    print(f"檔案位置: {env_path}")
    print(f"寫入內容: GEMINI_API_KEY={key[:5]}...")
    print("-" * 50)
    print("👉 現在請重新執行 python app.py，問題應該已解決！")
    print("-" * 50)

except Exception as e:
    print(f"❌ 寫入檔案失敗: {e}")