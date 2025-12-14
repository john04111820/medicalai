
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,              -- 真实姓名
    phone VARCHAR(20) NOT NULL,              -- 联络电话
    identity_id VARCHAR(20) NOT NULL UNIQUE, -- 身份证号
    username VARCHAR(50) NOT NULL UNIQUE,    -- 登录用户名
    password_hash VARCHAR(200) NOT NULL,     -- 密码哈希值
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**medical_appointments表 (预约表)**
```sql
CREATE TABLE medical_appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(100) NOT NULL,          -- 关联用户
    patient_id VARCHAR(50),                  -- 病历号(选填)
    patient_name VARCHAR(100) NOT NULL,      -- 病患姓名
    patient_phone VARCHAR(20) NOT NULL,      -- 联络电话
    department VARCHAR(100) NOT NULL,        -- 科别
    doctor_name VARCHAR(100) NOT NOT NULL,          -- 医师姓名
    appointment_date DATE NOT NULL,          -- 预约日期
    appointment_time TIME NOT NULL,          -- 预约时间
    symptoms TEXT,                           -- 症状描述(选填)
    status VARCHAR(20) DEFAULT 'pending',    -- 状态
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**doctors表 (医师表)**
```sql
CREATE TABLE doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department VARCHAR(100) NOT NULL,        -- 科别
    doctor_name VARCHAR(100) NOT NULL,       -- 医师姓名
    shift VARCHAR(20) NOT NULL,              -- 班别(morning/afternoon)
    start_time TIME NOT NULL,                -- 开始时间
    end_time TIME NOT NULL                   -- 结束时间
);
```

#### 6.1.2 索引设计

```sql
-- 提高查询效率的索引
CREATE INDEX idx_username ON medical_appointments(username);
CREATE INDEX idx_appointment_date ON medical_appointments(appointment_date);
CREATE INDEX idx_patient_id ON medical_appointments(patient_id);
CREATE INDEX idx_doctor_dept ON doctors(department);
```

#### 6.1.3 数据关系

```
users (1) ───< (N) medical_appointments
  用户可以有多个预约

medical_appointments (N) ───> (1) doctors
  预约关联一位医师（通过doctor_name）
```

### 6.2 数据字典

#### users表字段说明
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK, AUTO_INCREMENT | 用户ID |
| name | VARCHAR(100) | NOT NULL | 真实姓名 |
| phone | VARCHAR(20) | NOT NULL | 联络电话 |
| identity_id | VARCHAR(20) | UNIQUE, NOT NULL | 身份证号 |
| username | VARCHAR(50) | UNIQUE, NOT NULL | 登录用户名 |
| password_hash | VARCHAR(200) | NOT NULL | 加密后的密码 |
| created_at | TIMESTAMP | DEFAULT NOW | 注册时间 |

#### medical_appointments表字段说明
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK, AUTO_INCREMENT | 预约ID |
| username | VARCHAR(100) | NOT NULL | 用户名（外键） |
| patient_id | VARCHAR(50) | NULL | 病历号 |
| patient_name | VARCHAR(100) | NOT NULL | 病患姓名 |
| patient_phone | VARCHAR(20) | NOT NULL | 联络电话 |
| department | VARCHAR(100) | NOT NULL | 科别 |
| doctor_name | VARCHAR(100) | NOT NULL | 医师姓名 |
| appointment_date | DATE | NOT NULL | 预约日期 |
| appointment_time | TIME | NOT NULL | 预约时间 |
| symptoms | TEXT | NULL | 症状描述 |
| status | VARCHAR(20) | DEFAULT 'pending' | 预约状态 |
| created_at | TIMESTAMP | DEFAULT NOW | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW | 更新时间 |

#### doctors表字段说明
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PK, AUTO_INCREMENT | 医师ID |
| department | VARCHAR(100) | NOT NULL | 科别 |
| doctor_name | VARCHAR(100) | NOT NULL | 医师姓名 |
| shift | VARCHAR(20) | NOT NULL | 班别 |
| start_time | TIME | NOT NULL | 开始时间 |
| end_time | TIME | NOT NULL | 结束时间 |

### 6.3 数据验证规则

1. **用户注册验证**:
   - 用户名和身份证号不能重复
   - 密码需进行哈希加密存储
   
2. **预约创建验证**:
   - 日期必须是未来日期
   - 时间在09:00-21:00之间
   - 科别和医师必须匹配

3. **数据完整性**:
   - 外键引用保持一致性
   - 必填字段不能为空

## 第七节、执行设计追溯

### 7.1 需求到设计的追溯

| 需求编号 | 需求描述 | 对应设计组件 |
|---------|---------|-------------|
| FR-UM-001 | 用户注册 | `register()` 路由 + users表 |
| FR-UM-002 | 用户登录 | `login()` 路由 + session管理 |
| FR-AM-001 | 表单预约 | `appointment()` 路由 + appointment.html |
| FR-AM-002 | AI预约 | `create_appointment_via_ai()` + `/api/chat` |
| FR-AM-003 | 查询预约 | `appointment_list()` 路由 |
| FR-AI-001 | 文字对话 | `/api/chat` + Gemini整合 |
| FR-AI-002 | 语音交互 | `/api/transcribe` + Whisper整合 |
| FR-AC-001 | 长辈模式 | JavaScript模式切换 + CSS样式 |

### 7.2 设计验证

通过以下方式验证设计的正确性：
1. **代码审查**: 确保代码符合设计规范
2. **单元测试**: 测试各个模块功能
3. **集成测试**: 测试模块间交互
4. **用户测试**: 验证界面和交互设计

---

# 第四章、系统实作

## 第一节、目的说明

本章节详细说明医疗AI智能预约系统的具体实现过程，包括开发环境配置、核心功能实现、API接口设计和关键代码说明。

## 第二节、系统实作说明

### 2.1 开发环境配置

#### 2.1.1 Python环境
```bash
# Python版本
Python 3.8+

