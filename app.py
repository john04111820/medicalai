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
    """登入頁，沿用 c5e7c7e 版本的表單樣式與提示文字。"""
    login_html = """<!DOCTYPE html><html><head><title>登入</title></head>
    <body style="font-family: Arial; background:#eef1f7; display:flex; justify-content:center; align-items:center; height:100vh;">
    <div style="background:white; padding:30px; border-radius:10px; width:320px; text-align:center;">
        <h2>登入</h2>
        <form method="POST" action="/login">
            <input type="text" name="username" placeholder="帳號" required style="width:100%; padding:10px; margin:8px 0;"><br>
            <input type="password" name="password" placeholder="密碼" required style="width:100%; padding:10px; margin:8px 0;"><br>
            <button type="submit" style="width:100%; padding:10px; background:#5563DE; color:white; border:none; border-radius:5px; cursor:pointer;">登入</button>
        </form>
        <p style="color:red;">{{ message }}</p>
        <a href="/register" style="color:#5563DE; text-decoration:none;">註冊新帳號</a> | <a href="/" style="color:#888; text-decoration:none;">暫不登入 (回首頁)</a>
    </div>
    </body></html>"""
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
    """簡易註冊頁（與 c5e7c7e 版本一致，使用記憶體暫存）。"""
    register_html = """<!DOCTYPE html><html><head><title>註冊</title></head>
    <body style="font-family: Arial; background:#eef1f7; display:flex; justify-content:center; align-items:center; height:100vh;">
    <div style="background:white; padding:30px; border-radius:10px; width:320px; text-align:center;">
        <h2>註冊</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="帳號" required style="width:100%; padding:10px; margin:8px 0;"><br>
            <input type="password" name="password" placeholder="密碼" required style="width:100%; padding:10px; margin:8px 0;"><br>
            <button type="submit" style="width:100%; padding:10px; background:#5563DE; color:white; border:none; border-radius:5px; cursor:pointer;">註冊</button>
        </form>
        <p style="color:red;">{{ message }}</p>
        <a href="/login" style="color:#5563DE; text-decoration:none;">返回登入</a>
    </div>
    </body></html>"""
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

# === 預約功能 ===
@app.route("/appointment", methods=["GET", "POST"])
@login_required
def appointment():
    min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    if request.method == "POST":
        form = request.form
        conn = get_db_connection()
        if not conn: 
            return render_template("appointment.html", username=session.get("user"), 
                                 error="無法連線到資料庫", form_data=form, min_date=min_date)
        
        try:
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
                                 error=f"資料庫錯誤: {str(e)}", form_data=form, min_date=min_date)
        finally: 
            conn.close()
    return render_template("appointment.html", username=session.get("user"), min_date=min_date)

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
    return jsonify({"success": True})

@app.route("/appointment/cancel/<int:id>", methods=["POST"])
@login_required
def cancel_appointment(id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "資料庫連接失敗"}), 500
    try:
        username = session.get("user")
        # 檢查權限
        cursor = conn.execute("SELECT username FROM medical_appointments WHERE id=?", (id,))
        result = cursor.fetchone()
        if not result or dict(result)['username'] != username:
            return jsonify({"success": False, "error": "無權限取消此預約"}), 403
        
        conn.execute("UPDATE medical_appointments SET status='cancelled' WHERE id=?", (id,))
        conn.commit()
        return jsonify({"success": True, "message": "預約已取消"})
    except Exception as e:
        print(f"取消預約錯誤: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally: 
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)