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

# === 1. 強制載入 .env ===
basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')
load_dotenv(env_path)

app = Flask(__name__)
app.secret_key = "supersecretkey"

# === MySQL 資料庫配置 ===
# 注意：這裡只保留基礎配置，不放入會導致錯誤的額外參數
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'medical_db'),
    'charset': 'utf8mb4',
}

def get_db_connection():
    """獲取資料庫連接 (修正版)"""
    try:
        # 複製配置以免修改全域變數
        config = DB_CONFIG.copy()
        
        # 針對 Azure 或特殊環境的 SSL 處理
        if 'azure' in config.get('host', '').lower():
            connection = pymysql.connect(
                ssl={'ssl_disabled': True},
                **config
            )
        else:
            # 本機環境：直接連接，確保沒有多餘參數
            connection = pymysql.connect(**config)
            
        return connection
    except pymysql.Error as e:
        print(f"資料庫連接錯誤 (PyMySQL): {e}")
        return None
    except Exception as e:
        print(f"資料庫連接錯誤 (未知): {e}")
        return None

def init_database():
    """初始化資料庫表結構"""
    print("[初始化] 開始檢查資料庫表結構...")
    connection = get_db_connection()
    if not connection:
        print("[警告] 無法連接到資料庫，跳過表初始化。請檢查 .env 配置。")
        return False
    
    try:
        with connection.cursor() as cursor:
            # 創建預約表
            create_appointments_table = """
            CREATE TABLE IF NOT EXISTS medical_appointments (
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
                INDEX idx_username (username),
                INDEX idx_appointment_date (appointment_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            cursor.execute(create_appointments_table)
            connection.commit()
            print("[成功] 資料庫表檢查/創建完成")
            return True
                
    except Exception as e:
        print(f"[錯誤] 資料庫表初始化失敗: {e}")
        return False
    finally:
        if connection:
            connection.close()

# 啟動時嘗試初始化
init_database()

def login_required(f):
    """登入驗證裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# === 2. 初始化 Gemini 模型 ===
gemini_model = None
gemini_api_key = os.getenv("GEMINI_API_KEY")

print("=" * 50)
if gemini_api_key:
    print(f"✅ 讀取到 API Key (前綴: {gemini_api_key[:5]}...)")
    try:
        genai.configure(api_key=gemini_api_key)
        models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
        
        for model_name in models_to_try:
            try:
                temp_model = genai.GenerativeModel(model_name)
                response = temp_model.generate_content("Hello")
                if response:
                    gemini_model = temp_model
                    print(f"成功！使用此模型: {model_name}")
                    break
            except:
                continue
        
        if not gemini_model:
             print("❌ 模型初始化失敗，將無法使用 AI 回應功能。")
    except Exception as e:
        print(f"❌ Gemini 設定錯誤: {e}")
