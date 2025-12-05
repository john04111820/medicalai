from flask import Flask, render_template_string, request, redirect, url_for, session, render_template, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import whisper
import os
import tempfile
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3
import pymysql
from datetime import datetime, timedelta
from functools import wraps

print("="*50)
if os.getenv('USE_SQLITE', 'true').lower() == 'true':
    print("啟動應用程式 (使用 SQLite 資料庫)")
else:
    print("啟動 Azure 連線版應用程式 (使用 MySQL)")
print("="*50)

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

app = Flask(__name__)
app.secret_key = "supersecretkey"

# === 資料庫連線設定 ===
# 使用 SQLite 或 MySQL（優先使用 SQLite）
USE_SQLITE = os.getenv('USE_SQLITE', 'true').lower() == 'true'
SQLITE_DB_FILE = 'medical_appointments.db'

def get_db_connection():
    """獲取資料庫連接（支援 SQLite 和 MySQL）"""
    try:
        if USE_SQLITE:
            # 使用 SQLite
            conn = sqlite3.connect(SQLITE_DB_FILE)
            conn.row_factory = sqlite3.Row  # 讓結果可以像字典一樣訪問
            return conn
        else:
            # 使用 MySQL (Azure)
            host = os.getenv('DB_HOST')
            user = os.getenv('DB_USER')
            password = os.getenv('DB_PASSWORD')
            database = os.getenv('DB_NAME')

            if not all([host, user, password, database]):
                print("[錯誤] 缺少 MySQL 資料庫設定，請先執行 setup_azure_force.py")
                return None

            config = {
                'host': host,
                'user': user,
                'password': password,
                'database': database,
                'charset': 'utf8mb4',
                'cursorclass': pymysql.cursors.DictCursor
            }

            if 'azure' in host.lower():
                config['ssl'] = {'ssl_disabled': True}

            return pymysql.connect(**config)
    except Exception as e:
        print(f"[錯誤] 資料庫連線失敗: {e}")
        return None

