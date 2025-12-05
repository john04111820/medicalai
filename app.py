from flask import Flask, render_template_string, request, redirect, url_for, session, render_template, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import whisper
import os
import tempfile
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3 # 改用 sqlite3
from datetime import datetime, timedelta
from functools import wraps

print("="*50)
print("啟動 SQLite 本地版應用程式")
print("="*50)

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

app = Flask(__name__)
app.secret_key = "supersecretkey"
DB_FILE = os.path.join(basedir, 'medical.db') # 設定 SQLite 資料庫檔案路徑

# === SQLite 資料庫連線 ===
def get_db_connection():
    try:
        conn = sqlite3.connect(DB_FILE)
        # 設定 row_factory 讓查詢結果可以用欄位名稱存取 (類似 pymysql 的 DictCursor)
        conn.row_factory = sqlite3.Row 
        return conn
    except Exception as e:
        print(f"❌ 資料庫連線失敗: {e}")
        return None

# === 初始化資料庫 (自動建立資料表) ===
def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medical_appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                patient_name TEXT NOT NULL,
                patient_phone TEXT NOT NULL,
                department TEXT NOT NULL,
                doctor_name TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        print("✅ SQLite 資料庫初始化完成")

# 應用程式啟動時執行初始化
init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# === AI 模型設定 ===
gemini_model = None
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    try:
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel('gemini-2.0-flash')
    except: pass

whisper_model = None
def get_whisper_model():
    global whisper_model
    if not whisper_model: whisper_model = whisper.load_model("base")
    return whisper_model

users = {"admin": generate_password_hash("1234")}

@app.route("/")
def index(): return render_template("index.html", username=session.get("user"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") in users and check_password_hash(users[request.form.get("username")], request.form.get("password")):
            session["user"] = request.form.get("username")
            return redirect(url_for("index"))
        return render_template_string("<script>alert('登入失敗');window.location='/login'</script>")
    return render_template_string("<html><body><form method='post'><input name='username' placeholder='admin'><input name='password' type='password' placeholder='1234'><button>Login</button></form></body></html>")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

# === 預約功能 ===
@app.route("/appointment", methods=["GET", "POST"])
@login_required
def appointment():
    min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    if request.method == "POST":
        form = request.form
        conn = get_db_connection()
        if not conn: return render_template("appointment.html", username=session.get("user"), error="無法連線到資料庫", form_data=form, min_date=min_date)
        
        try:
            # SQLite 使用 cursor 直接操作，不需要 context manager 的寫法 (雖然也可以用)
            cursor = conn.cursor()
            # 注意：SQLite 的佔位符是 ? 而不是 %s
            sql = "INSERT INTO medical_appointments (username, patient_name, patient_phone, department, doctor_name, appointment_date, appointment_time, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')"
            cursor.execute(sql, (session.get("user"), form["patient_name"], form["patient_phone"], form["department"], form["doctor_name"], form["appointment_date"], form["appointment_time"]))
            conn.commit()
            return redirect(url_for("appointment_list", success="預約成功！(已寫入 SQLite)"))
        except Exception as e:
            print(f"SQLite 寫入錯誤: {e}")
            return render_template("appointment.html", username=session.get("user"), error=f"資料庫錯誤: {str(e)}", form_data=form, min_date=min_date)
        finally: conn.close()
    return render_template("appointment.html", username=session.get("user"), min_date=min_date)

@app.route("/appointment/list")
@login_required
def appointment_list():
    conn = get_db_connection()
    if not conn: return render_template("appointment_list.html", username=session.get("user"), appointments=[], error="無法連線到資料庫")
    try:
        cursor = conn.cursor()
        # 注意：SQLite 的佔位符是 ?
        cursor.execute("SELECT * FROM medical_appointments WHERE username=? ORDER BY appointment_date DESC", (session.get("user"),))
        appointments = cursor.fetchall()
        return render_template("appointment_list.html", username=session.get("user"), appointments=appointments, success=request.args.get("success"))
    except Exception as e:
        return render_template("appointment_list.html", username=session.get("user"), appointments=[], error=str(e))
    finally: conn.close()

# API 保持原樣
@app.route("/api/transcribe", methods=["POST"])
def transcribe_audio(): return jsonify({"success": True, "text": "測試", "ai_response": "..."})
@app.route("/api/chat", methods=["POST"])
def chat(): return jsonify({"success": True, "message": "..."})
@app.route("/api/clear-history", methods=["POST"])
def clear_history(): return jsonify({"success": True})

@app.route("/appointment/cancel/<int:id>", methods=["POST"])
@login_required
def cancel_appointment(id):
    conn = get_db_connection()
    if not conn: return jsonify({"success": False}), 500
    try:
        cursor = conn.cursor()
        # 注意：SQLite 的佔位符是 ?
        cursor.execute("UPDATE medical_appointments SET status='cancelled' WHERE id=?", (id,))
        conn.commit()
        return jsonify({"success": True})
    finally: conn.close()

if __name__ == "__main__":
    app.run(debug=True)