else:
    print("❌ 警告：未設置 GEMINI_API_KEY，AI 功能將無法使用。")
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
            
            ai_reply = ""
            if gemini_model and text:
                try:
                    system_prompt = """您是一位專業的醫療AI助手，請使用繁體中文回覆。當用戶詢問預約相關問題時，請引導用戶使用網站的「預約門診」功能。"""
                    response = gemini_model.generate_content(system_prompt + "\n\n用戶問題：" + text)
                    ai_reply = response.text.strip()
                except:
                    pass

            return jsonify({"success": True, "text": text, "ai_response": ai_reply})
        finally:
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
def chat():
    global gemini_model
    if not gemini_model:
        return jsonify({"success": False, "error": "AI 模型初始化失敗"}), 500
    
    data = request.get_json()
    msg = data.get("message", "").strip()
    if not msg: return jsonify({"success": False, "error": "Empty message"}), 400
    
    try:
        system_prompt = "您是一位專業的醫療AI助手，請使用繁體中文回覆。當用戶詢問預約時，請引導其使用「預約門診」頁面。"
        response = gemini_model.generate_content(system_prompt + "\n\n用戶問題：" + msg)
        return jsonify({"success": True, "message": response.text.strip()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/clear-history", methods=["POST"])
def clear_history():
    return jsonify({"success": True})

# === 預約門診相關路由 (核心修復部分) ===
@app.route("/appointment", methods=["GET", "POST"])
@login_required
def appointment():
    """預約門診頁面"""
    min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    if request.method == "POST":
        try:
            # 1. 獲取表單資料
            form = request.form
            patient_name = form.get("patient_name", "").strip()
            patient_phone = form.get("patient_phone", "").strip()
            department = form.get("department", "").strip()
            doctor_name = form.get("doctor_name", "").strip()
            appointment_date = form.get("appointment_date", "").strip()
            appointment_time = form.get("appointment_time", "").strip()
            
            # 2. 基礎驗證
            if not all([patient_name, patient_phone, department, doctor_name, appointment_date, appointment_time]):
                return render_template("appointment.html", username=session.get("user"), error="請填寫所有欄位", form_data=form, min_date=min_date)
            
            # 3. 日期驗證
            try:
                apt_dt = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
                if apt_dt < datetime.now():
                    return render_template("appointment.html", username=session.get("user"), error="不能預約過去的時間", form_data=form, min_date=min_date)
            except ValueError:
                return render_template("appointment.html", username=session.get("user"), error="日期時間格式錯誤", form_data=form, min_date=min_date)
            
            # 4. 資料庫寫入 (含自動修復邏輯)
            connection = get_db_connection()
            if not connection:
                return render_template("appointment.html", username=session.get("user"), error="資料庫連接失敗，請檢查 .env 設定或 MySQL 服務", form_data=form, min_date=min_date)
            
            try:
                with connection.cursor() as cursor:
                    sql = """
                    INSERT INTO medical_appointments 
                    (username, patient_name, patient_phone, department, doctor_name, 
                     appointment_date, appointment_time, symptoms, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, 'pending')
                    """
                    data = (session.get("user"), patient_name, patient_phone, department, doctor_name, appointment_date, appointment_time)
                    
                    try:
                        cursor.execute(sql, data)
                        connection.commit()
                    except pymysql.Error as e:
                        # 自動修復：如果錯誤是「資料表不存在」(1146)，則嘗試創建表並重試
                        if e.args[0] == 1146:
                            print("[自動修復] 檢測到資料表缺失，正在嘗試重建...")
                            connection.rollback()
                            if init_database(): # 重新初始化
                                # 重新獲取連接並重試
                                connection.close()
                                connection = get_db_connection()
                                with connection.cursor() as retry_cursor:
                                    retry_cursor.execute(sql, data)
                                    connection.commit()
                                    print("[自動修復] 資料表重建並寫入成功！")
                            else:
                                raise e # 初始化失敗，拋出原始錯誤
                        else:
                            raise e # 其他錯誤直接拋出

                    # 成功寫入
                    return redirect(url_for("appointment_list", success="預約成功！"))
                    
            except pymysql.Error as e:
                connection.rollback()
                print(f"[資料庫錯誤] {e}")
                error_msg = f"資料庫寫入錯誤 (代碼 {e.args[0]})。請確保資料庫 'medical_db' 已建立。"
                if e.args[0] == 1045: error_msg = "資料庫密碼錯誤 (Access Denied)"
                if e.args[0] == 1049: error_msg = "資料庫 'medical_db' 不存在，請先建立資料庫"
                
                return render_template("appointment.html", username=session.get("user"), error=error_msg, form_data=form, min_date=min_date)
            finally:
                connection.close()

        except Exception as e:
            print(f"[系統錯誤] {e}")
            return render_template("appointment.html", username=session.get("user"), error=f"系統發生未預期的錯誤: {str(e)}", form_data=request.form, min_date=min_date)

    return render_template("appointment.html", username=session.get("user"), min_date=min_date)

@app.route("/appointment/list")
@login_required
def appointment_list():
    """查看預約記錄"""
    connection = get_db_connection()
    if not connection:
        return render_template("appointment_list.html", username=session.get("user"), appointments=[], error="資料庫連接失敗")
    
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = "SELECT * FROM medical_appointments WHERE username = %s ORDER BY appointment_date DESC, appointment_time DESC"
            cursor.execute(sql, (session.get("user"),))
            appointments = cursor.fetchall()
            return render_template("appointment_list.html", username=session.get("user"), appointments=appointments, success=request.args.get("success"))
    except Exception as e:
        # 如果是資料表不存在，回傳空列表而不是錯誤
        if "1146" in str(e):
             return render_template("appointment_list.html", username=session.get("user"), appointments=[], error=None)
        return render_template("appointment_list.html", username=session.get("user"), appointments=[], error=str(e))
    finally:
        if connection: connection.close()

@app.route("/appointment/cancel/<int:appointment_id>", methods=["POST"])
@login_required
def cancel_appointment(appointment_id):
    connection = get_db_connection()
    if not connection: return jsonify({"success": False, "error": "DB connect fail"}), 500
    try:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE medical_appointments SET status='cancelled' WHERE id=%s AND username=%s", (appointment_id, session.get("user")))
            connection.commit()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()

if __name__ == "__main__":
    app.run(debug=True)
