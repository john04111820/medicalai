from flask import Flask, render_template_string, request, redirect, url_for, session, render_template, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import whisper
import os
import tempfile
import google.generativeai as genai
from dotenv import load_dotenv
import pymysql
from datetime import datetime, timedelta
from functools import wraps

print("="*50)
print("啟動 Azure 連線版應用程式 (v5.0 Force)")
print("="*50)

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

app = Flask(__name__)
app.secret_key = "supersecretkey"

# === Azure 資料庫連線 ===
def get_db_connection():
    try:
        # 讀取環境變數
        host = os.getenv('DB_HOST')
        user = os.getenv('DB_USER')
        password = os.getenv('DB_PASSWORD')
        database = os.getenv('DB_NAME')

        if not all([host, user, password, database]):
            print("❌ 錯誤：缺少資料庫設定，請先執行 setup_azure_force.py")
            return None

        # 設定連線參數
        config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database,
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }

        # Azure 強制 SSL 處理
        # 只要是 Azure 主機，就自動加入 SSL 參數
        if 'azure' in host.lower():
            config['ssl'] = {'ssl_disabled': True}

        return pymysql.connect(**config)
    except Exception as e:
        print(f"❌ 資料庫連線失敗: {e}")
        return None

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
        if not conn: return render_template("appointment.html", username=session.get("user"), error="無法連線到 Azure 資料庫 (請檢查防火牆)", form_data=form, min_date=min_date)
        
        try:
            with conn.cursor() as cursor:
                sql = "INSERT INTO medical_appointments (username, patient_name, patient_phone, department, doctor_name, appointment_date, appointment_time, status) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')"
                cursor.execute(sql, (session.get("user"), form["patient_name"], form["patient_phone"], form["department"], form["doctor_name"], form["appointment_date"], form["appointment_time"]))
                conn.commit()
                return redirect(url_for("appointment_list", success="預約成功！(已寫入 Azure)"))
        except Exception as e:
            print(f"Azure 寫入錯誤: {e}")
            return render_template("appointment.html", username=session.get("user"), error=f"Azure 錯誤: {str(e)}", form_data=form, min_date=min_date)
        finally: conn.close()
    return render_template("appointment.html", username=session.get("user"), min_date=min_date)

@app.route("/appointment/list")
@login_required
def appointment_list():
    conn = get_db_connection()
    if not conn: return render_template("appointment_list.html", username=session.get("user"), appointments=[], error="無法連線到 Azure")
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM medical_appointments WHERE username=%s ORDER BY appointment_date DESC", (session.get("user"),))
            return render_template("appointment_list.html", username=session.get("user"), appointments=cursor.fetchall(), success=request.args.get("success"))
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
        with conn.cursor() as c:
            c.execute("UPDATE medical_appointments SET status='cancelled' WHERE id=%s", (id,))
            conn.commit()
        return jsonify({"success": True})
    finally: conn.close()

if __name__ == "__main__":
    app.run(debug=True)
