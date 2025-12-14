SeniorMode = !isSeniorMode;
    if (isSeniorMode) {
        document.body.classList.add('senior-mode');
        // 隐藏复杂UI，显示大按钮
    } else {
        document.body.classList.remove('senior-mode');
    }
});
```

## 第三节、应用程式介面API

### 3.1 API端点设计

#### 3.1.1 用户认证API

**注册 - POST /register**
- 请求参数: name, phone, identity_id, username, password
- 响应: HTML页面（成功/失败消息）

**登录 - POST /login**
- 请求参数: username, password
- 响应: 重定向到主页或返回错误消息

**登出 - GET /logout**
- 响应: 重定向到欢迎页

#### 3.1.2 预约管理API

**创建预约 - POST /appointment**
- 请求参数: patient_id, department, doctor_name, appointment_date, appointment_time, symptoms
- 响应: 重定向到预约列表

**查询预约列表 - GET /appointment/list**
- 响应: HTML页面显示所有预约

**修改预约 - GET/POST /appointment/edit/<apt_id>**
- GET: 显示编辑表单
- POST: 提交修改后的数据

**取消预约 - GET /appointment/cancel/<apt_id>**
- 响应: 更新状态为canceled，重定向到列表

#### 3.1.3 AI交互API

**语音转文字 - POST /api/transcribe**
```json
// 请求
Content-Type: multipart/form-data
Body: audio file (webm format)

// 响应
{
  "success": true,
  "text": "转录的文字内容",
  "ai_response": "AI的回复（可选）"
}
```

**AI聊天 - POST /api/chat**
```json
// 请求
{
  "message": "用户发送的消息"
}

// 响应（成功）
{
  "success": true,
  "message": "AI的回复内容"
}

// 响应（失败）
{
  "success": false,
  "error": "错误信息"
}
```

**清除对话历史 - POST /api/clear-history**
```json
// 响应
{
  "success": true
}
```

### 3.2 API调用示例

#### 3.2.1 前端调用语音转文字API
```javascript
const formData = new FormData();
formData.append('audio', audioBlob, 'recording.webm');

const response = await fetch('/api/transcribe', {
    method: 'POST',
    body: formData
});

const data = await response.json();
if (data.success) {
    console.log('转录文字:', data.text);
}
```

#### 3.2.2 前端调用聊天API
```javascript
const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: '我想预约内科' })
});

const data = await response.json();
if (data.success) {
    console.log('AI回复:', data.message);
}
```

## 第四节、程式原始码

### 4.1 核心模块代码

#### 4.1.1 数据库连接模块
```python
# 文件: app.py (部分)

import sqlite3
import os

SQLITE_DB_FILE = os.path.join(basedir, 'medical_appointments.db')

def get_db_connection():
    """获取 SQLite 数据库连接"""
    try:
        conn = sqlite3.connect(SQLITE_DB_FILE)
        conn.row_factory = sqlite3.Row  # 让结果可以像字典一样访问
        return conn
    except Exception as e:
        print(f"[错误] 数据库连线失败: {e}")
        return None
```

#### 4.1.2 用户注册模块
```python
@app.route("/register", methods=["GET","POST"])
def register():
    """用户注册"""
    msg = ""
    if request.method == "POST":
        try:
            name = request.form["name"]
            phone = request.form["phone"]
            identity_id = request.form["identity_id"]
            username = request.form["username"]
            password = request.form["password"]
            
            conn = get_db_connection()
            # 检查账号是否已存在
            user = conn.execute(
                'SELECT id FROM users WHERE username = ? OR identity_id = ?', 
                (username, identity_id)
            ).fetchone()
            
            if user:
                msg = "账号或身份证字号已存在"
            else:
                hashed_password = generate_password_hash(password)
                conn.execute(
                    'INSERT INTO users (name, phone, identity_id, username, password_hash) VALUES (?, ?, ?, ?, ?)',
                    (name, phone, identity_id, username, hashed_password)
                )
                conn.commit()
                msg = "注册成功！请登入"
            conn.close()
        except Exception as e:
            print(f"注册错误: {e}")
            msg = "注册发生错误，请稍后再试"
    return render_template("register.html", message=msg)
