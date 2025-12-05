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
# 確保環境變數已載入
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'medical_db')

# 輸出配置資訊（用於調試）
print("=" * 50)
print("資料庫配置資訊：")
print(f"Host: {DB_HOST}")
print(f"User: {DB_USER}")
print(f"Database: {DB_NAME}")
print("=" * 50)

DB_CONFIG = {
    'host': DB_HOST,
    'user': DB_USER,
    'password': DB_PASSWORD,
    'database': DB_NAME,
    'charset': 'utf8mb4',
    'ssl_disabled': True  # Azure MySQL 可能需要 SSL，如果連接失敗請改為 False
}

def get_db_connection():
    """獲取資料庫連接"""
    try:
        # 如果是 Azure MySQL，嘗試使用 SSL 連接
        if 'azure' in DB_CONFIG.get('host', '').lower():
            # Azure MySQL 通常需要 SSL，但如果連接失敗可以禁用
            connection = pymysql.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                charset=DB_CONFIG['charset'],
                ssl={'ssl_disabled': True}  # Azure 連接選項
            )
        else:
            connection = pymysql.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        print(f"資料庫連接錯誤: {e}")
        print(f"嘗試連接的資料庫: {DB_CONFIG['host']} / {DB_CONFIG['database']}")
        return None

def init_database():
    """初始化資料庫表結構"""
    connection = get_db_connection()
    if not connection:
        print("無法連接到資料庫，跳過表初始化")
        return
    
    try:
        with connection.cursor() as cursor:
            # 創建預約表（使用新表名避免與現有表衝突）
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
            print("[成功] 資料庫表初始化成功")
    except Exception as e:
        print(f"[錯誤] 資料庫表初始化失敗: {e}")
    finally:
        connection.close()

# 初始化資料庫
init_database()

