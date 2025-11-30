from flask import Flask, render_template_string, request, redirect, url_for, session, render_template, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import whisper
import os
import tempfile
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = "supersecretkey"

# 初始化 Google Gemini API 客戶端
# 從環境變數讀取 API Key，Gemini 提供免費額度
gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    gemini_model = genai.GenerativeModel('gemini-pro')
    print("Google Gemini API 客戶端已初始化")
else:
    gemini_model = None
    print("警告: 未設置 GEMINI_API_KEY 環境變數，Gemini 功能將無法使用")

# 初始化 Whisper 模型（使用 base 模型，平衡速度和準確度）
# 首次運行時會自動下載模型
print("正在載入 Whisper 模型...")
whisper_model = whisper.load_model("base")
print("Whisper 模型載入完成！")

# 模擬使用者資料庫
users = {"admin": generate_password_hash("1234")}

# 對話歷史管理（使用 session 存儲）
def get_conversation_history():
    """獲取當前用戶的對話歷史"""
    if "conversation" not in session:
        session["conversation"] = []
    return session["conversation"]

def add_to_conversation(role, content):
    """添加消息到對話歷史"""
    conversation = get_conversation_history()
    conversation.append({"role": role, "content": content})
    # 限制對話歷史長度（保留最近 20 條消息）
    if len(conversation) > 20:
        conversation = conversation[-20:]
    session["conversation"] = conversation

# --- HTML 模板 (微調了連結路徑) ---

# 1. 登入頁面 HTML
login_html = """
<!DOCTYPE html>
<html>
<head><title>登入</title></head>
<body style="font-family: Arial; background:#eef1f7; display:flex; justify-content:center; align-items:center; height:100vh;">
<div style="background:white; padding:30px; border-radius:10px; width:300px; text-align:center;">
<h2>登入</h2>
<form method="POST" action="/login">
    <input type="text" name="username" placeholder="帳號" required style="width:100%; padding:10px; margin:8px 0;"><br>
    <input type="password" name="password" placeholder="密碼" required style="width:100%; padding:10px; margin:8px 0;"><br>
    <button type="submit" style="width:100%; padding:10px; background:#5563DE; color:white; border:none; border-radius:5px; cursor:pointer;">登入</button>
</form>
<p style="color:red;">{{ message }}</p>
<a href="/register" style="color:#5563DE; text-decoration:none;">註冊新帳號</a> | 
<a href="/" style="color:#888; text-decoration:none;">暫不登入 (回首頁)</a>
</div></body></html>
"""

# 2. 註冊頁面 HTML
register_html = """
<!DOCTYPE html>
<html>
<head><title>註冊</title></head>
<body style="font-family: Arial; background:#eef1f7; display:flex; justify-content:center; align-items:center; height:100vh;">
<div style="background:white; padding:30px; border-radius:10px; width:300px; text-align:center;">
<h2>註冊</h2>
<form method="POST">
    <input type="text" name="username" placeholder="帳號" required style="width:100%; padding:10px; margin:8px 0;"><br>
    <input type="password" name="password" placeholder="密碼" required style="width:100%; padding:10px; margin:8px 0;"><br>
    <button type="submit" style="width:100%; padding:10px; background:#5563DE; color:white; border:none; border-radius:5px; cursor:pointer;">註冊</button>
</form>
<p style="color:red;">{{ message }}</p>
<a href="/login" style="color:#5563DE; text-decoration:none;">返回登入</a>
</div></body></html>
"""

# --- 路由設定 ---

# 1. 首頁路由：現在直接顯示「語音助理介面」
@app.route("/")
def index():
    # session.get("user") 會嘗試抓取使用者名稱
    # 如果沒登入，它會回傳 None，HTML 那邊的 {% if %} 就會判斷正確
    return render_template("index.html", username=session.get("user"))

# 2. 登入路由：同時處理「顯示頁面 (GET)」和「處理登入 (POST)」
@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    # 如果是按下登入按鈕 (POST)
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        if username in users and check_password_hash(users[username], password):
            session["user"] = username
            # 登入成功後，導回首頁 (index)
            return redirect(url_for("index"))
        
        msg = "帳號或密碼錯誤"
    
    # 如果是直接輸入網址進入 (GET)，或是登入失敗，都顯示登入畫面
    return render_template_string(login_html, message=msg)

