from flask import Flask, render_template_string, request, redirect, url_for, session, render_template, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import whisper
import os
import tempfile
import google.generativeai as genai
from dotenv import load_dotenv

# === 1. 強制載入 .env ===
basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')
load_dotenv(env_path)

app = Flask(__name__)
app.secret_key = "supersecretkey"

# === 2. 初始化 Gemini 模型 (更新版：支援 Gemini 2.0) ===
gemini_model = None
gemini_api_key = os.getenv("GEMINI_API_KEY")

print("=" * 50)
if gemini_api_key:
    print(f"✅ 讀取到 API Key (前綴: {gemini_api_key[:5]}...)")
    try:
        genai.configure(api_key=gemini_api_key)
        
        # === 關鍵修改：更新模型清單，優先使用您帳號支援的 2.0/2.5 版本 ===
        models_to_try = [
            'gemini-2.0-flash',          # 首選：最新且快速
            'gemini-2.5-flash',          # 次選：更新的版本
            'gemini-2.0-flash-exp',      # 備用：實驗版
            'gemini-1.5-flash',          # 舊版
            'gemini-pro'                 # 最舊版
        ]
        
        for model_name in models_to_try:
            print(f"正在測試模型: {model_name} ...", end=" ")
            try:
                temp_model = genai.GenerativeModel(model_name)
                # 發送測試請求
                response = temp_model.generate_content("Hello")
                if response:
                    gemini_model = temp_model
                    print(f"成功！使用此模型: {model_name}")
                    break
            except Exception as e:
                print("失敗。")
                # print(f"   -> 錯誤原因: {e}") # 暫時隱藏詳細錯誤保持版面乾淨
        
        if not gemini_model:
            print("\n❌ 所有模型測試均失敗。嘗試使用最後手段：自動搜尋...")
            # 如果上面的清單都失敗，嘗試從您的可用列表中抓取第一個 'flash' 模型
            try:
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        if 'flash' in m.name:
                            print(f"嘗試系統偵測到的模型: {m.name} ...")
                            gemini_model = genai.GenerativeModel(m.name)
                            print("成功！")
                            break
            except:
                pass

        if not gemini_model:
             print("❌ 嚴重錯誤：無法初始化任何 AI 模型。")

    except Exception as e:
        print(f"❌ Gemini 設定發生嚴重錯誤: {e}")
else:
    print("❌ 嚴重錯誤：找不到 GEMINI_API_KEY 環境變數！")
print("=" * 50)


# === 3. Whisper 設定 ===
whisper_model = None
def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        print("正在載入 Whisper 模型...")
        whisper_model = whisper.load_model("base")
        print("Whisper 模型載入完成")
    return whisper_model

users = {"admin": generate_password_hash("1234")}

# === 路由 ===
@app.route("/")
def index():
    return render_template("index.html", username=session.get("user"))

@app.route("/login", methods=["GET", "POST"])
def login():
    login_html = """<!DOCTYPE html><html><head><title>登入</title></head><body style="font-family: Arial; background:#eef1f7; display:flex; justify-content:center; align-items:center; height:100vh;"><div style="background:white; padding:30px; border-radius:10px; width:300px; text-align:center;"><h2>登入</h2><form method="POST" action="/login"><input type="text" name="username" placeholder="帳號" required style="width:100%; padding:10px; margin:8px 0;"><br><input type="password" name="password" placeholder="密碼" required style="width:100%; padding:10px; margin:8px 0;"><br><button type="submit" style="width:100%; padding:10px; background:#5563DE; color:white; border:none; border-radius:5px; cursor:pointer;">登入</button></form><p style="color:red;">{{ message }}</p><a href="/register" style="color:#5563DE; text-decoration:none;">註冊新帳號</a> | <a href="/" style="color:#888; text-decoration:none;">暫不登入 (回首頁)</a></div></body></html>"""
    msg = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users and check_password_hash(users[username], password):
            session["user"] = username
            return redirect(url_for("index"))
        msg = "帳號或密碼錯誤"
    return render_template_string(login_html, message=msg)

@app.route("/register", methods=["GET","POST"])
def register():
    register_html = """<!DOCTYPE html><html><head><title>註冊</title></head><body style="font-family: Arial; background:#eef1f7; display:flex; justify-content:center; align-items:center; height:100vh;"><div style="background:white; padding:30px; border-radius:10px; width:300px; text-align:center;"><h2>註冊</h2><form method="POST"><input type="text" name="username" placeholder="帳號" required style="width:100%; padding:10px; margin:8px 0;"><br><input type="password" name="password" placeholder="密碼" required style="width:100%; padding:10px; margin:8px 0;"><br><button type="submit" style="width:100%; padding:10px; background:#5563DE; color:white; border:none; border-radius:5px; cursor:pointer;">註冊</button></form><p style="color:red;">{{ message }}</p><a href="/login" style="color:#5563DE; text-decoration:none;">返回登入</a></div></body></html>"""
    msg = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users:
            msg = "帳號已存在"
        else:
            users[username] = generate_password_hash(password)
            msg = "註冊成功！請登入"
    return render_template_string(register_html, message=msg)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

@app.route("/api/transcribe", methods=["POST"])
def transcribe_audio():
    try:
        if "audio" not in request.files: return jsonify({"error": "No audio file"}), 400
        audio_file = request.files["audio"]
        if audio_file.filename == "": return jsonify({"error": "Empty filename"}), 400
        
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"whisper_{os.urandom(4).hex()}.webm")
        audio_file.save(temp_path)
        
        try:
            model = get_whisper_model()
            result = model.transcribe(temp_path, language="zh", fp16=False)
            text = result["text"].strip()
            print(f"Whisper 聽到: {text}")
            
            # 自動觸發 Gemini 回應 (可選)
            ai_reply = ""
            if gemini_model and text:
                try:
                    response = gemini_model.generate_content(text)
                    ai_reply = response.text.strip()
                except:
                    pass

            return jsonify({"success": True, "text": text, "ai_response": ai_reply})
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
def chat():
    # === 確保 global 宣告在函式最開頭 ===
    global gemini_model
    
    if not gemini_model:
        return jsonify({"success": False, "error": "AI 模型初始化失敗，請檢查後端伺服器的詳細錯誤日誌。"}), 500
    
    data = request.get_json()
    msg = data.get("message", "").strip()
    if not msg: return jsonify({"success": False, "error": "Empty message"}), 400
    
    print(f"傳送給 AI: {msg}")
    try:
        response = gemini_model.generate_content(msg)
        reply = response.text.strip()
        print(f"AI 回應: {reply}")
        return jsonify({"success": True, "message": reply})
    except Exception as e:
        print(f"AI 錯誤: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/clear-history", methods=["POST"])
def clear_history():
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)