def init_sqlite_database():
    """初始化 SQLite 資料庫表結構"""
    if not USE_SQLITE:
        return
    
    try:
        conn = sqlite3.connect(SQLITE_DB_FILE)
        cursor = conn.cursor()
        
        # 檢查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='medical_appointments'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            # 檢查是否已有病歷號欄位
            cursor.execute("PRAGMA table_info(medical_appointments)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'patient_id' not in columns:
                # 添加病歷號欄位
                try:
                    cursor.execute("ALTER TABLE medical_appointments ADD COLUMN patient_id VARCHAR(50)")
                    print("[成功] 已添加病歷號欄位到現有資料表")
                except Exception as e:
                    print(f"[注意] 添加病歷號欄位時發生錯誤（可能已存在）: {e}")
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS medical_appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(100) NOT NULL,
            patient_id VARCHAR(50),
            patient_name VARCHAR(100) NOT NULL,
            patient_phone VARCHAR(20) NOT NULL,
            department VARCHAR(100) NOT NULL,
            doctor_name VARCHAR(100) NOT NULL,
            appointment_date DATE NOT NULL,
            appointment_time TIME NOT NULL,
            symptoms TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        cursor.execute(create_table_sql)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON medical_appointments(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointment_date ON medical_appointments(appointment_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_patient_id ON medical_appointments(patient_id)")
        conn.commit()
        conn.close()
        print(f"[成功] SQLite 資料庫已初始化: {SQLITE_DB_FILE}")
    except Exception as e:
        print(f"[錯誤] SQLite 資料庫初始化失敗: {e}")

# 初始化 SQLite 資料庫
if USE_SQLITE:
    init_sqlite_database()

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
        # 設定醫療專用的系統提示詞
        medical_system_prompt = """你是一位專業的醫療AI助理，專門協助處理醫療相關問題和預約服務。

重要規則：
1. 所有回答必須使用繁體中文
2. 專注於醫療健康相關內容
3. 提供專業、準確、友善的醫療建議
4. 當用戶詢問預約資訊時，你可以查詢資料庫獲取相關資訊
5. 當用戶想要預約或修改預約時，你可以協助處理
6. 對於非醫療問題，禮貌地引導用戶詢問醫療相關問題

你可以執行的功能：

【查詢預約】
當用戶詢問預約資訊時，系統會自動查詢資料庫並提供相關記錄，你可以根據這些資訊回答用戶。

【創建預約】
當用戶想要預約門診時，你需要收集以下資訊：
- 病歷號（選填）
- 病患姓名（必填）
- 聯絡電話（必填）
- 科別（必填，如：內科、外科、兒科等）
- 醫師姓名（必填）
- 預約日期（必填，必須是未來日期）
- 預約時間（必填）
- 症狀描述（選填）

如果資訊不完整，請友善地詢問缺少的資訊。

【修改預約】
當用戶想要修改預約時，你需要：
1. 先找到要修改的預約（根據病歷號、姓名或電話）
2. 確認要修改的欄位
3. 更新預約資訊

請始終以專業、友善的態度回答，並確保所有資訊準確無誤。"""
        
        gemini_model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=medical_system_prompt)
        print("[成功] Gemini 醫療AI模型已初始化")
    except Exception as e:
        print(f"[錯誤] Gemini 模型初始化失敗: {e}")
else:
    print("[警告] 未找到 GEMINI_API_KEY，AI 聊天功能將無法使用")

whisper_model = None
def get_whisper_model():
    global whisper_model
    if not whisper_model:
        try:
            print("[載入] 正在載入 Whisper 模型...")
            whisper_model = whisper.load_model("base")
            print("[成功] Whisper 模型已載入")
        except Exception as e:
            print(f"[錯誤] Whisper 模型載入失敗: {e}")
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
        if not conn: 
            db_type = "SQLite" if USE_SQLITE else "Azure MySQL"
            return render_template("appointment.html", username=session.get("user"), 
                                 error=f"無法連線到 {db_type} 資料庫", form_data=form, min_date=min_date)
        
        try:
            if USE_SQLITE:
                # SQLite 使用 ? 作為參數佔位符
                sql = """INSERT INTO medical_appointments 
                        (username, patient_id, patient_name, patient_phone, department, doctor_name, 
                         appointment_date, appointment_time, symptoms, status) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')"""
                symptoms = form.get("symptoms", "").strip() or None
                patient_id = form.get("patient_id", "").strip() or None
                conn.execute(sql, (
                    session.get("user"),
                    patient_id,
                    form["patient_name"], 
                    form["patient_phone"], 
                    form["department"], 
                    form["doctor_name"], 
                    form["appointment_date"], 
                    form["appointment_time"],
                    symptoms
                ))
                conn.commit()
                success_msg = "預約成功！(已寫入 SQLite 資料庫)"
            else:
                # MySQL 使用 %s 作為參數佔位符
                with conn.cursor() as cursor:
                    sql = """INSERT INTO medical_appointments 
                            (username, patient_id, patient_name, patient_phone, department, doctor_name, 
                             appointment_date, appointment_time, symptoms, status) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')"""
                    symptoms = form.get("symptoms", "").strip() or None
                    patient_id = form.get("patient_id", "").strip() or None
                    cursor.execute(sql, (
                        session.get("user"),
                        patient_id,
                        form["patient_name"], 
                        form["patient_phone"], 
                        form["department"], 
                        form["doctor_name"], 
                        form["appointment_date"], 
                        form["appointment_time"],
                        symptoms
                    ))
                    conn.commit()
                success_msg = "預約成功！(已寫入 Azure MySQL)"
            
            return redirect(url_for("appointment_list", success=success_msg))
        except Exception as e:
            print(f"資料庫寫入錯誤: {e}")
            db_type = "SQLite" if USE_SQLITE else "Azure MySQL"
            return render_template("appointment.html", username=session.get("user"), 
                                 error=f"{db_type} 錯誤: {str(e)}", form_data=form, min_date=min_date)
        finally: 
            conn.close()
    return render_template("appointment.html", username=session.get("user"), min_date=min_date)

@app.route("/appointment/list")
@login_required
def appointment_list():
    conn = get_db_connection()
    if not conn: 
        db_type = "SQLite" if USE_SQLITE else "Azure MySQL"
        return render_template("appointment_list.html", username=session.get("user"), 
                             appointments=[], error=f"無法連線到 {db_type}")
    try:
        username = session.get("user")
        if USE_SQLITE:
            # SQLite 查詢
            cursor = conn.execute(
                "SELECT * FROM medical_appointments WHERE username=? ORDER BY appointment_date DESC, appointment_time DESC", 
                (username,)
            )
            # 將 Row 對象轉換為字典
            appointments = [dict(row) for row in cursor.fetchall()]
        else:
            # MySQL 查詢
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM medical_appointments WHERE username=%s ORDER BY appointment_date DESC, appointment_time DESC", 
                    (username,)
                )
                appointments = cursor.fetchall()
        
        # 格式化日期時間
        for apt in appointments:
            if apt.get('appointment_date'):
                if isinstance(apt['appointment_date'], str):
                    apt['appointment_date'] = apt['appointment_date']
                else:
                    apt['appointment_date'] = apt['appointment_date'].strftime('%Y-%m-%d')
            if apt.get('appointment_time'):
                if isinstance(apt['appointment_time'], str):
                    apt['appointment_time'] = apt['appointment_time']
                else:
                    apt['appointment_time'] = apt['appointment_time'].strftime('%H:%M')
            if apt.get('created_at'):
                if isinstance(apt['created_at'], str):
                    apt['created_at'] = apt['created_at']
                else:
                    apt['created_at'] = apt['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return render_template("appointment_list.html", username=username, 
                             appointments=appointments, success=request.args.get("success"))
    except Exception as e:
        return render_template("appointment_list.html", username=session.get("user"), 
                             appointments=[], error=str(e))
    finally: 
        conn.close()

# === AI API 端點 ===
@app.route("/api/transcribe", methods=["POST"])
def transcribe_audio():
    """語音轉文字 API"""
    try:
        if "audio" not in request.files:
            return jsonify({"success": False, "error": "沒有收到音頻文件"}), 400
        
        audio_file = request.files["audio"]
        if audio_file.filename == "":
            return jsonify({"success": False, "error": "音頻文件名稱為空"}), 400
        
        # 保存臨時文件
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"whisper_{os.urandom(4).hex()}.webm")
        audio_file.save(temp_path)
        
        try:
            # 使用 Whisper 轉錄
            model = get_whisper_model()
            if not model:
                return jsonify({"success": False, "error": "Whisper 模型未載入"}), 500
            
            result = model.transcribe(temp_path, language="zh", fp16=False)
            text = result["text"].strip()
            print(f"[Whisper] 轉錄結果: {text}")
            
            # 可選：自動觸發 Gemini 回應
            ai_reply = ""
            if gemini_model and text:
                try:
                    response = gemini_model.generate_content(text)
                    ai_reply = response.text.strip()
                except Exception as e:
                    print(f"[錯誤] Gemini 回應失敗: {e}")
            
            return jsonify({
                "success": True, 
                "text": text, 
                "ai_response": ai_reply
            })
        finally:
            # 清理臨時文件
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
    except Exception as e:
        print(f"[錯誤] 語音轉錄失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def query_appointments_by_keyword(username, keyword=""):
    """根據關鍵字查詢預約記錄（支援病歷號、姓名、電話）"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        if keyword:
            if USE_SQLITE:
                cursor = conn.execute(
                    """SELECT * FROM medical_appointments 
                       WHERE username = ? AND (
                           patient_id LIKE ? OR 
                           patient_name LIKE ? OR 
                           patient_phone LIKE ?
                       )
                       ORDER BY appointment_date DESC, appointment_time DESC""",
                    (username, f'%{keyword}%', f'%{keyword}%', f'%{keyword}%')
                )
                appointments = [dict(row) for row in cursor.fetchall()]
            else:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """SELECT * FROM medical_appointments 
                           WHERE username = %s AND (
                               patient_id LIKE %s OR 
                               patient_name LIKE %s OR 
                               patient_phone LIKE %s
                           )
                           ORDER BY appointment_date DESC, appointment_time DESC""",
                        (username, f'%{keyword}%', f'%{keyword}%', f'%{keyword}%')
                    )
                    appointments = cursor.fetchall()
        else:
            # 查詢所有預約
            if USE_SQLITE:
                cursor = conn.execute(
                    """SELECT * FROM medical_appointments 
                       WHERE username = ?
                       ORDER BY appointment_date DESC, appointment_time DESC""",
                    (username,)
                )
                appointments = [dict(row) for row in cursor.fetchall()]
            else:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """SELECT * FROM medical_appointments 
                           WHERE username = %s
                           ORDER BY appointment_date DESC, appointment_time DESC""",
                        (username,)
                    )
                    appointments = cursor.fetchall()
        
        # 格式化日期時間
        for apt in appointments:
            if apt.get('appointment_date') and not isinstance(apt['appointment_date'], str):
                apt['appointment_date'] = apt['appointment_date'].strftime('%Y-%m-%d')
            if apt.get('appointment_time') and not isinstance(apt['appointment_time'], str):
                apt['appointment_time'] = apt['appointment_time'].strftime('%H:%M')
        
        return appointments
    except Exception as e:
        print(f"[錯誤] 查詢預約記錄失敗: {e}")
        return []
    finally:
        conn.close()

def create_appointment_via_ai(username, appointment_data):
    """通過 AI 創建預約"""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "資料庫連接失敗"}
    
    try:
        # 驗證必填欄位
        required_fields = ['patient_name', 'patient_phone', 'department', 'doctor_name', 'appointment_date', 'appointment_time']
        missing_fields = [field for field in required_fields if not appointment_data.get(field)]
        
        if missing_fields:
            return {"success": False, "error": f"缺少必填欄位: {', '.join(missing_fields)}"}
        
        # 驗證日期
        from datetime import datetime
        try:
            appointment_datetime = datetime.strptime(f"{appointment_data['appointment_date']} {appointment_data['appointment_time']}", "%Y-%m-%d %H:%M")
            if appointment_datetime < datetime.now():
                return {"success": False, "error": "預約時間不能是過去時間"}
        except ValueError:
            return {"success": False, "error": "日期或時間格式錯誤"}
        
        if USE_SQLITE:
            sql = """INSERT INTO medical_appointments 
                    (username, patient_id, patient_name, patient_phone, department, doctor_name, 
                     appointment_date, appointment_time, symptoms, status) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')"""
            symptoms = appointment_data.get("symptoms", "").strip() or None
            patient_id = appointment_data.get("patient_id", "").strip() or None
            cursor = conn.execute(sql, (
                username,
                patient_id,
                appointment_data['patient_name'],
                appointment_data['patient_phone'],
                appointment_data['department'],
                appointment_data['doctor_name'],
                appointment_data['appointment_date'],
                appointment_data['appointment_time'],
                symptoms
            ))
            appointment_id = cursor.lastrowid
            conn.commit()
        else:
            with conn.cursor() as cursor:
                sql = """INSERT INTO medical_appointments 
                        (username, patient_id, patient_name, patient_phone, department, doctor_name, 
                         appointment_date, appointment_time, symptoms, status) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')"""
                symptoms = appointment_data.get("symptoms", "").strip() or None
                patient_id = appointment_data.get("patient_id", "").strip() or None
                cursor.execute(sql, (
                    username,
                    patient_id,
                    appointment_data['patient_name'],
                    appointment_data['patient_phone'],
                    appointment_data['department'],
                    appointment_data['doctor_name'],
                    appointment_data['appointment_date'],
                    appointment_data['appointment_time'],
                    symptoms
                ))
                appointment_id = cursor.lastrowid
                conn.commit()
        
        return {"success": True, "appointment_id": appointment_id, "message": "預約已成功創建"}
    except Exception as e:
        print(f"[錯誤] 創建預約失敗: {e}")
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def update_appointment_via_ai(username, appointment_id, update_data):
    """通過 AI 修改預約"""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "資料庫連接失敗"}
    
    try:
        # 先檢查預約是否存在且屬於當前用戶
        if USE_SQLITE:
            cursor = conn.execute("SELECT username FROM medical_appointments WHERE id=?", (appointment_id,))
            result = cursor.fetchone()
            if not result or dict(result)['username'] != username:
                return {"success": False, "error": "找不到該預約記錄或無權限修改"}
        else:
            with conn.cursor() as cursor:
                cursor.execute("SELECT username FROM medical_appointments WHERE id=%s", (appointment_id,))
                result = cursor.fetchone()
                if not result or result['username'] != username:
                    return {"success": False, "error": "找不到該預約記錄或無權限修改"}
        
        # 構建更新 SQL
        update_fields = []
        update_values = []
        
        allowed_fields = ['patient_id', 'patient_name', 'patient_phone', 'department', 
                         'doctor_name', 'appointment_date', 'appointment_time', 'symptoms', 'status']
        
        for field in allowed_fields:
            if field in update_data:
                update_fields.append(f"{field} = ?" if USE_SQLITE else f"{field} = %s")
                update_values.append(update_data[field])
        
        if not update_fields:
            return {"success": False, "error": "沒有要更新的欄位"}
        
        update_values.append(appointment_id)
        
        if USE_SQLITE:
            sql = f"UPDATE medical_appointments SET {', '.join(update_fields)} WHERE id = ?"
            conn.execute(sql, update_values)
            conn.commit()
        else:
            sql = f"UPDATE medical_appointments SET {', '.join(update_fields)} WHERE id = %s"
            with conn.cursor() as cursor:
                cursor.execute(sql, update_values)
                conn.commit()
        
        return {"success": True, "message": "預約已成功更新"}
    except Exception as e:
        print(f"[錯誤] 更新預約失敗: {e}")
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def extract_appointment_info(message):
    """從消息中提取預約資訊"""
    import re
    from datetime import datetime, timedelta
    
    info = {}
    
    # 提取病歷號
    patient_id_match = re.search(r'病歷號[：:]\s*([A-Z0-9]+)|([A-Z]\d{4,})', message.upper())
    if patient_id_match:
        info['patient_id'] = patient_id_match.group(1) or patient_id_match.group(2)
    
    # 提取姓名
    name_patterns = [
        r'姓名[：:]\s*([^\s，,。]+)',
        r'病患[：:]\s*([^\s，,。]+)',
        r'([張王李陳林黃劉吳周鄭趙錢孫李]{1,3}[^\s，,。]{0,5})',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, message)
        if match and len(match.group(1)) <= 10:
            info['patient_name'] = match.group(1)
            break
    
    # 提取電話
    phone_match = re.search(r'電話[：:]\s*([\d\-]+)|(\d{4}[\s\-]?\d{3}[\s\-]?\d{3})', message)
    if phone_match:
        phone = (phone_match.group(1) or phone_match.group(2)).replace('-', '').replace(' ', '')
        if len(phone) >= 8:
            info['patient_phone'] = phone
    
    # 提取科別
    departments = ['內科', '外科', '兒科', '婦產科', '骨科', '眼科', '耳鼻喉科', '皮膚科', '精神科', '復健科']
    for dept in departments:
        if dept in message:
            info['department'] = dept
            break
    
    # 提取醫師姓名
    doctor_match = re.search(r'醫師[：:]\s*([^\s，,。]+)|([^\s，,。]+醫師)', message)
    if doctor_match:
        doctor = doctor_match.group(1) or doctor_match.group(2)
        if '醫師' in doctor:
            doctor = doctor.replace('醫師', '')
        info['doctor_name'] = doctor
    
    # 提取日期
    date_patterns = [
        r'(\d{4}[\-\/]\d{1,2}[\-\/]\d{1,2})',
        r'(\d{1,2}月\d{1,2}日)',
        r'(明天|後天|大後天)',
        r'(\d{1,2}\/\d{1,2})',  # 月/日格式
    ]
    for pattern in date_patterns:
        match = re.search(pattern, message)
        if match:
            date_str = match.group(1)
            try:
                if '明天' in date_str:
                    date_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                elif '後天' in date_str:
                    date_str = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
                elif '大後天' in date_str:
                    date_str = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
                elif '月' in date_str and '日' in date_str:
                    # 處理中文日期格式
                    year = datetime.now().year
                    month = int(re.search(r'(\d+)月', date_str).group(1))
                    day = int(re.search(r'(\d+)日', date_str).group(1))
                    date_str = f"{year}-{month:02d}-{day:02d}"
                elif '/' in date_str and len(date_str.split('/')) == 2:
                    # 處理月/日格式
                    parts = date_str.split('/')
                    year = datetime.now().year
                    month = int(parts[0])
                    day = int(parts[1])
                    date_str = f"{year}-{month:02d}-{day:02d}"
                # 驗證日期格式
                datetime.strptime(date_str, '%Y-%m-%d')
                info['appointment_date'] = date_str
                break
            except (ValueError, AttributeError):
                continue
    
    # 提取時間
    time_match = re.search(r'時間[：:]\s*(\d{1,2}[:：]\d{2})|(\d{1,2}[:：]\d{2})|(\d{1,2}點)', message)
    if time_match:
        time_str = time_match.group(1) or time_match.group(2) or time_match.group(3)
        if '點' in time_str:
            hour = int(re.search(r'(\d+)', time_str).group(1))
            time_str = f"{hour:02d}:00"
        time_str = time_str.replace('：', ':')
        info['appointment_time'] = time_str
    
    # 提取症狀
    if '症狀' in message or '不舒服' in message or '問題' in message:
        # 嘗試提取症狀描述
        symptom_match = re.search(r'症狀[：:]\s*([^。]+)|不舒服[：:]\s*([^。]+)', message)
        if symptom_match:
            info['symptoms'] = symptom_match.group(1) or symptom_match.group(2)
    
    return info