# 3. 註冊路由
@app.route("/register", methods=["GET","POST"])
def register():
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

# 4. 登出路由
@app.route("/logout")
def logout():
    session.pop("user", None) # 清除 session
    return redirect(url_for("index")) # 登出後留在首頁 (變成未登入狀態)

# 5. Whisper 語音轉文字 API
@app.route("/api/transcribe", methods=["POST"])
def transcribe_audio():
    try:
        # 檢查是否有上傳的文件
        if "audio" not in request.files:
            return jsonify({"error": "沒有上傳音頻文件"}), 400
        
        audio_file = request.files["audio"]
        
        if audio_file.filename == "":
            return jsonify({"error": "文件為空"}), 400
        
        # 將上傳的音頻保存到臨時文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_file:
            audio_file.save(tmp_file.name)
            temp_path = tmp_file.name
        
        try:
            # 使用 Whisper 轉錄音頻
            # Whisper 會自動使用 ffmpeg 處理各種音頻格式（包括 webm）
            # language="zh" 指定中文，提高中文識別準確度
            print(f"開始轉錄音頻文件: {temp_path}")
            result = whisper_model.transcribe(
                temp_path, 
                language="zh",  # 指定中文
                task="transcribe",  # 轉錄任務
                fp16=False  # 如果沒有 GPU，使用 fp32
            )
            transcribed_text = result["text"].strip()
            print(f"轉錄結果: {transcribed_text}")
            
            if not transcribed_text:
                return jsonify({
                    "success": False,
                    "error": "未能識別到語音內容，請確保錄音清晰且包含語音"
                }), 200
            
            return jsonify({
                "success": True,
                "text": transcribed_text
            })
        finally:
            # 清理臨時文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"處理音頻時發生錯誤: {str(e)}")
        print(f"錯誤詳情: {error_trace}")
        return jsonify({
            "success": False,
            "error": f"處理音頻時發生錯誤: {str(e)}"
        }), 500

# 6. Gemini 聊天 API
@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        if not gemini_model:
            return jsonify({
                "success": False,
                "error": "Gemini API 未配置，請設置 GEMINI_API_KEY 環境變數"
            }), 500
        
        data = request.get_json()
        user_message = data.get("message", "").strip()
        
        if not user_message:
            return jsonify({
                "success": False,
                "error": "消息內容不能為空"
            }), 400
        
        # 獲取對話歷史
        conversation = get_conversation_history()
        
        # 構建提示詞（包含系統提示和對話歷史）
        system_prompt = "你是一個友善且專業的醫療AI助手，專門幫助用戶解答醫療相關問題。請用繁體中文回答，回答要準確、易懂且具有同理心。\n\n"
        
        # 將對話歷史轉換為 Gemini 格式
        chat_history = ""
        for msg in conversation[-10:]:  # 只使用最近 10 條消息
            if msg["role"] == "user":
                chat_history += f"用戶: {msg['content']}\n"
            else:
                chat_history += f"助手: {msg['content']}\n"
        
        full_prompt = system_prompt + chat_history + f"用戶: {user_message}\n助手:"
        
        # 調用 Gemini API
        print(f"發送消息到 Gemini: {user_message}")
        response = gemini_model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1000,
            )
        )
        
        ai_response = response.text.strip()
        print(f"Gemini 回應: {ai_response}")
        
        # 添加用戶消息和 AI 回應到歷史
        add_to_conversation("user", user_message)
        add_to_conversation("assistant", ai_response)
        
        return jsonify({
            "success": True,
            "message": ai_response
        })
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Gemini API 調用錯誤: {str(e)}")
        print(f"錯誤詳情: {error_trace}")
        return jsonify({
            "success": False,
            "error": f"Gemini API 調用失敗: {str(e)}"
        }), 500

# 7. 清除對話歷史
@app.route("/api/clear-history", methods=["POST"])
def clear_history():
    session["conversation"] = []
    return jsonify({"success": True, "message": "對話歷史已清除"})

if __name__ == "__main__":
    app.run(debug=True)
