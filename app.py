from flask import Flask, render_template_string, request, redirect, url_for, session, render_template, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import whisper
import os
import tempfile
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
import re

print("="*50)
print("啟動應用程式 (純 SQLite 版)")
print("="*50)

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

app = Flask(__name__)
app.secret_key = "supersecretkey"

# === 資料庫設定 ===
SQLITE_DB_FILE = os.path.join(basedir, 'medical_appointments.db')

def get_db_connection():
    """獲取 SQLite 資料庫連接"""
    try:
        conn = sqlite3.connect(SQLITE_DB_FILE)
        conn.row_factory = sqlite3.Row  # 讓結果可以像字典一樣訪問
        return conn
    except Exception as e:
        print(f"[錯誤] 資料庫連線失敗: {e}")
        return None

def init_db():
    """初始化 SQLite 資料庫表結構"""
    try:
        conn = get_db_connection()
        if not conn: return
        
        cursor = conn.cursor()
        
        # 建立資料表
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
        
        # 建立索引以加速查詢
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON medical_appointments(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointment_date ON medical_appointments(appointment_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_patient_id ON medical_appointments(patient_id)")

        # 醫師表：每科兩位醫師，早/下午分流
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department VARCHAR(100) NOT NULL,
            doctor_name VARCHAR(100) NOT NULL,
            shift VARCHAR(20) NOT NULL, -- morning / afternoon
            start_time TIME NOT NULL,
            end_time TIME NOT NULL
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doctor_dept ON doctors(department)")

        doctor_seed = {
            "內科": [("張內晨", "morning"), ("李內昕", "afternoon")],
            "外科": [("王外晨", "morning"), ("陳外昕", "afternoon")],
            "兒科": [("林兒晨", "morning"), ("黃兒昕", "afternoon")],
            "婦產科": [("周婦晨", "morning"), ("趙婦昕", "afternoon")],
            "骨科": [("吳骨晨", "morning"), ("鄭骨昕", "afternoon")],
            "眼科": [("許眼晨", "morning"), ("郭眼昕", "afternoon")],
            "耳鼻喉科": [("洪耳晨", "morning"), ("邱耳昕", "afternoon")],
            "皮膚科": [("何膚晨", "morning"), ("柯膚昕", "afternoon")],
            "精神科": [("施心晨", "morning"), ("簡心昕", "afternoon")],
            "復健科": [("蔡復晨", "morning"), ("曾復昕", "afternoon")],
        }

        cursor.execute("SELECT COUNT(*) FROM doctors")
        doctor_count = cursor.fetchone()[0]
        if doctor_count == 0:
            for dept, doctors in doctor_seed.items():
                for name, shift in doctors:
                    start, end = ("09:00", "15:00") if shift == "morning" else ("15:00", "21:00")
                    cursor.execute(
                        "INSERT INTO doctors (department, doctor_name, shift, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
                        (dept, name, shift, start, end)
                    )
            print("[成功] 預設醫師資料已建立")
        
        conn.commit()
        conn.close()
        print(f"[成功] SQLite 資料庫已就緒: {SQLITE_DB_FILE}")
    except Exception as e:
        print(f"[錯誤] SQLite 資料庫初始化失敗: {e}")

# 啟動時初始化資料庫
init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_doctors_by_department():
    """回傳 {department: [doctor rows]} 的映射。"""
    conn = get_db_connection()
    if not conn: return {}
    try:
        cursor = conn.execute(
            "SELECT department, doctor_name, shift, start_time, end_time FROM doctors ORDER BY department, shift"
        )
        result = {}
        for row in cursor.fetchall():
            dept = row['department']
            result.setdefault(dept, []).append(dict(row))
        return result
    finally:
        conn.close()

def is_time_in_range(time_str, start="09:00", end="21:00"):
    """檢查時間是否在營業時間內（含邊界）。格式 HH:MM"""
    try:
        t = datetime.strptime(time_str, "%H:%M").time()
        start_t = datetime.strptime(start, "%H:%M").time()
        end_t = datetime.strptime(end, "%H:%M").time()
        return start_t <= t <= end_t
    except Exception:
        return False

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
            whisper_model = whisper.load_model("medium")
            print("[成功] Whisper 模型已載入")
        except Exception as e:
            print(f"[錯誤] Whisper 模型載入失敗: {e}")
    return whisper_model

users = {"admin": generate_password_hash("1234")}

@app.route("/")
def welcome():
    return render_template("welcome.html")

@app.route("/home")
def index():
    doctors_map = get_doctors_by_department()
    return render_template("index.html", username=session.get("user"), doctor_options=doctors_map)

@app.route("/appointment/cancel/<int:apt_id>")
@login_required
def cancel_appointment(apt_id):
    conn = get_db_connection()
    # 檢查是否為該用戶的預約 We need to verify ownership
    cursor = conn.execute("SELECT username FROM medical_appointments WHERE id = ?", (apt_id,))
    apt = cursor.fetchone()
    
    if apt and apt['username'] == session.get('user'):
        conn.execute("UPDATE medical_appointments SET status = 'canceled' WHERE id = ?", (apt_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('appointment_list', success="預約已成功取消"))
    
    conn.close()
    return redirect(url_for('appointment_list', error="無法取消該預約"))

@app.route("/appointment/edit/<int:apt_id>", methods=["GET", "POST"])
@login_required
def edit_appointment(apt_id):
    conn = get_db_connection()
    
    # 檢查所有權
    cursor = conn.execute("SELECT * FROM medical_appointments WHERE id = ?", (apt_id,))
    apt = cursor.fetchone()
    
    if not apt or apt['username'] != session.get('user'):
        conn.close()
        return redirect(url_for('appointment_list', error="無法編輯該預約"))
        
    doctors_map = get_doctors_by_department()
    min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    if request.method == "POST":
        form = request.form
        
        # 簡單驗證
        if not all([form.get("patient_name"), form.get("patient_phone"), form.get("department"), 
                    form.get("doctor_name"), form.get("appointment_date"), form.get("appointment_time")]):
             conn.close()
             return render_template("appointment.html", 
                                  username=session.get('user'), 
                                  min_date=min_date,
                                  doctor_options=doctors_map,
                                  error="請填寫所有必填欄位",
                                  form_data=form,
                                  edit_mode=True,  # 標記為編輯模式
                                  apt_id=apt_id)

        try:
             conn.execute("""
                UPDATE medical_appointments 
                SET patient_id=?, patient_name=?, patient_phone=?, department=?, 
                    doctor_name=?, appointment_date=?, appointment_time=?, symptoms=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (
                form.get("patient_id"),
                form.get("patient_name"),
                form.get("patient_phone"),
                form.get("department"),
                form.get("doctor_name"),
                form.get("appointment_date"),
                form.get("appointment_time"),
                form.get("symptoms"),
                apt_id
            ))
             conn.commit()
             conn.close()
             return redirect(url_for('appointment_list', success="預約已成功修改"))
        except Exception as e:
             conn.close()
             return render_template("appointment.html", 
                                  username=session.get('user'), 
                                  min_date=min_date, 
                                  doctor_options=doctors_map, 
                                  error="修改失敗，請稍後再試",
                                  form_data=form,
                                  edit_mode=True,
                                  apt_id=apt_id)

    # GET 請求：顯示表單並帶入現有資料
    conn.close()
    return render_template("appointment.html", 
                         username=session.get('user'), 
                         min_date=min_date, 
                         doctor_options=doctors_map,
                         form_data=apt,  # 直接使用 apt row 作為初始資料
                         edit_mode=True,
                         apt_id=apt_id)


@app.route("/login", methods=["GET", "POST"])
def login():
    """登入頁，使用 templates/login.html。"""
    msg = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users and check_password_hash(users[username], password):
            session["user"] = username
            return redirect(url_for("index"))
        msg = "帳號或密碼錯誤"
    return render_template("login.html", message=msg)

@app.route("/register", methods=["GET","POST"])
def register():
    """註冊頁，使用 templates/register.html。"""
    msg = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users:
            msg = "帳號已存在"
        else:
            users[username] = generate_password_hash(password)
            msg = "註冊成功！請登入"
    return render_template("register.html", message=msg)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("welcome"))

# === 預約功能 ===
@app.route("/appointment", methods=["GET", "POST"])
@login_required
def appointment():
    min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    doctors_map = get_doctors_by_department()
    if request.method == "POST":
        form = request.form
        conn = get_db_connection()
        if not conn: 
            return render_template("appointment.html", username=session.get("user"), 
                                 error="無法連線到資料庫", form_data=form, min_date=min_date, doctor_options=doctors_map)
        
        try:
            # 檢查時間是否在營業時間 (09:00-21:00) - 已移除限制
            appt_time = form.get("appointment_time", "")
            # if not is_time_in_range(appt_time):
            #     return render_template("appointment.html", username=session.get("user"),
            #                          error="預約時間需介於 09:00 至 21:00", form_data=form, min_date=min_date,
            #                          doctor_options=doctors_map)

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
            success_msg = "預約成功！"
            
            return redirect(url_for("appointment_list", success=success_msg))
        except Exception as e:
            print(f"資料庫寫入錯誤: {e}")
            return render_template("appointment.html", username=session.get("user"), 
                                 error=f"資料庫錯誤: {str(e)}", form_data=form, min_date=min_date,
                                 doctor_options=doctors_map)
        finally: 
            conn.close()
    return render_template("appointment.html", username=session.get("user"), min_date=min_date, doctor_options=doctors_map)

@app.route("/appointment/list")
@login_required
def appointment_list():
    conn = get_db_connection()
    if not conn: 
        return render_template("appointment_list.html", username=session.get("user"), 
                             appointments=[], error="無法連線到資料庫")
    try:
        username = session.get("user")
        # SQLite 查詢
        cursor = conn.execute(
            "SELECT * FROM medical_appointments WHERE username=? ORDER BY appointment_date DESC, appointment_time DESC", 
            (username,)
        )
        # 將 Row 對象轉換為字典
        appointments = [dict(row) for row in cursor.fetchall()]
        
        # 格式化日期時間
        for apt in appointments:
            if apt.get('appointment_date'):
                # 如果不是字串才轉換，SQLite有時存字串有時存物件
                if not isinstance(apt['appointment_date'], str):
                    apt['appointment_date'] = apt['appointment_date'].strftime('%Y-%m-%d')
            if apt.get('appointment_time'):
                if not isinstance(apt['appointment_time'], str):
                    apt['appointment_time'] = apt['appointment_time'].strftime('%H:%M')
            if apt.get('created_at'):
                if not isinstance(apt['created_at'], str):
                    apt['created_at'] = apt['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return render_template("appointment_list.html", username=username, 
                             appointments=appointments, success=request.args.get("success"))
    except Exception as e:
        return render_template("appointment_list.html", username=session.get("user"), 
                             appointments=[], error=str(e))
    finally: 
        conn.close()

# === AI 輔助函數 ===

def query_appointments_by_keyword(username, keyword=""):
    """根據關鍵字查詢預約記錄（支援病歷號、姓名、電話）"""
    conn = get_db_connection()
    if not conn: return []
    
    try:
        if keyword:
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
        else:
            # 查詢所有預約
            cursor = conn.execute(
                """SELECT * FROM medical_appointments 
                   WHERE username = ?
                   ORDER BY appointment_date DESC, appointment_time DESC""",
                (username,)
            )
        
        appointments = [dict(row) for row in cursor.fetchall()]
        
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
        try:
            appointment_datetime = datetime.strptime(f"{appointment_data['appointment_date']} {appointment_data['appointment_time']}", "%Y-%m-%d %H:%M")
            if appointment_datetime < datetime.now():
                return {"success": False, "error": "預約時間不能是過去時間"}
            # if not is_time_in_range(appointment_data['appointment_time']):
            #    return {"success": False, "error": "預約時間需介於 09:00 至 21:00"}
        except ValueError:
            return {"success": False, "error": "日期或時間格式錯誤"}
        
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
        cursor = conn.execute("SELECT username FROM medical_appointments WHERE id=?", (appointment_id,))
        result = cursor.fetchone()
        if not result or dict(result)['username'] != username:
            return {"success": False, "error": "找不到該預約記錄或無權限修改"}
        
        # 構建更新 SQL
        update_fields = []
        update_values = []
        
        allowed_fields = ['patient_id', 'patient_name', 'patient_phone', 'department', 
                         'doctor_name', 'appointment_date', 'appointment_time', 'symptoms', 'status']
        
        for field in allowed_fields:
            if field in update_data:
                update_fields.append(f"{field} = ?")
                update_values.append(update_data[field])
        
        if not update_fields:
            return {"success": False, "error": "沒有要更新的欄位"}
        
        update_values.append(appointment_id)
        
        sql = f"UPDATE medical_appointments SET {', '.join(update_fields)} WHERE id = ?"
        conn.execute(sql, update_values)
        conn.commit()
        
        return {"success": True, "message": "預約已成功更新"}
    except Exception as e:
        print(f"[錯誤] 更新預約失敗: {e}")
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def extract_appointment_info(message):
    """從消息中提取預約資訊"""
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
                    year = datetime.now().year
                    month = int(re.search(r'(\d+)月', date_str).group(1))
                    day = int(re.search(r'(\d+)日', date_str).group(1))
                    date_str = f"{year}-{month:02d}-{day:02d}"
                elif '/' in date_str and len(date_str.split('/')) == 2:
                    parts = date_str.split('/')
                    year = datetime.now().year
                    month = int(parts[0])
                    day = int(parts[1])
                    date_str = f"{year}-{month:02d}-{day:02d}"
                
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
        symptom_match = re.search(r'症狀[：:]\s*([^。]+)|不舒服[：:]\s*([^。]+)', message)
        if symptom_match:
            info['symptoms'] = symptom_match.group(1) or symptom_match.group(2)
    
    return info

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
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass
    except Exception as e:
        print(f"[錯誤] 語音轉錄失敗: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

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
        if not data: return jsonify({"success": False, "error": "請求數據為空"}), 400
        
        message = data.get("message", "").strip()
        if not message: return jsonify({"success": False, "error": "消息內容為空"}), 400
        
        username = session.get("user")
        if not username: return jsonify({"success": False, "error": "請先登入"}), 401
        
        print(f"[Gemini] 收到消息: {message}")
        
        # 識別用戶意圖
        create_keywords = ['預約', '掛號', '我要預約', '幫我預約', '預約門診', '我要掛號']
        update_keywords = ['修改', '更改', '改', '更新', '調整', '變更']
        query_keywords = ['查詢', '我的預約', '預約記錄', '查看', '查']
        
        is_create = any(keyword in message for keyword in create_keywords) and not any(k in message for k in update_keywords + query_keywords)
        is_update = any(keyword in message for keyword in update_keywords)
        is_query = any(keyword in message for keyword in query_keywords) or not (is_create or is_update)
        
        enhanced_message = message

        if is_create:
            appointment_info = extract_appointment_info(message)
            print(f"[AI] 提取的預約資訊: {appointment_info}")
            
            required_fields = ['patient_name', 'patient_phone', 'department', 'doctor_name', 'appointment_date', 'appointment_time']
            missing_fields = [field for field in required_fields if field not in appointment_info]
            
            if missing_fields:
                # 資料不全時才請 Gemini 協助詢問缺漏
                missing_info = "缺少以下資訊：" + "、".join(missing_fields)
                enhanced_message = f"{message}\n\n{missing_info}\n請友善地詢問用戶缺少的資訊。"
            else:
                # 資料完整：直接建立預約並回傳，不再進入 AI 追問
                result = create_appointment_via_ai(username, appointment_info)
                if result['success']:
                    return jsonify({
                        "success": True,
                        "message": f"預約已成功創建，編號：{result['appointment_id']}"
                    })
                else:
                    return jsonify({"success": False, "error": f"創建預約時發生錯誤：{result['error']}"})
        
        elif is_update:
            appointments = query_appointments_by_keyword(username, "")
            if not appointments:
                enhanced_message = f"{message}\n\n（目前沒有找到任何預約記錄）\n請告知用戶沒有可修改的預約。"
            else:
                update_info = extract_appointment_info(message)
                target_appointment = None
                if update_info.get('patient_id'):
                    target_appointment = next((apt for apt in appointments if apt.get('patient_id') == update_info['patient_id']), None)
                elif update_info.get('patient_name'):
                    target_appointment = next((apt for apt in appointments if apt.get('patient_name') == update_info['patient_name']), None)
                elif update_info.get('patient_phone'):
                    target_appointment = next((apt for apt in appointments if apt.get('patient_phone') == update_info['patient_phone']), None)
                
                if target_appointment:
                    result = update_appointment_via_ai(username, target_appointment['id'], update_info)
                    if result['success']:
                        enhanced_message = f"{message}\n\n預約已成功更新！\n請用友善的語氣告知用戶預約已成功修改。"
                    else:
                        enhanced_message = f"{message}\n\n更新預約時發生錯誤：{result['error']}\n請友善地告知用戶錯誤原因。"
                else:
                    appointment_list = "\n".join([f"ID: {apt['id']}, {apt.get('patient_name', 'N/A')}, {apt.get('appointment_date', 'N/A')}" for apt in appointments[:5]])
                    enhanced_message = f"{message}\n\n找到以下預約記錄：\n{appointment_list}\n請詢問用戶要修改哪一筆預約。"
        
        elif is_query:
            patient_id_match = re.search(r'[A-Z0-9]{4,}', message.upper())
            phone_match = re.search(r'[\d\-]{8,}', message)
            
            keyword = ""
            if patient_id_match: keyword = patient_id_match.group()
            elif phone_match: keyword = phone_match.group().replace('-', '')
            
            appointments = query_appointments_by_keyword(username, keyword)
            
            if appointments:
                appointment_info = "\n\n以下是您的預約記錄：\n"
                for i, apt in enumerate(appointments[:5], 1):
                    appointment_info += f"\n預約 {i} (ID: {apt['id']}):\n"
                    if apt.get('patient_id'): appointment_info += f"  病歷號: {apt['patient_id']}\n"
                    appointment_info += f"  病患姓名: {apt.get('patient_name', 'N/A')}\n"
                    appointment_info += f"  聯絡電話: {apt.get('patient_phone', 'N/A')}\n"
                    appointment_info += f"  科別: {apt.get('department', 'N/A')}\n"
                    appointment_info += f"  醫師: {apt.get('doctor_name', 'N/A')}\n"
                    appointment_info += f"  預約日期: {apt.get('appointment_date', 'N/A')}\n"
                    appointment_info += f"  預約時間: {apt.get('appointment_time', 'N/A')}\n"
                    appointment_info += f"  狀態: {apt.get('status', 'N/A')}\n"
                    if apt.get('symptoms'): appointment_info += f"  症狀描述: {apt['symptoms']}\n"
                enhanced_message = f"{message}\n\n{appointment_info}"
            else:
                enhanced_message = f"{message}\n\n（目前沒有找到相關的預約記錄）"
        
        # 常見疾病資訊的本地化回答（當 API 配額用盡時使用）
        common_diseases_responses = {
            '感冒': """**感冒的常見症狀：**
• 流鼻水、鼻塞
• 打噴嚏
• 喉嚨痛或咳嗽
• 輕微發燒（通常低於 38.5°C）
• 頭痛、身體痠痛
• 疲勞、食慾不振

**處理方式：**
• 多休息，保持充足睡眠
• 多喝溫水，補充水分
• 可用溫鹽水漱口緩解喉嚨痛
• 避免接觸冷空氣，注意保暖
• 症狀嚴重或持續超過一週，建議就醫

**何時需要看醫生：**
• 高燒超過 38.5°C
• 症狀持續超過 7-10 天未改善
• 出現呼吸困難、胸痛等嚴重症狀
• 兒童、長者或慢性病患者應及早就醫""",
            '高血壓': """**高血壓注意事項：**
• 定期測量血壓，記錄數值
• 遵循醫師指示服藥，不可自行停藥
• 控制體重，維持健康 BMI
• 規律運動（每週至少 150 分鐘中等強度運動）

**飲食建議：**
• 低鈉飲食：每日鹽分攝取少於 6 公克
• 多攝取蔬果、全穀類
• 減少加工食品、高脂肪食物
• 限制酒精攝取
• 可適量攝取富含鉀的食物（如香蕉、菠菜）

**生活習慣：**
• 戒菸、避免二手菸
• 減少壓力，學習放鬆技巧
• 充足睡眠（7-9 小時）
• 定期回診追蹤""",
            '頭痛': """**頭痛可能原因：**
• 壓力性頭痛（最常見）
• 偏頭痛
• 睡眠不足或過度疲勞
• 脫水
• 眼睛疲勞
• 鼻竇炎
• 頸部肌肉緊繃

**何時需要看醫生：**
• 突然劇烈頭痛（如雷擊般）
• 頭痛伴隨發燒、頸部僵硬
• 頭痛伴隨視力模糊、意識改變
• 頭痛頻率或強度突然改變
• 50 歲以上首次出現嚴重頭痛
• 頭痛影響日常生活超過 3 天

**緩解方式：**
• 休息、放鬆
• 適度按摩太陽穴、頸部
• 冷敷或熱敷
• 保持充足水分
• 避免過度使用止痛藥（可能造成反彈性頭痛）""",
            '胃痛': """**胃痛可能原因：**
• 消化不良
• 胃食道逆流
• 胃炎
• 壓力或焦慮
• 飲食不當（過油、過辣、過量）

**緩解方式：**
• 少量多餐，細嚼慢嚥
• 避免刺激性食物（咖啡、酒精、辛辣）
• 飯後不要立即躺下
• 可適量飲用溫水或薑茶
• 放鬆心情，減少壓力

**何時需要就醫：**
• 劇烈疼痛或持續超過數小時
• 伴隨嘔血、黑便
• 體重不明原因下降
• 吞嚥困難
• 疼痛影響日常生活
• 症狀反覆發作超過 2 週""",
        }
        
        # 檢查是否為常見疾病問題，如果是且 API 可能配額用盡，使用本地化回答
        message_lower = message.lower()
        disease_keywords = {
            '感冒': ['感冒', '流鼻水', '鼻塞', '打噴嚏', '咳嗽'],
            '高血壓': ['高血壓', '血壓'],
            '頭痛': ['頭痛', '頭疼'],
            '胃痛': ['胃痛', '胃疼', '胃不舒服']
        }
        
        local_response = None
        for disease, keywords in disease_keywords.items():
            if any(kw in message_lower for kw in keywords):
                local_response = common_diseases_responses.get(disease)
                break
        
        # 嘗試調用 Gemini API
        try:
            response = gemini_model.generate_content(enhanced_message)
            reply = response.text.strip()
            print(f"[Gemini] 回應: {reply[:100]}...")
            return jsonify({"success": True, "message": reply})
        except Exception as e:
            error_str = str(e)
            # 檢查是否為配額/速率限制錯誤
            if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower() or "Resource exhausted" in error_str:
                print(f"[警告] Gemini API 配額/速率限制：{error_str}")
                # 如果有本地化回答，使用它；否則顯示友善提示
                if local_response:
                    return jsonify({"success": True, "message": local_response})
                else:
                    friendly_msg = "AI 服務目前配額已用完，請稍後再試。如需預約門診，請點擊右上角「預約門診」按鈕。"
                    return jsonify({"success": False, "error": friendly_msg}), 429
            else:
                # 其他錯誤：如果有本地化回答則使用，否則顯示錯誤
                print(f"[錯誤] Gemini API 調用失敗: {error_str}")
                import traceback
                traceback.print_exc()
                if local_response:
                    return jsonify({"success": True, "message": local_response})
                return jsonify({"success": False, "error": f"AI 服務暫時無法使用：{error_str}"}), 500
    
    except Exception as e:
        # 處理整個函數的意外錯誤
        print(f"[錯誤] 聊天 API 發生未預期錯誤: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"系統錯誤：{str(e)}"}), 500

@app.route("/api/clear-history", methods=["POST"])
def clear_history():
    return jsonify({"success": True})



if __name__ == "__main__":
    app.run(debug=True)