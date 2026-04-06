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
import sys

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

def ensure_column(conn, table_name, column_name, column_definition):
    """Add a column if it does not already exist."""
    existing_columns = {
        row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in existing_columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")

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
            owner_username VARCHAR(100),
            profile_id INTEGER,
            created_by_username VARCHAR(100),
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
        ensure_column(conn, "medical_appointments", "owner_username", "owner_username VARCHAR(100)")
        ensure_column(conn, "medical_appointments", "profile_id", "profile_id INTEGER")
        ensure_column(conn, "medical_appointments", "created_by_username", "created_by_username VARCHAR(100)")
        conn.execute("UPDATE medical_appointments SET owner_username = username WHERE owner_username IS NULL OR owner_username = ''")
        conn.execute("UPDATE medical_appointments SET created_by_username = username WHERE created_by_username IS NULL OR created_by_username = ''")
        
        # 建立索引以加速查詢
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON medical_appointments(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_owner_username ON medical_appointments(owner_username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profile_id ON medical_appointments(profile_id)")
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

        # 使用者資料表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(200) NOT NULL,
            name VARCHAR(100) DEFAULT '',
            phone VARCHAR(20) DEFAULT '',
            identity_id VARCHAR(20) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS care_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_username VARCHAR(50) NOT NULL,
            profile_name VARCHAR(100) NOT NULL,
            relationship VARCHAR(50) DEFAULT '',
            phone VARCHAR(20) DEFAULT '',
            identity_id VARCHAR(20) DEFAULT '',
            birth_date DATE,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_care_profiles_owner ON care_profiles(owner_username)")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS care_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_username VARCHAR(50) NOT NULL,
            linked_username VARCHAR(50) NOT NULL,
            note VARCHAR(255) DEFAULT '',
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(owner_username, linked_username)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_care_links_owner ON care_links(owner_username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_care_links_linked ON care_links(linked_username)")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(100) NOT NULL,
            owner_username VARCHAR(100),
            profile_id INTEGER,
            created_by_username VARCHAR(100),
            medication_name VARCHAR(120) NOT NULL,
            dosage VARCHAR(120) NOT NULL,
            frequency VARCHAR(120) NOT NULL,
            reminder_times VARCHAR(255) NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE,
            instructions TEXT DEFAULT '',
            precautions TEXT DEFAULT '',
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        ensure_column(conn, "medications", "owner_username", "owner_username VARCHAR(100)")
        ensure_column(conn, "medications", "profile_id", "profile_id INTEGER")
        ensure_column(conn, "medications", "created_by_username", "created_by_username VARCHAR(100)")
        ensure_column(conn, "medications", "instructions", "instructions TEXT DEFAULT ''")
        ensure_column(conn, "medications", "precautions", "precautions TEXT DEFAULT ''")
        conn.execute("UPDATE medications SET owner_username = username WHERE owner_username IS NULL OR owner_username = ''")
        conn.execute("UPDATE medications SET created_by_username = username WHERE created_by_username IS NULL OR created_by_username = ''")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_medications_owner ON medications(owner_username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_medications_profile ON medications(profile_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_medications_status ON medications(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_medications_start_date ON medications(start_date)")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS medication_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL,
            owner_username VARCHAR(100) NOT NULL,
            log_date DATE NOT NULL,
            reminder_time VARCHAR(10) NOT NULL,
            status VARCHAR(20) NOT NULL,
            note TEXT DEFAULT '',
            created_by_username VARCHAR(100),
            taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(medication_id, log_date, reminder_time)
        )
        """)
        ensure_column(conn, "medication_logs", "owner_username", "owner_username VARCHAR(100)")
        ensure_column(conn, "medication_logs", "note", "note TEXT DEFAULT ''")
        ensure_column(conn, "medication_logs", "created_by_username", "created_by_username VARCHAR(100)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_medication_logs_med_date ON medication_logs(medication_id, log_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_medication_logs_owner ON medication_logs(owner_username)")

        # 植入預設 admin 帳號（若尚未存在）
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO users (username, password_hash, name, phone, identity_id) VALUES (?, ?, ?, ?, ?)",
                ('admin', generate_password_hash('1234'), '系統管理員', '', '')
            )
            print("[成功] 預設 admin 帳號已建立")

        conn.commit()
        conn.close()
        print(f"[成功] SQLite 資料庫已就緒: {SQLITE_DB_FILE}")
    except Exception as e:
        print(f"[錯誤] SQLite 資料庫初始化失敗: {e}")

# 啟動時初始化資料庫
init_db()

def normalize_lang(value):
    return 'en' if str(value).lower() == 'en' else 'zh'

def get_request_lang(default='zh'):
    return normalize_lang(request.values.get('lang', default))

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

# === Medication Features ===
@app.route("/medication", methods=["GET", "POST"])
@login_required
def medication():
    username = session.get("user")
    manageable_people = get_manageable_people(username)
    default_target = request.args.get("target_profile") or (
        manageable_people[0]["target_value"] if manageable_people else f"user:{username}"
    )
    default_start = datetime.now().strftime("%Y-%m-%d")
    if request.method == "POST":
        form = request.form
        reminder_values = parse_reminder_times(form.get("reminder_times", ""))
        required_fields = [
            form.get("medication_name"),
            form.get("dosage"),
            form.get("frequency"),
            form.get("start_date"),
        ]
        if not all(required_fields) or not reminder_values:
            form_data = dict(form)
            form_data["target_profile"] = form.get("target_profile", default_target)
            return render_template(
                "medication.html",
                username=username,
                manageable_people=manageable_people,
                form_data=form_data,
                error="請完整填寫藥品、劑量、頻率、開始日期與提醒時間",
                edit_mode=False,
            )

        conn = get_db_connection()
        if not conn:
            return render_template(
                "medication.html",
                username=username,
                manageable_people=manageable_people,
                form_data=form,
                error="Database connection failed",
                edit_mode=False,
            )
        try:
            resolved_target = resolve_manageable_target(username, form.get("target_profile"))
            if not resolved_target:
                raise ValueError("請選擇有效的用藥對象")
            conn.execute(
                """INSERT INTO medications
                   (username, owner_username, profile_id, created_by_username, medication_name, dosage, frequency,
                    reminder_times, start_date, end_date, instructions, precautions, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                (
                    resolved_target["owner_username"],
                    resolved_target["owner_username"],
                    resolved_target.get("profile_id"),
                    username,
                    form.get("medication_name", "").strip(),
                    form.get("dosage", "").strip(),
                    form.get("frequency", "").strip(),
                    ",".join(reminder_values),
                    form.get("start_date"),
                    form.get("end_date") or None,
                    form.get("instructions", "").strip(),
                    form.get("precautions", "").strip(),
                )
            )
            conn.commit()
            return redirect(url_for("medication_list", success="用藥計畫已新增"))
        except Exception as e:
            form_data = dict(form)
            form_data["target_profile"] = form.get("target_profile", default_target)
            return render_template(
                "medication.html",
                username=username,
                manageable_people=manageable_people,
                form_data=form_data,
                error=f"新增失敗：{e}",
                edit_mode=False,
            )
        finally:
            conn.close()

    return render_template(
        "medication.html",
        username=username,
        manageable_people=manageable_people,
        form_data={"target_profile": default_target, "start_date": default_start},
        edit_mode=False,
    )

@app.route("/medication/edit/<int:medication_id>", methods=["GET", "POST"])
@login_required
def edit_medication(medication_id):
    username = session.get("user")
    medication_item = get_medication_with_access(medication_id, username)
    if not medication_item:
        return redirect(url_for("medication_list", error="找不到這筆用藥資料"))

    manageable_people = get_manageable_people(username)
    target_value = (
        f"profile:{medication_item['profile_id']}"
        if medication_item.get("profile_id")
        else f"user:{medication_item['owner_username']}"
    )

    if request.method == "POST":
        form = request.form
        reminder_values = parse_reminder_times(form.get("reminder_times", ""))
        required_fields = [
            form.get("medication_name"),
            form.get("dosage"),
            form.get("frequency"),
            form.get("start_date"),
        ]
        if not all(required_fields) or not reminder_values:
            form_data = dict(form)
            form_data["target_profile"] = form.get("target_profile", target_value)
            return render_template(
                "medication.html",
                username=username,
                manageable_people=manageable_people,
                form_data=form_data,
                error="請完整填寫藥品、劑量、頻率、開始日期與提醒時間",
                edit_mode=True,
                medication_id=medication_id,
            )

        conn = get_db_connection()
        if not conn:
            return redirect(url_for("medication_list", error="Database connection failed"))
        try:
            resolved_target = resolve_manageable_target(username, form.get("target_profile"))
            if not resolved_target:
                raise ValueError("請選擇有效的用藥對象")
            conn.execute(
                """UPDATE medications
                   SET username=?, owner_username=?, profile_id=?, created_by_username=?, medication_name=?, dosage=?,
                       frequency=?, reminder_times=?, start_date=?, end_date=?, instructions=?, precautions=?,
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    resolved_target["owner_username"],
                    resolved_target["owner_username"],
                    resolved_target.get("profile_id"),
                    username,
                    form.get("medication_name", "").strip(),
                    form.get("dosage", "").strip(),
                    form.get("frequency", "").strip(),
                    ",".join(reminder_values),
                    form.get("start_date"),
                    form.get("end_date") or None,
                    form.get("instructions", "").strip(),
                    form.get("precautions", "").strip(),
                    medication_id,
                )
            )
            conn.commit()
            return redirect(url_for("medication_list", success="用藥計畫已更新"))
        except Exception as e:
            form_data = dict(form)
            form_data["target_profile"] = form.get("target_profile", target_value)
            return render_template(
                "medication.html",
                username=username,
                manageable_people=manageable_people,
                form_data=form_data,
                error=f"更新失敗：{e}",
                edit_mode=True,
                medication_id=medication_id,
            )
        finally:
            conn.close()

    form_data = dict(medication_item)
    form_data["target_profile"] = target_value
    form_data["reminder_times"] = ", ".join(medication_item.get("reminder_list", []))
    return render_template(
        "medication.html",
        username=username,
        manageable_people=manageable_people,
        form_data=form_data,
        edit_mode=True,
        medication_id=medication_id,
    )

@app.route("/medication/archive/<int:medication_id>")
@login_required
def archive_medication(medication_id):
    medication_item = get_medication_with_access(medication_id, session.get("user"))
    if not medication_item:
        return redirect(url_for("medication_list", error="找不到這筆用藥資料"))
    conn = get_db_connection()
    if not conn:
        return redirect(url_for("medication_list", error="Database connection failed"))
    try:
        conn.execute(
            "UPDATE medications SET status = 'inactive', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (medication_id,)
        )
        conn.commit()
        return redirect(url_for("medication_list", success="用藥計畫已封存"))
    finally:
        conn.close()

@app.route("/medication/log/<int:medication_id>", methods=["POST"])
@login_required
def log_medication_status(medication_id):
    username = session.get("user")
    medication_item = get_medication_with_access(medication_id, username)
    if not medication_item:
        return redirect(url_for("medication_list", error="找不到這筆用藥資料"))

    log_date = request.form.get("log_date") or datetime.now().strftime("%Y-%m-%d")
    reminder_time = request.form.get("reminder_time", "").strip()
    status = request.form.get("status", "taken").strip().lower()
    note = request.form.get("note", "").strip()
    if reminder_time not in medication_item.get("reminder_list", []):
        return redirect(url_for("medication_list", error="提醒時間格式不正確"))
    if status not in {"taken", "skipped"}:
        return redirect(url_for("medication_list", error="用藥狀態不正確"))

    conn = get_db_connection()
    if not conn:
        return redirect(url_for("medication_list", error="Database connection failed"))
    try:
        conn.execute(
            """INSERT INTO medication_logs
               (medication_id, owner_username, log_date, reminder_time, status, note, created_by_username, taken_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(medication_id, log_date, reminder_time)
               DO UPDATE SET status=excluded.status, note=excluded.note, created_by_username=excluded.created_by_username,
                             taken_at=CURRENT_TIMESTAMP""",
            (
                medication_id,
                medication_item["owner_username"],
                log_date,
                reminder_time,
                status,
                note,
                username,
            )
        )
        conn.commit()
        message = "已標記為已服用" if status == "taken" else "已標記為略過"
        return redirect(url_for("medication_list", success=message))
    finally:
        conn.close()

@app.route("/medication/list")
@login_required
def medication_list():
    username = session.get("user")
    keyword = request.args.get("keyword", "").strip()
    try:
        medications = get_accessible_medications(username, keyword)
        today_schedule = build_today_medication_schedule(medications)
        summary = {
            "active_count": sum(1 for med in medications if med.get("status") == "active"),
            "today_reminders": len(today_schedule),
            "taken_count": sum(1 for item in today_schedule if item["status"] == "taken"),
            "due_count": sum(1 for item in today_schedule if item["status"] == "due"),
        }
        return render_template(
            "medication_list.html",
            username=username,
            medications=medications,
            today_schedule=today_schedule,
            summary=summary,
            keyword=keyword,
            success=request.args.get("success"),
            error=request.args.get("error"),
            today=datetime.now().strftime("%Y-%m-%d"),
            accessible_owners=get_accessible_owner_usernames(username),
        )
    except Exception as e:
        return render_template(
            "medication_list.html",
            username=username,
            medications=[],
            today_schedule=[],
            summary={"active_count": 0, "today_reminders": 0, "taken_count": 0, "due_count": 0},
            keyword=keyword,
            error=str(e),
            today=datetime.now().strftime("%Y-%m-%d"),
            accessible_owners=get_accessible_owner_usernames(username),
        )

# === AI 模型設定 ===
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

gemini_model = None

def save_gemini_api_key_to_env(api_key):
    """將 GEMINI_API_KEY 寫入 .env（存在則覆蓋，不存在則新增）。"""
    env_path = os.path.join(basedir, '.env')
    new_line = f"GEMINI_API_KEY={api_key}"

    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith('GEMINI_API_KEY='):
            lines[i] = new_line
            updated = True
            break

    if not updated:
        lines.append(new_line)

    with open(env_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines).rstrip() + '\n')

def is_set_api_key_command():
    """判斷是否執行設定 API key 的命令。"""
    args = sys.argv[1:]
    return "--set-api-key" in args or "set-key" in args
def resolve_gemini_api_key():
    """優先使用本次新輸入的 key；未輸入時才回退到既有設定。"""
    if is_set_api_key_command():
        return ""

    if __name__ == "__main__" and sys.stdin and sys.stdin.isatty():
        try:
            user_key = input("請輸入 Gemini API Key（直接按 Enter 使用既有設定）: ").strip()
            if user_key:
                os.environ["GEMINI_API_KEY"] = user_key
                return user_key
        except EOFError:
            pass

    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if key:
        return key

    return ""

def init_gemini_model():
    global gemini_model

    if is_set_api_key_command():
        return

    api_key = resolve_gemini_api_key()

    if not api_key:
        print("[警告] 未找到 GEMINI_API_KEY，AI 聊天功能將無法使用")
        return

    try:
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=medical_system_prompt)
        print("[成功] Gemini 醫療AI模型已初始化")
    except Exception as e:
        print(f"[錯誤] Gemini 模型初始化失敗: {e}")

def handle_set_api_key_command():
    """命令列指令：互動式輸入 API key 並寫入 .env。"""
    if not (sys.stdin and sys.stdin.isatty()):
        print("[錯誤] 目前不是互動式終端機，無法輸入 API key")
        return

    api_key = input("請輸入要儲存的 Gemini API Key: ").strip()
    if not api_key:
        print("[取消] 未輸入 API Key，未進行任何變更")
        return

    save_gemini_api_key_to_env(api_key)
    os.environ["GEMINI_API_KEY"] = api_key
    print("[成功] 已寫入 .env 的 GEMINI_API_KEY")

init_gemini_model()

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

def get_user_by_username(username):
    """從 SQLite 查詢使用者。"""
    conn = get_db_connection()
    if not conn: return None
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_accessible_owner_usernames(username):
    """Return owner accounts the current user can manage."""
    conn = get_db_connection()
    if not conn:
        return [username]
    try:
        owner_usernames = {username}
        rows = conn.execute(
            """SELECT owner_username
               FROM care_links
               WHERE linked_username = ? AND status = 'active'""",
            (username,)
        ).fetchall()
        owner_usernames.update(row["owner_username"] for row in rows)
        return sorted(owner_usernames)
    finally:
        conn.close()

def get_owner_linked_accounts(owner_username):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        rows = conn.execute(
            """SELECT cl.id, cl.linked_username, cl.note, cl.status, cl.created_at,
                      u.name AS linked_name, u.phone AS linked_phone
               FROM care_links cl
               LEFT JOIN users u ON u.username = cl.linked_username
               WHERE cl.owner_username = ?
               ORDER BY cl.created_at DESC""",
            (owner_username,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_owner_care_profiles(owner_username):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        rows = conn.execute(
            """SELECT *
               FROM care_profiles
               WHERE owner_username = ?
               ORDER BY created_at DESC, id DESC""",
            (owner_username,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_manageable_people(username):
    """Build selectable booking targets for the current user."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        targets = []
        owner_usernames = get_accessible_owner_usernames(username)
        for owner_username in owner_usernames:
            owner = conn.execute(
                "SELECT username, name, phone, identity_id FROM users WHERE username = ?",
                (owner_username,)
            ).fetchone()
            if owner:
                owner = dict(owner)
                owner_name = owner.get("name") or owner_username
                targets.append({
                    "target_value": f"user:{owner_username}",
                    "target_type": "user",
                    "owner_username": owner_username,
                    "profile_id": None,
                    "patient_name": owner_name,
                    "patient_phone": owner.get("phone", ""),
                    "patient_id": owner.get("identity_id", ""),
                    "label": f"{owner_name}（本人）" if owner_username == username else f"{owner_name}（{owner_username} 本人）",
                    "description": "我的帳號" if owner_username == username else f"由 {owner_username} 授權代辦"
                })

            profile_rows = conn.execute(
                """SELECT id, owner_username, profile_name, relationship, phone, identity_id, birth_date, notes
                   FROM care_profiles
                   WHERE owner_username = ?
                   ORDER BY created_at DESC, id DESC""",
                (owner_username,)
            ).fetchall()
            for row in profile_rows:
                profile = dict(row)
                relationship = profile.get("relationship") or "家人"
                targets.append({
                    "target_value": f"profile:{profile['id']}",
                    "target_type": "profile",
                    "owner_username": owner_username,
                    "profile_id": profile["id"],
                    "patient_name": profile.get("profile_name", ""),
                    "patient_phone": profile.get("phone", ""),
                    "patient_id": profile.get("identity_id", ""),
                    "relationship": relationship,
                    "birth_date": profile.get("birth_date", ""),
                    "notes": profile.get("notes", ""),
                    "label": f"{profile.get('profile_name', '')}（{relationship}）",
                    "description": "我的受照護對象" if owner_username == username else f"{owner_username} 家庭成員"
                })
        return targets
    finally:
        conn.close()

def resolve_manageable_target(username, target_value):
    targets = get_manageable_people(username)
    target_map = {target["target_value"]: target for target in targets}
    if target_value in target_map:
        return target_map[target_value]
    return target_map.get(f"user:{username}")

def get_appointment_with_access(apt_id, username):
    owner_usernames = get_accessible_owner_usernames(username)
    placeholders = ",".join(["?"] * len(owner_usernames))
    conn = get_db_connection()
    if not conn:
        return None
    try:
        row = conn.execute(
            f"""SELECT ma.*, cp.profile_name, cp.relationship
                FROM medical_appointments ma
                LEFT JOIN care_profiles cp ON cp.id = ma.profile_id
                WHERE ma.id = ? AND COALESCE(ma.owner_username, ma.username) IN ({placeholders})""",
            [apt_id] + owner_usernames
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_accessible_appointments(username, keyword=""):
    owner_usernames = get_accessible_owner_usernames(username)
    placeholders = ",".join(["?"] * len(owner_usernames))
    conn = get_db_connection()
    if not conn:
        return []
    try:
        sql = f"""
            SELECT ma.*, cp.profile_name, cp.relationship
            FROM medical_appointments ma
            LEFT JOIN care_profiles cp ON cp.id = ma.profile_id
            WHERE COALESCE(ma.owner_username, ma.username) IN ({placeholders})
        """
        params = list(owner_usernames)
        if keyword:
            sql += """
                AND (
                    ma.patient_id LIKE ? OR
                    ma.patient_name LIKE ? OR
                    ma.patient_phone LIKE ?
                )
            """
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        sql += " ORDER BY ma.appointment_date DESC, ma.appointment_time DESC"
        appointments = [dict(row) for row in conn.execute(sql, params).fetchall()]
        for apt in appointments:
            apt["owner_username"] = apt.get("owner_username") or apt.get("username")
            apt["created_by_username"] = apt.get("created_by_username") or apt.get("username")
            apt["booking_target"] = (
                f"{apt.get('profile_name')} ({apt.get('relationship') or 'family'})"
                if apt.get("profile_id")
                else "Self"
            )
            apt["managed_for_other"] = apt["owner_username"] != username
        return appointments
    finally:
        conn.close()

def parse_reminder_times(reminder_times):
    """Normalize reminder time text into sorted HH:MM values."""
    if not reminder_times:
        return []
    values = []
    for item in str(reminder_times).split(","):
        cleaned = item.strip()
        if not cleaned:
            continue
        try:
            values.append(datetime.strptime(cleaned, "%H:%M").strftime("%H:%M"))
        except ValueError:
            continue
    return sorted(set(values))

def get_medication_safety_info(medication_name, precautions=""):
    name = (medication_name or "").lower()
    hints = []
    safety_map = {
        "metformin": "服用後若持續噁心、嘔吐或食慾下降，請盡快回診評估。",
        "insulin": "注射胰島素後請留意低血糖，若冒冷汗、手抖或頭暈應立即補充糖分。",
        "warfarin": "服用抗凝血藥期間若有不明瘀青、血尿或黑便，應儘速就醫。",
        "aspirin": "阿斯匹靈與其他止痛消炎藥併用前請先詢問醫師，避免增加出血風險。",
        "ibuprofen": "止痛消炎藥建議飯後服用，若胃痛或黑便請停止使用並就醫。",
        "acetaminophen": "含普拿疼成分藥物避免重複服用，以免增加肝臟負擔。",
        "amoxicillin": "抗生素請依療程完成，勿自行提前停藥。",
        "antibiotic": "抗生素請依醫囑完成療程，不要因症狀改善就自行停藥。",
        "steroid": "類固醇藥物通常不建議自行突然停用，需依醫囑調整。",
        "prednisone": "類固醇通常不建議自行突然停用，若需停藥請先與醫師討論。",
        "atorvastatin": "降血脂藥若合併明顯肌肉痠痛或尿色變深，請盡快就醫。",
        "amlodipine": "降血壓藥可能造成頭暈，初期起身動作請放慢。 ",
    }
    for keyword, hint in safety_map.items():
        if keyword in name:
            hints.append(hint.strip())
    if precautions:
        hints.append(f"個別注意事項：{precautions}")
    if not hints:
        hints.append("首次使用新藥、出現紅疹、呼吸喘或明顯不適時，應停止自行加量並儘快聯繫醫師或藥師。")
    return hints[:3]

def get_medication_with_access(medication_id, username):
    owner_usernames = get_accessible_owner_usernames(username)
    placeholders = ",".join(["?"] * len(owner_usernames))
    conn = get_db_connection()
    if not conn:
        return None
    try:
        row = conn.execute(
            f"""SELECT m.*, cp.profile_name, cp.relationship
                FROM medications m
                LEFT JOIN care_profiles cp ON cp.id = m.profile_id
                WHERE m.id = ? AND COALESCE(m.owner_username, m.username) IN ({placeholders})""",
            [medication_id] + owner_usernames
        ).fetchone()
        if not row:
            return None
        medication = dict(row)
        medication["owner_username"] = medication.get("owner_username") or medication.get("username")
        medication["created_by_username"] = medication.get("created_by_username") or medication.get("username")
        medication["reminder_list"] = parse_reminder_times(medication.get("reminder_times"))
        medication["target_label"] = (
            f"{medication.get('profile_name')}（{medication.get('relationship') or '家人'}）"
            if medication.get("profile_id")
            else "自己"
        )
        medication["safety_info"] = get_medication_safety_info(
            medication.get("medication_name"), medication.get("precautions", "")
        )
        return medication
    finally:
        conn.close()

def get_medication_log_lookup(medication_ids, log_date):
    if not medication_ids:
        return {}
    placeholders = ",".join(["?"] * len(medication_ids))
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        rows = conn.execute(
            f"""SELECT medication_id, reminder_time, status, note, taken_at
                FROM medication_logs
                WHERE log_date = ? AND medication_id IN ({placeholders})""",
            [log_date] + medication_ids
        ).fetchall()
        lookup = {}
        for row in rows:
            entry = dict(row)
            lookup.setdefault(entry["medication_id"], {})[entry["reminder_time"]] = entry
        return lookup
    finally:
        conn.close()

def get_accessible_medications(username, keyword=""):
    owner_usernames = get_accessible_owner_usernames(username)
    placeholders = ",".join(["?"] * len(owner_usernames))
    conn = get_db_connection()
    if not conn:
        return []
    try:
        sql = f"""
            SELECT m.*, cp.profile_name, cp.relationship
            FROM medications m
            LEFT JOIN care_profiles cp ON cp.id = m.profile_id
            WHERE COALESCE(m.owner_username, m.username) IN ({placeholders})
        """
        params = list(owner_usernames)
        if keyword:
            sql += """
                AND (
                    m.medication_name LIKE ? OR
                    m.dosage LIKE ? OR
                    m.frequency LIKE ?
                )
            """
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        sql += " ORDER BY CASE WHEN m.status = 'active' THEN 0 ELSE 1 END, m.start_date DESC, m.id DESC"
        medications = [dict(row) for row in conn.execute(sql, params).fetchall()]
        today = datetime.now().strftime("%Y-%m-%d")
        log_lookup = get_medication_log_lookup([med["id"] for med in medications], today)
        for med in medications:
            med["owner_username"] = med.get("owner_username") or med.get("username")
            med["created_by_username"] = med.get("created_by_username") or med.get("username")
            med["reminder_list"] = parse_reminder_times(med.get("reminder_times"))
            med["target_label"] = (
                f"{med.get('profile_name')}（{med.get('relationship') or '家人'}）"
                if med.get("profile_id")
                else "自己"
            )
            med["today_logs"] = log_lookup.get(med["id"], {})
            med["today_taken_count"] = sum(1 for entry in med["today_logs"].values() if entry["status"] == "taken")
            med["daily_total"] = len(med["reminder_list"])
            med["adherence_ratio"] = (
                round((med["today_taken_count"] / med["daily_total"]) * 100)
                if med["daily_total"] else 0
            )
            med["safety_info"] = get_medication_safety_info(med.get("medication_name"), med.get("precautions", ""))
        return medications
    finally:
        conn.close()

def build_today_medication_schedule(medications):
    today = datetime.now().strftime("%Y-%m-%d")
    now_text = datetime.now().strftime("%H:%M")
    schedule = []
    for med in medications:
        if med.get("status") != "active":
            continue
        end_date = med.get("end_date")
        if end_date and end_date < today:
            continue
        start_date = med.get("start_date")
        if start_date and start_date > today:
            continue
        for reminder_time in med.get("reminder_list", []):
            log_entry = med.get("today_logs", {}).get(reminder_time)
            state = log_entry["status"] if log_entry else "pending"
            if state == "pending" and reminder_time < now_text:
                state = "due"
            schedule.append({
                "medication_id": med["id"],
                "medication_name": med["medication_name"],
                "dosage": med["dosage"],
                "frequency": med["frequency"],
                "target_label": med["target_label"],
                "owner_username": med["owner_username"],
                "reminder_time": reminder_time,
                "status": state,
                "note": log_entry.get("note", "") if log_entry else "",
            })
    schedule.sort(key=lambda item: (item["reminder_time"], item["medication_name"]))
    return schedule

def mask_identity_id(identity_id):
    """遮碼身分證號，如 A123456789 -> A12***789"""
    if not identity_id or len(identity_id) < 6:
        return identity_id or ''
    return identity_id[:3] + '***' + identity_id[-3:]

@app.route("/")
def welcome():
    return render_template("welcome.html")

@app.route("/home")
def index():
    doctors_map = get_doctors_by_department()
    lang = normalize_lang(request.args.get('lang', 'zh'))
    return render_template("index.html", username=session.get("user"), doctor_options=doctors_map, lang=lang)

@app.route("/appointment/cancel/<int:apt_id>")
@login_required
def cancel_appointment(apt_id):
    lang = get_request_lang()
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('appointment_list', error="Database connection failed", lang=lang))
    try:
        apt = get_appointment_with_access(apt_id, session.get('user'))
        if not apt:
            return redirect(url_for('appointment_list', error="You do not have access to this appointment", lang=lang))
        conn.execute(
            "UPDATE medical_appointments SET status = 'canceled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (apt_id,)
        )
        conn.commit()
        return redirect(url_for('appointment_list', success="Appointment updated", lang=lang))
    finally:
        conn.close()

@app.route("/appointment/edit/<int:apt_id>", methods=["GET", "POST"])
@login_required
def edit_appointment(apt_id):
    lang = get_request_lang()
    apt = get_appointment_with_access(apt_id, session.get('user'))
    if not apt:
        return redirect(url_for('appointment_list', error="You do not have access to this appointment", lang=lang))

    conn = get_db_connection()
    doctors_map = get_doctors_by_department()
    min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    manageable_people = get_manageable_people(session.get('user'))
    target_value = f"profile:{apt['profile_id']}" if apt.get('profile_id') else f"user:{apt.get('owner_username') or apt.get('username')}"

    if request.method == "POST":
        form = request.form
        if not all([form.get("patient_name"), form.get("patient_phone"), form.get("department"),
                    form.get("doctor_name"), form.get("appointment_date"), form.get("appointment_time")]):
            conn.close()
            form_data = dict(form)
            form_data["target_profile"] = form.get("target_profile", target_value)
            return render_template(
                "appointment.html",
                username=session.get('user'),
                lang=lang,
                min_date=min_date,
                doctor_options=doctors_map,
                error="Please complete all required fields",
                form_data=form_data,
                edit_mode=True,
                apt_id=apt_id,
                manageable_people=manageable_people
            )

        try:
            resolved_target = resolve_manageable_target(session.get('user'), form.get("target_profile"))
            if not resolved_target:
                raise ValueError("Invalid booking target")
            conn.execute("""
                UPDATE medical_appointments
                SET username=?, owner_username=?, profile_id=?, created_by_username=?, patient_id=?, patient_name=?, patient_phone=?, department=?,
                    doctor_name=?, appointment_date=?, appointment_time=?, symptoms=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (
                resolved_target["owner_username"],
                resolved_target["owner_username"],
                resolved_target.get("profile_id"),
                session.get('user'),
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
            return redirect(url_for('appointment_list', success="Appointment updated", lang=lang))
        except Exception as e:
            form_data = dict(form)
            form_data["target_profile"] = form.get("target_profile", target_value)
            return render_template(
                "appointment.html",
                username=session.get('user'),
                lang=lang,
                min_date=min_date,
                doctor_options=doctors_map,
                error=f"Update failed: {e}",
                form_data=form_data,
                edit_mode=True,
                apt_id=apt_id,
                manageable_people=manageable_people
            )
        finally:
            conn.close()

    conn.close()
    form_data = dict(apt)
    form_data["target_profile"] = target_value
    return render_template(
        "appointment.html",
        username=session.get('user'),
        lang=lang,
        min_date=min_date,
        doctor_options=doctors_map,
        form_data=form_data,
        edit_mode=True,
        apt_id=apt_id,
        manageable_people=manageable_people
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    """登入頁，使用 templates/login.html。"""
    msg = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
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
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        identity_id = request.form.get("identity_id", "").strip()
        conn = get_db_connection()
        if not conn:
            msg = "資料庫連線失敗"
        else:
            try:
                conn.execute(
                    "INSERT INTO users (username, password_hash, name, phone, identity_id) VALUES (?, ?, ?, ?, ?)",
                    (username, generate_password_hash(password), name, phone, identity_id)
                )
                conn.commit()
                msg = "註冊成功！請登入"
            except Exception as e:
                if 'UNIQUE' in str(e):
                    msg = "帳號已存在"
                else:
                    msg = f"註冊失敗：{e}"
            finally:
                conn.close()
    return render_template("register.html", message=msg)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("welcome"))

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    username = session.get("user")
    success_msg = request.args.get("success", "")
    error_msg = request.args.get("error", "")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        conn = get_db_connection()
        if conn:
            try:
                conn.execute(
                    "UPDATE users SET name=?, phone=? WHERE username=?",
                    (name, phone, username)
                )
                conn.commit()
                success_msg = "Profile updated successfully"
            except Exception as e:
                error_msg = f"Update failed: {e}"
            finally:
                conn.close()
        else:
            error_msg = "Database connection failed"

    user = get_user_by_username(username) or {}
    masked_id = mask_identity_id(user.get('identity_id', ''))
    return render_template(
        "profile.html",
        username=username,
        user=user,
        masked_id=masked_id,
        success=success_msg,
        error=error_msg,
        care_profiles=get_owner_care_profiles(username),
        linked_accounts=get_owner_linked_accounts(username),
        accessible_owners=get_accessible_owner_usernames(username)
    )

@app.route("/family/profile/add", methods=["POST"])
@login_required
def add_care_profile():
    username = session.get("user")
    form = request.form
    conn = get_db_connection()
    if not conn:
        return redirect(url_for("profile", error="Database connection failed"))
    try:
        profile_name = form.get("profile_name", "").strip()
        if not profile_name:
            return redirect(url_for("profile", error="Please complete all required fields"))
        conn.execute(
            """INSERT INTO care_profiles (owner_username, profile_name, relationship, phone, identity_id, birth_date, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                username,
                profile_name,
                form.get("relationship", "").strip(),
                form.get("phone", "").strip(),
                form.get("identity_id", "").strip(),
                form.get("birth_date", "").strip() or None,
                form.get("notes", "").strip()
            )
        )
        conn.commit()
        return redirect(url_for("profile", success="Care recipient removed"))
    finally:
        conn.close()

@app.route("/family/profile/delete/<int:profile_id>", methods=["POST"])
@login_required
def delete_care_profile(profile_id):
    username = session.get("user")
    conn = get_db_connection()
    if not conn:
        return redirect(url_for("profile", error="Database connection failed"))
    try:
        conn.execute(
            "DELETE FROM care_profiles WHERE id = ? AND owner_username = ?",
            (profile_id, username)
        )
        conn.execute(
            "UPDATE medical_appointments SET profile_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE profile_id = ? AND owner_username = ?",
            (profile_id, username)
        )
        conn.commit()
        return redirect(url_for("profile", success="Care recipient removed"))
    finally:
        conn.close()

@app.route("/family/link/add", methods=["POST"])
@login_required
def add_family_link():
    username = session.get("user")
    linked_username = request.form.get("linked_username", "").strip()
    note = request.form.get("note", "").strip()
    if not linked_username:
        return redirect(url_for("profile", error="Please complete all required fields"))
    if linked_username == username:
        return redirect(url_for("profile", error="You cannot link your own account"))
    linked_user = get_user_by_username(linked_username)
    if not linked_user:
        return redirect(url_for("profile", error="Database connection failed"))

    conn = get_db_connection()
    if not conn:
        return redirect(url_for("profile", error="Database connection failed"))
    try:
        conn.execute(
            """INSERT INTO care_links (owner_username, linked_username, note, status)
               VALUES (?, ?, ?, 'active')
               ON CONFLICT(owner_username, linked_username)
               DO UPDATE SET note=excluded.note, status='active'""",
            (username, linked_username, note)
        )
        conn.commit()
        return redirect(url_for("profile", success="Linked account authorized"))
    finally:
        conn.close()

@app.route("/family/link/delete/<int:link_id>", methods=["POST"])
@login_required
def delete_family_link(link_id):
    username = session.get("user")
    conn = get_db_connection()
    if not conn:
        return redirect(url_for("profile", error="Database connection failed"))
    try:
        conn.execute(
            "DELETE FROM care_links WHERE id = ? AND owner_username = ?",
            (link_id, username)
        )
        conn.commit()
        return redirect(url_for("profile", success="Linked account authorized"))
    finally:
        conn.close()

# === Appointment Features ===
@app.route("/appointment", methods=["GET", "POST"])
@login_required
def appointment():
    lang = get_request_lang()
    min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    doctors_map = get_doctors_by_department()
    manageable_people = get_manageable_people(session.get("user"))
    default_target = request.args.get("target_profile") or (manageable_people[0]["target_value"] if manageable_people else f"user:{session.get('user')}")
    if request.method == "POST":
        form = request.form
        conn = get_db_connection()
        if not conn:
            return render_template(
                "appointment.html",
                username=session.get("user"),
                lang=lang,
                error="Database connection failed",
                form_data=form,
                min_date=min_date,
                doctor_options=doctors_map,
                manageable_people=manageable_people
            )

        try:
            resolved_target = resolve_manageable_target(session.get("user"), form.get("target_profile"))
            if not resolved_target:
                raise ValueError("Please choose a valid service target")

            sql = """INSERT INTO medical_appointments
                    (username, owner_username, profile_id, created_by_username, patient_id, patient_name, patient_phone, department, doctor_name,
                     appointment_date, appointment_time, symptoms, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')"""
            symptoms = form.get("symptoms", "").strip() or None
            patient_id = form.get("patient_id", "").strip() or None
            conn.execute(sql, (
                resolved_target["owner_username"],
                resolved_target["owner_username"],
                resolved_target.get("profile_id"),
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
            success_msg = "Appointment created successfully!" if lang == 'en' else "Appointment created"
            return redirect(url_for("appointment_list", success=success_msg, lang=lang))
        except Exception as e:
            form_data = dict(form)
            form_data["target_profile"] = form.get("target_profile", default_target)
            return render_template(
                "appointment.html",
                username=session.get("user"),
                lang=lang,
                error=f"Appointment failed: {str(e)}",
                form_data=form_data,
                min_date=min_date,
                doctor_options=doctors_map,
                manageable_people=manageable_people
            )
        finally:
            conn.close()
    return render_template(
        "appointment.html",
        username=session.get("user"),
        lang=lang,
        min_date=min_date,
        doctor_options=doctors_map,
        manageable_people=manageable_people,
        form_data={"target_profile": default_target}
    )

@app.route("/appointment/list")
@login_required
def appointment_list():
    lang = normalize_lang(request.args.get('lang', 'zh'))
    username = session.get("user")
    try:
        appointments = get_accessible_appointments(username)
        for apt in appointments:
            if apt.get('appointment_date') and not isinstance(apt['appointment_date'], str):
                apt['appointment_date'] = apt['appointment_date'].strftime('%Y-%m-%d')
            if apt.get('appointment_time') and not isinstance(apt['appointment_time'], str):
                apt['appointment_time'] = apt['appointment_time'].strftime('%H:%M')
            if apt.get('created_at') and not isinstance(apt['created_at'], str):
                apt['created_at'] = apt['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        return render_template(
            "appointment_list.html",
            username=username,
            lang=lang,
            appointments=appointments,
            success=request.args.get("success"),
            error=request.args.get("error"),
            accessible_owners=get_accessible_owner_usernames(username)
        )
    except Exception as e:
        return render_template(
            "appointment_list.html",
            username=username,
            lang=lang,
            appointments=[],
            error=str(e),
            accessible_owners=get_accessible_owner_usernames(username)
        )

# === AI 模型設定 ===
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

gemini_model = None

def save_gemini_api_key_to_env(api_key):
    """將 GEMINI_API_KEY 寫入 .env（存在則覆蓋，不存在則新增）。"""
    env_path = os.path.join(basedir, '.env')
    new_line = f"GEMINI_API_KEY={api_key}"

    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith('GEMINI_API_KEY='):
            lines[i] = new_line
            updated = True
            break

    if not updated:
        lines.append(new_line)

    with open(env_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines).rstrip() + '\n')

def is_set_api_key_command():
    """判斷是否執行設定 API key 的命令。"""
    args = sys.argv[1:]
    return "--set-api-key" in args or "set-key" in args
def resolve_gemini_api_key():
    """優先使用本次新輸入的 key；未輸入時才回退到既有設定。"""
    if is_set_api_key_command():
        return ""

    if __name__ == "__main__" and sys.stdin and sys.stdin.isatty():
        try:
            user_key = input("請輸入 Gemini API Key（直接按 Enter 使用既有設定）: ").strip()
            if user_key:
                os.environ["GEMINI_API_KEY"] = user_key
                return user_key
        except EOFError:
            pass

    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if key:
        return key

    return ""

def init_gemini_model():
    global gemini_model

    if is_set_api_key_command():
        return

    api_key = resolve_gemini_api_key()

    if not api_key:
        print("[警告] 未找到 GEMINI_API_KEY，AI 聊天功能將無法使用")
        return

    try:
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=medical_system_prompt)
        print("[成功] Gemini 醫療AI模型已初始化")
    except Exception as e:
        print(f"[錯誤] Gemini 模型初始化失敗: {e}")

def handle_set_api_key_command():
    """命令列指令：互動式輸入 API key 並寫入 .env。"""
    if not (sys.stdin and sys.stdin.isatty()):
        print("[錯誤] 目前不是互動式終端機，無法輸入 API key")
        return

    api_key = input("請輸入要儲存的 Gemini API Key: ").strip()
    if not api_key:
        print("[取消] 未輸入 API Key，未進行任何變更")
        return

    save_gemini_api_key_to_env(api_key)
    os.environ["GEMINI_API_KEY"] = api_key
    print("[成功] 已寫入 .env 的 GEMINI_API_KEY")

init_gemini_model()

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

def get_user_by_username(username):
    """從 SQLite 查詢使用者。"""
    conn = get_db_connection()
    if not conn: return None
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def query_appointments_by_keyword(username, keyword=""):
    """Query appointments the user can manage."""
    try:
        appointments = get_accessible_appointments(username, keyword)
        for apt in appointments:
            if apt.get('appointment_date') and not isinstance(apt['appointment_date'], str):
                apt['appointment_date'] = apt['appointment_date'].strftime('%Y-%m-%d')
            if apt.get('appointment_time') and not isinstance(apt['appointment_time'], str):
                apt['appointment_time'] = apt['appointment_time'].strftime('%H:%M')
        return appointments
    except Exception as e:
        print(f"[error] Failed to query appointments: {e}")
        return []


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
    is_english = False
    
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

        lang = str(data.get("lang", "zh")).lower()
        if lang not in ("zh", "en"):
            lang = "zh"
        is_english = lang == "en"

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
                        "message": (f"Appointment created successfully. ID: {result['appointment_id']}" if is_english else f"預約已成功創建，編號：{result['appointment_id']}")
                    })
                else:
                    return jsonify({"success": False, "error": (f"Failed to create appointment: {result['error']}" if is_english else f"創建預約時發生錯誤：{result['error']}")})
        
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
        
        if is_english:
            enhanced_message = (
                "Please answer everything in English. Override any previous language preference. "
                "Translate system notices and warnings into natural English as well.\n\n"
            ) + enhanced_message

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
        
        common_diseases_responses_by_lang = common_diseases_responses
        if is_english:
            common_diseases_responses_by_lang = {
                '感冒': "For common cold symptoms, prioritize rest, hydration, and monitoring fever. Seek medical care if symptoms worsen or persist.",
                '高血壓': "For hypertension, monitor blood pressure regularly, follow medication plans, reduce sodium, exercise, and follow up with your doctor.",
                '頭痛': "Headache can come from tension, migraine, dehydration, or fatigue. Seek care for sudden severe headache or neurological symptoms.",
                '胃痛': "Stomach pain may be due to indigestion, reflux, or gastritis. Avoid irritating foods and seek care for severe or persistent pain.",
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
                local_response = common_diseases_responses_by_lang.get(disease)
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
                    friendly_msg = "AI quota is currently exhausted. Please try again later. If you need an appointment, click the top-right Appointment button." if is_english else "AI 服務目前配額已用完，請稍後再試。如需預約門診，請點擊右上角「預約門診」按鈕。"
                    return jsonify({"success": False, "error": friendly_msg}), 429
            else:
                # 其他錯誤：如果有本地化回答則使用，否則顯示錯誤
                print(f"[錯誤] Gemini API 調用失敗: {error_str}")
                import traceback
                traceback.print_exc()
                if local_response:
                    return jsonify({"success": True, "message": local_response})
                return jsonify({"success": False, "error": (f"AI service is temporarily unavailable: {error_str}" if is_english else f"AI 服務暫時無法使用：{error_str}")}), 500
    
    except Exception as e:
        # 處理整個函數的意外錯誤
        print(f"[錯誤] 聊天 API 發生未預期錯誤: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": (f"System error: {str(e)}" if is_english else f"系統錯誤：{str(e)}")}), 500

@app.route("/api/clear-history", methods=["POST"])
def clear_history():
    return jsonify({"success": True})



if __name__ == "__main__":
    if is_set_api_key_command():
        handle_set_api_key_command()
    else:
        app.run(debug=True)