@app.route("/api/chat", methods=["POST"])
def chat():
    """AI 聊天 API（整合資料庫查詢、創建和修改預約功能）"""
    global gemini_model
    
    if not gemini_model:
        return jsonify({
            "success": False, 
            "error": "AI 模型未初始化，請檢查 GEMINI_API_KEY 是否正確設置"
        }), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "請求數據為空"}), 400
        
        message = data.get("message", "").strip()
        if not message:
            return jsonify({"success": False, "error": "消息內容為空"}), 400
        
        username = session.get("user")
        if not username:
            return jsonify({"success": False, "error": "請先登入"}), 401
        
        print(f"[Gemini] 收到消息: {message}")
        
        # 識別用戶意圖
        create_keywords = ['預約', '掛號', '我要預約', '幫我預約', '預約門診', '我要掛號']
        update_keywords = ['修改', '更改', '改', '更新', '調整', '變更']
        query_keywords = ['查詢', '我的預約', '預約記錄', '查看', '查']
        
        is_create = any(keyword in message for keyword in create_keywords) and not any(k in message for k in update_keywords + query_keywords)
        is_update = any(keyword in message for keyword in update_keywords)
        is_query = any(keyword in message for keyword in query_keywords) or not (is_create or is_update)
        
        # 處理創建預約
        if is_create:
            appointment_info = extract_appointment_info(message)
            print(f"[AI] 提取的預約資訊: {appointment_info}")
            
            # 檢查必填欄位
            required_fields = ['patient_name', 'patient_phone', 'department', 'doctor_name', 'appointment_date', 'appointment_time']
            missing_fields = [field for field in required_fields if field not in appointment_info]
            
            if missing_fields:
                # 資訊不完整，讓 AI 詢問缺少的資訊
                missing_info = "缺少以下資訊：" + "、".join(missing_fields)
                enhanced_message = f"{message}\n\n{missing_info}\n請友善地詢問用戶缺少的資訊。"
            else:
                # 嘗試創建預約
                result = create_appointment_via_ai(username, appointment_info)
                if result['success']:
                    enhanced_message = f"{message}\n\n預約已成功創建！預約編號：{result['appointment_id']}\n請用友善的語氣告知用戶預約已成功，並提供預約詳情。"
                else:
                    enhanced_message = f"{message}\n\n創建預約時發生錯誤：{result['error']}\n請友善地告知用戶錯誤原因。"
        
        # 處理修改預約
        elif is_update:
            # 先查詢預約記錄
            appointments = query_appointments_by_keyword(username, "")
            if not appointments:
                enhanced_message = f"{message}\n\n（目前沒有找到任何預約記錄）\n請告知用戶沒有可修改的預約。"
            else:
                # 提取要修改的資訊
                update_info = extract_appointment_info(message)
                # 嘗試找到要修改的預約（根據病歷號、姓名或電話）
                target_appointment = None
                if update_info.get('patient_id'):
                    target_appointment = next((apt for apt in appointments if apt.get('patient_id') == update_info['patient_id']), None)
                elif update_info.get('patient_name'):
                    target_appointment = next((apt for apt in appointments if apt.get('patient_name') == update_info['patient_name']), None)
                elif update_info.get('patient_phone'):
                    target_appointment = next((apt for apt in appointments if apt.get('patient_phone') == update_info['patient_phone']), None)
                
                if target_appointment:
                    # 執行更新
                    result = update_appointment_via_ai(username, target_appointment['id'], update_info)
                    if result['success']:
                        enhanced_message = f"{message}\n\n預約已成功更新！\n請用友善的語氣告知用戶預約已成功修改。"
                    else:
                        enhanced_message = f"{message}\n\n更新預約時發生錯誤：{result['error']}\n請友善地告知用戶錯誤原因。"
                else:
                    # 提供預約列表讓用戶選擇
                    appointment_list = "\n".join([f"ID: {apt['id']}, {apt.get('patient_name', 'N/A')}, {apt.get('appointment_date', 'N/A')}" for apt in appointments[:5]])
                    enhanced_message = f"{message}\n\n找到以下預約記錄：\n{appointment_list}\n請詢問用戶要修改哪一筆預約。"
        
        # 處理查詢預約
        elif is_query:
            import re
            # 提取關鍵字
            patient_id_match = re.search(r'[A-Z0-9]{4,}', message.upper())
            phone_match = re.search(r'[\d\-]{8,}', message)
            
            keyword = ""
            if patient_id_match:
                keyword = patient_id_match.group()
            elif phone_match:
                keyword = phone_match.group().replace('-', '')
            
            appointments = query_appointments_by_keyword(username, keyword)
            
            if appointments:
                appointment_info = "\n\n以下是您的預約記錄：\n"
                for i, apt in enumerate(appointments[:5], 1):
                    appointment_info += f"\n預約 {i} (ID: {apt['id']}):\n"
                    if apt.get('patient_id'):
                        appointment_info += f"  病歷號: {apt['patient_id']}\n"
                    appointment_info += f"  病患姓名: {apt.get('patient_name', 'N/A')}\n"
                    appointment_info += f"  聯絡電話: {apt.get('patient_phone', 'N/A')}\n"
                    appointment_info += f"  科別: {apt.get('department', 'N/A')}\n"
                    appointment_info += f"  醫師: {apt.get('doctor_name', 'N/A')}\n"
                    appointment_info += f"  預約日期: {apt.get('appointment_date', 'N/A')}\n"
                    appointment_info += f"  預約時間: {apt.get('appointment_time', 'N/A')}\n"
                    appointment_info += f"  狀態: {apt.get('status', 'N/A')}\n"
                    if apt.get('symptoms'):
                        appointment_info += f"  症狀描述: {apt['symptoms']}\n"
                
                enhanced_message = f"{message}\n\n{appointment_info}"
            else:
                enhanced_message = f"{message}\n\n（目前沒有找到相關的預約記錄）"
        else:
            enhanced_message = message
        
        # 調用 Gemini API
        response = gemini_model.generate_content(enhanced_message)
        reply = response.text.strip()
        
        print(f"[Gemini] 回應: {reply[:100]}...")
        
        return jsonify({"success": True, "message": reply})
    except Exception as e:
        print(f"[錯誤] Gemini API 調用失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/clear-history", methods=["POST"])