# 虚拟环境创建
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

#### 2.1.2 依赖包安装
```bash
pip install Flask
pip install Werkzeug
pip install google-generativeai
pip install openai-whisper
pip install torch torchaudio
pip install python-dotenv
pip install gunicorn
```

完整的`requirements.txt`:
```
Flask
gunicorn
Werkzeug
google-generativeai
openai-whisper
torch
torchaudio
numpy
ffmpeg-python
python-dotenv
pymysql
```

#### 2.1.3 环境变量配置
创建`.env`文件：
```
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2.2 数据库初始化

运行数据库初始化脚本：
```bash
python init_sqlite_db.py
```

该脚本会：
1. 创建`medical_appointments.db`数据库文件
2. 创建三个数据表（users、medical_appointments、doctors）
3. 插入初始医师数据
4. 创建索引优化查询性能

### 2.3 核心功能实现

#### 2.3.1 用户认证系统

**密码加密**:
```python
from werkzeug.security import generate_password_hash, check_password_hash

# 注册时加密密码
hashed_password = generate_password_hash(password)

# 登录时验证密码
check_password_hash(user['password_hash'], password)
```

**会话管理**:
```python
from flask import session

# 登录成功后设置会话
session["user"] = username

# 登录验证装饰器
@login_required
def some_route():
    # 只有登录用户才能访问
```

#### 2.3.2 AI语音识别实现

**Whisper模型加载**:
```python
import whisper

whisper_model = whisper.load_model("base")
result = whisper_model.transcribe(audio_path, language="zh", fp16=False)
text = result["text"].strip()
```

**�音数据处理**:
```python
@app.route("/api/transcribe", methods=["POST"])
def transcribe_audio():
    # 1. 接收前端上传的音频文件
    audio_file = request.files["audio"]
    
    # 2. 保存到临时文件
    temp_path = os.path.join(tempfile.gettempdir(), "recording.webm")
    audio_file.save(temp_path)
    
    # 3. 使用Whisper转录
    model = get_whisper_model()
    result = model.transcribe(temp_path, language="zh", fp16=False)
    
    # 4. 返回转录文字
    return jsonify({"success": True, "text": result["text"]})
```

#### 2.3.3 Gemini AI整合

**模型初始化**:
```python
import google.generativeai as genai

# 配置API密钥
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# 创建带系统提示词的模型
medical_system_prompt = """你是一位专业的医疗AI助理..."""
gemini_model = genai.GenerativeModel(
    'gemini-2.0-flash', 
    system_instruction=medical_system_prompt
)
```

**对话处理**:
```python
@app.route("/api/chat", methods=["POST"])
def chat():
    message = request.json["message"]
    
    # 识别用户意图
    if "预约" in message:
        # 处理预约逻辑
        appointment_info = extract_appointment_info(message)
        if all_fields_complete:
            create_appointment_via_ai(username, appointment_info)
        else:
            # 询问缺失信息
            
    # 调用Gemini API
    response = gemini_model.generate_content(message)
    return jsonify({"success": True, "message": response.text})