```

#### 4.1.3 AI对话处理模块
```python
@app.route("/api/chat", methods=["POST"])
def chat():
    """AI 聊天 API（整合数据库查询、创建和修改预约功能）"""
    if not gemini_model:
        return jsonify({
            "success": False, 
            "error": "AI 模型未初始化"
        }), 500
    
    try:
        data = request.get_json()
        message = data.get("message", "").strip()
        username = session.get("user")
        
        # 识别用户意图
        create_keywords = ['预约', '掛號', '我要预约']
        update_keywords = ['修改', '更改', '改', '更新']
        query_keywords = ['查询', '我的预约', '预约记录']
        
        is_create = any(keyword in message for keyword in create_keywords)
        is_update = any(keyword in message for keyword in update_keywords)
        is_query = any(keyword in message for keyword in query_keywords)
        
        enhanced_message = message
        
        # 处理预约创建
        if is_create:
            appointment_info = extract_appointment_info(message)
            required_fields = ['patient_name', 'patient_phone', 'department', 
                             'doctor_name', 'appointment_date', 'appointment_time']
            missing_fields = [f for f in required_fields if f not in appointment_info]
            
            if missing_fields:
                # 询问缺失信息
                missing_info = "缺少以下资讯：" + "、".join(missing_fields)
                enhanced_message = f"{message}\\n\\n{missing_info}\\n请友善地询问用户缺少的资讯。"
            else:
                # 直接创建预约
                result = create_appointment_via_ai(username, appointment_info)
                if result['success']:
                    return jsonify({
                        "success": True,
                        "message": f"预约已成功创建，编号：{result['appointment_id']}"
                    })
        
        # 处理预约查询
        elif is_query:
            appointments = query_appointments_by_keyword(username, "")
            if appointments:
                appointment_info = "\\n\\n以下是您的预约记录：\\n"
                for i, apt in enumerate(appointments[:5], 1):
                    appointment_info += f"\\n预约 {i}:\\n"
                    appointment_info += f"  科别: {apt['department']}\\n"
                    appointment_info += f"  医师: {apt['doctor_name']}\\n"
                    appointment_info += f"  日期: {apt['appointment_date']}\\n"
                enhanced_message = f"{message}\\n\\n{appointment_info}"
        
        # 调用 Gemini API
        response = gemini_model.generate_content(enhanced_message)
        return jsonify({"success": True, "message": response.text})
        
    except Exception as e:
        print(f"[错误] 聊天 API 发生错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
```

#### 4.1.4 信息提取模块
```python
def extract_appointment_info(message):
    """从消息中提取预约资讯"""
    info = {}
    
    # 提取病历号
    patient_id_match = re.search(r'病歷號[：:]\\s*([A-Z0-9]+)|([A-Z]\\d{4,})', message.upper())
    if patient_id_match:
        info['patient_id'] = patient_id_match.group(1) or patient_id_match.group(2)
    
    # 提取姓名
    name_match = re.search(r'姓名[：:]\\s*([^\\s，,。]+)', message)
    if name_match:
        info['patient_name'] = name_match.group(1)
    
    # 提取电话
    phone_match = re.search(r'電話[：:]\\s*([\\d\\-]+)', message)
    if phone_match:
        phone = phone_match.group(1).replace('-', '').replace(' ', '')
        if len(phone) >= 8:
            info['patient_phone'] = phone
    
    # 提取科别
    departments = ['内科', '外科', '儿科', '妇产科', '骨科', 
                  '眼科', '耳鼻喉科', '皮肤科', '精神科', '复健科']
    for dept in departments:
        if dept in message:
            info['department'] = dept
            break
    
    # 提取日期
    if '明天' in message:
        info['appointment_date'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    elif '後天' in message:
        info['appointment_date'] = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
    
    # 提取时间
    time_match = re.search(r'(\\d{1,2}[:：]\\d{2})|(\\d{1,2}點)', message)
    if time_match:
        time_str = time_match.group(1) or time_match.group(2)
        if '點' in time_str:
            hour = int(re.search(r'(\\d+)', time_str).group(1))
            time_str = f"{hour:02d}:00"
        info['appointment_time'] = time_str.replace('：', ':')
    
    return info
```

### 4.2 项目文件结构

```
medicalai-main/
├── app.py                          # 主应用程序
├── init_sqlite_db.py              # 数据库初始化脚本
├── requirements.txt               # Python依赖包
├── .env                           # 环境变量配置
├── medical_appointments.db        # SQLite数据库文件
├── Procfile                       # Render部署配置
├── render.yaml                    # Render服务配置
├── 快速启动.bat                    # Windows快速启动脚本
├── 上传到GitHub.bat               # Git上传脚本
├── templates/                     # HTML模板文件夹
│   ├── welcome.html              # 欢迎页
│   ├── login.html                # 登录页
│   ├── register.html             # 注册页
│   ├── index.html                # 主界面（AI助手）
│   ├── appointment.html          # 预约表单页
│   ├── appointment_list.html     # 预约列表页
│   └── profile.html              # 个人资料页
├── static/                        # 静态文件文件夹
│   └── style.css                 # 样式表
└── 说明文档/
    ├── AI预约功能使用说明.md
    ├── Gemini设置说明.md
    ├── Render部署说明.md
    └── 本机运行问题诊断.md
```

---

# 第五章、系统测试

## 第一节、目的说明

本章节说明系统测试的目的、测试环境、测试计划和测试结果。通过全面的测试，确保系统功能正常、性能稳定、用户体验良好。

**测试目标**:
1. 验证所有功能是否正常运作
2. 检测并修复系统缺陷
3. 确保系统性能符合要求
4. 验证用户界面友好性
5. 测试AI功能的准确性

## 第二节、测试环境

### 2.1 测试硬件环境