def clear_history():
    """清除對話歷史（前端功能，後端無需處理）"""
    return jsonify({"success": True})
@app.route("/appointment/cancel/<int:id>", methods=["POST"])
@login_required
def cancel_appointment(id):
    conn = get_db_connection()
    if not conn: 
        return jsonify({"success": False, "error": "資料庫連接失敗"}), 500
    try:
        username = session.get("user")
        
        # 先檢查預約是否屬於當前用戶
        if USE_SQLITE:
            cursor = conn.execute("SELECT username FROM medical_appointments WHERE id=?", (id,))
            result = cursor.fetchone()
            if not result or dict(result)['username'] != username:
                return jsonify({"success": False, "error": "無權限取消此預約"}), 403
            conn.execute("UPDATE medical_appointments SET status='cancelled' WHERE id=?", (id,))
        else:
            with conn.cursor() as c:
                c.execute("SELECT username FROM medical_appointments WHERE id=%s", (id,))
                result = c.fetchone()
                if not result or result['username'] != username:
                    return jsonify({"success": False, "error": "無權限取消此預約"}), 403
                c.execute("UPDATE medical_appointments SET status='cancelled' WHERE id=%s", (id,))
        
        conn.commit()
        return jsonify({"success": True, "message": "預約已取消"})
    except Exception as e:
        print(f"取消預約錯誤: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally: 
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)