```

#### 2.3.4 信息提取算法

使用正则表达式从自然语言中提取预约信息：

```python
def extract_appointment_info(message):
    info = {}
    
    # 提取病历号
    patient_id_match = re.search(r'病歷號[：:]\\s*([A-Z0-9]+)', message.upper())
    if patient_id_match:
        info['patient_id'] = patient_id_match.group(1)
    
    # 提取姓名
    name_match = re.search(r'姓名[：:]\\s*([^\\s，,。]+)', message)
    if name_match:
        info['patient_name'] = name_match.group(1)
    
    # 提取电话
    phone_match = re.search(r'電話[：:]\\s*([\\d\\-]+)', message)
    if phone_match:
        info['patient_phone'] = phone_match.group(1)
    
    # 提取科别
    departments = ['内科', '外科', '儿科', ...]
    for dept in departments:
        if dept in message:
            info['department'] = dept
            break
    
    # 提取日期（支持多种格式）
    if '明天' in message:
        info['appointment_date'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    # ... 其他日期格式
    
    return info
```

#### 2.3.5 预约管理实现

**创建预约**:
```python
@app.route("/appointment", methods=["POST"])
@login_required
def appointment():
    form = request.form
    
    # 获取用户信息自动填充
    user_info = get_user_info(session["user"])
    
    # 插入数据库
    conn.execute("""
        INSERT INTO medical_appointments 
        (username, patient_id, patient_name, patient_phone, 
         department, doctor_name, appointment_date, appointment_time, symptoms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session["user"],
        form.get("patient_id"),
        user_info['name'],
        user_info['phone'],
        form["department"],
        form["doctor_name"],
        form["appointment_date"],
        form.get("appointment_time", "09:00"),
        form.get("symptoms")
    ))
    conn.commit()
    
    return redirect(url_for("appointment_list"))
```

**查询预约**:
```python
@app.route("/appointment/list")
@login_required
def appointment_list():
    username = session["user"]
    
    # 查询该用户的所有预约
    cursor = conn.execute("""
        SELECT * FROM medical_appointments 
        WHERE username=? 
        ORDER BY appointment_date DESC, appointment_time DESC
    """, (username,))
    
    appointments = [dict(row) for row in cursor.fetchall()]
    
    return render_template("appointment_list.html", 
                         appointments=appointments)
```

### 2.4 前端實現

#### 2.4.1 语音录音功能
```javascript
let mediaRecorder = null;
let audioChunks = [];

micButton.addEventListener('click', async () => {
    if (!isRecording) {
        // 获取麦克风权限
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        // 创建录音器
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });
        
        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };
        
       mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            await sendAudioToServer(audioBlob);
        };
        
        mediaRecorder.start();
        isRecording = true;
    } else {
        mediaRecorder.stop();
        isRecording = false;
    }
});
```

#### 2.4.2 AI对话功能
```javascript
async function sendMessage() {
    const message = textInput.value.trim();
    
    // 显示用户消息
    addMessageToChat('user', message);
    
    // 调用后端API
    const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message })
    });
    
    const data = await response.json();
    
    // 显示AI回复
    addMessageToChat('assistant', data.message);
}
```

#### 2.4.3 对话历史保存
```javascript
function saveChatHistory() {
    const messages = [];
    document.querySelectorAll('.message').forEach(msg => {
        const role = msg.classList.contains('user-message') ? 'user' : 'assistant';
        const content = msg.querySelector('.message-text').textContent;
        messages.push({ role, content });
    });
    localStorage.setItem('chatHistory', JSON.stringify(messages));
}

function loadChatHistory() {
    const savedHistory = localStorage.getItem('chatHistory');
    if (savedHistory) {
        const messages = JSON.parse(savedHistory);
        messages.forEach(msg => {
            addMessageToChat(msg.role, msg.content);
        });
    }
}
```

#### 2.4.4 长辈模式切换
```javascript
modeToggleBtn.addEventListener('click', () => {
    is