def login_required(f):
    """登入驗證裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# === 2. 初始化 Gemini 模型 (更新版：支援 Gemini 2.0) ===
gemini_model = None
gemini_api_key = os.getenv("GEMINI_API_KEY")

print("=" * 50)
if gemini_api_key:
    print(f"[成功] 讀取到 API Key (前綴: {gemini_api_key[:5]}...)")
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
            print("\n[錯誤] 所有模型測試均失敗。嘗試使用最後手段：自動搜尋...")
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
             print("[錯誤] 嚴重錯誤：無法初始化任何 AI 模型。")

    except Exception as e:
        print(f"[錯誤] Gemini 設定發生嚴重錯誤: {e}")
else:
    print("[錯誤] 嚴重錯誤：找不到 GEMINI_API_KEY 環境變數！")
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

# === 預約門診相關路由 ===
@app.route("/appointment", methods=["GET", "POST"])
@login_required
def appointment():
    """預約門診頁面"""
    # 計算最小日期（明天）
    min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    if request.method == "POST":
        try:
            patient_name = request.form.get("patient_name", "").strip()
            patient_phone = request.form.get("patient_phone", "").strip()
            department = request.form.get("department", "").strip()
            doctor_name = request.form.get("doctor_name", "").strip()
            appointment_date = request.form.get("appointment_date", "").strip()
            appointment_time = request.form.get("appointment_time", "").strip()
            symptoms = request.form.get("symptoms", "").strip()
            
            # 驗證必填欄位
            if not all([patient_name, patient_phone, department, doctor_name, appointment_date, appointment_time]):
                return render_template("appointment.html", 
                                     username=session.get("user"),
                                     error="請填寫所有必填欄位",
                                     form_data=request.form,
                                     min_date=min_date)
            
            # 驗證日期格式
            try:
                appointment_datetime = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
                if appointment_datetime < datetime.now():
                    return render_template("appointment.html",
                                         username=session.get("user"),
                                         error="預約時間不能是過去時間",
                                         form_data=request.form,
                                         min_date=min_date)
            except ValueError:
                return render_template("appointment.html",
                                     username=session.get("user"),
                                     error="日期或時間格式錯誤",
                                     form_data=request.form,
                                     min_date=min_date)
            
            # 插入資料庫
            connection = get_db_connection()
            if not connection:
                return render_template("appointment.html",
                                     username=session.get("user"),
                                     error="資料庫連接失敗，請稍後再試",
                                     form_data=request.form,
                                     min_date=min_date)
            
            try:
                with connection.cursor() as cursor:
                    sql = """
                    INSERT INTO medical_appointments 
                    (username, patient_name, patient_phone, department, doctor_name, 
                     appointment_date, appointment_time, symptoms, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                    """
                    cursor.execute(sql, (
                        session.get("user"),
                        patient_name,
                        patient_phone,
                        department,
                        doctor_name,
                        appointment_date,
                        appointment_time,
                        symptoms
                    ))
                    connection.commit()
                    return redirect(url_for("appointment_list", success="預約成功！"))
            except Exception as e:
                connection.rollback()
                print(f"預約失敗: {e}")
                return render_template("appointment.html",
                                     username=session.get("user"),
                                     error=f"預約失敗：{str(e)}",
                                     form_data=request.form,
                                     min_date=min_date)
            finally:
                connection.close()
        
        except Exception as e:
            print(f"處理預約時發生錯誤: {e}")
            return render_template("appointment.html",
                                 username=session.get("user"),
                                 error="發生錯誤，請稍後再試",
                                 form_data=request.form,
                                 min_date=min_date)
    
    return render_template("appointment.html", username=session.get("user"), min_date=min_date)

@app.route("/appointment/list")
@login_required
def appointment_list():
    """查看預約記錄"""
    connection = get_db_connection()
    if not connection:
        return render_template("appointment_list.html",
                             username=session.get("user"),
                             appointments=[],
                             error="資料庫連接失敗")
    
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = """
            SELECT id, patient_name, patient_phone, department, doctor_name,
                   appointment_date, appointment_time, symptoms, status, created_at
            FROM medical_appointments
            WHERE username = %s
            ORDER BY appointment_date DESC, appointment_time DESC
            """
            cursor.execute(sql, (session.get("user"),))
            appointments = cursor.fetchall()
            
            # 轉換日期時間格式
            for apt in appointments:
                if apt['appointment_date']:
                    apt['appointment_date'] = apt['appointment_date'].strftime('%Y-%m-%d')
                if apt['appointment_time']:
                    apt['appointment_time'] = apt['appointment_time'].strftime('%H:%M')
                if apt['created_at']:
                    apt['created_at'] = apt['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            success_msg = request.args.get("success", "")
            return render_template("appointment_list.html",
                                 username=session.get("user"),
                                 appointments=appointments,
                                 success=success_msg)
    except Exception as e:
        print(f"查詢預約記錄失敗: {e}")
        return render_template("appointment_list.html",
                             username=session.get("user"),
                             appointments=[],
                             error="查詢失敗")
    finally:
        connection.close()

@app.route("/appointment/cancel/<int:appointment_id>", methods=["POST"])
@login_required
def cancel_appointment(appointment_id):
    """取消預約"""
    connection = get_db_connection()
    if not connection:
        return jsonify({"success": False, "error": "資料庫連接失敗"}), 500
    
    try:
        with connection.cursor() as cursor:
            # 檢查預約是否屬於當前用戶
            check_sql = "SELECT username FROM medical_appointments WHERE id = %s"
            cursor.execute(check_sql, (appointment_id,))
            result = cursor.fetchone()
            
            if not result or result[0] != session.get("user"):
                return jsonify({"success": False, "error": "無權限取消此預約"}), 403
            
            # 更新狀態為已取消
            update_sql = "UPDATE medical_appointments SET status = 'cancelled' WHERE id = %s"
            cursor.execute(update_sql, (appointment_id,))
            connection.commit()
            
            return jsonify({"success": True, "message": "預約已取消"})
    except Exception as e:
        connection.rollback()
        print(f"取消預約失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        connection.close()

if __name__ == "__main__":
    app.run(debug=True)