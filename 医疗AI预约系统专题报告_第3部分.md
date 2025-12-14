块设计、数据库设计和界面设计。通过系统化的设计，确保系统的可靠性、可维护性和可扩展性。

## 第二节、设计方法与工具

### 2.1 设计方法

1. **分层架构设计**: 采用MVC模式分离展示层、业务逻辑层和数据访问层
2. **模块化设计**: 将系统划分为独立的功能模块
3. **RESTful API设计**: API端点遵循REST风格
4. **响应式设计**: 前端界面自适应不同屏幕尺寸

### 2.2 设计工具

- **架构图**: 描述系统整体架构
- **ER图**: 数据库实体关系模型
- **流程图**: 业务流程可视化
- **线框图**: 界面布局设计

## 第三节、软件架构之准则

### 3.1 系统架构

系统采用经典的三层架构：

```
┌─────────────────────────────────────┐
│      展示层 (Presentation)          │
│  - HTML Templates (Jinja2)         │
│  - JavaScript (前端逻辑)            │
│  - CSS (样式设计)                   │
└──────────────┬──────────────────────┘
               │
┌──────────────┴──────────────────────┐
│      应用层 (Application)            │
│  - Flask Routes (路由)              │
│  - Business Logic (业务逻辑)        │
│  - AI Integration (AI整合)          │
└──────────────┬──────────────────────┘
               │
┌──────────────┴──────────────────────┐
│      数据层 (Data)                   │
│  - SQLite Database                  │
│  - Database Functions               │
│  - Data Models                      │
└─────────────────────────────────────┘
```

### 3.2 技术栈架构

```
前端技术:
- HTML5 + CSS3 + JavaScript
- Font Awesome图标库
- 响应式设计

后端框架:
- Flask 3.x (Web框架)
- Werkzeug (密码加密)
- Jinja2 (模板引擎)

AI服务:
- Google Gemini 2.0 Flash (对话AI)
- OpenAI Whisper Base (语音识别)

数据存储:
- SQLite (关系数据库)
- LocalStorage (浏览器端存储)

部署环境:
- Gunicorn (WSGI服务器)
- Render (云平台)
```

### 3.3 设计原则

1. **单一职责原则**: 每个函数和模块只负责单一功能
2. **开闭原则**: 对扩展开放，对修改封闭
3. **依赖倒置**: 依赖于抽象而非具体实现
4. **关注点分离**: 前后端分离，业务逻辑与数据访问分离

## 第四节、系统元件与模块设计

### 4.1 核心模块划分

#### 4.1.1 用户管理模块 (User Management)

**主要组件**:
- `register()`: 用户注册路由
- `login()`: 用户登录路由
- `profile()`: 个人资料管理路由
- `logout()`: 用户登出路由
- `login_required`: 登录验证装饰器

**关键函数**:
```python
@app.route("/register", methods=["GET","POST"])
def register():
    # 处理用户注册
    # 验证输入、检查唯一性、密码哈希、写入数据库

@login_required
@app.route("/profile", methods=["GET", "POST"])
def profile():
    # 个人资料查看和修改
    # 身份证号遮蔽显示
```

#### 4.1.2 预约管理模块 (Appointment Management)

**主要组件**:
- `appointment()`: 创建预约路由
- `appointment_list()`: 查询预约列表路由
- `edit_appointment()`: 修改预约路由
- `cancel_appointment()`: 取消预约路由

**辅助函数**:
```python
def query_appointments_by_keyword(username, keyword):
    # 根据关键词查询预约

def create_appointment_via_ai(username, appointment_data):
    # AI方式创建预约

def update_appointment_via_ai(username, appointment_id, update_data):
    # AI方式更新预约
```

#### 4.1.3 AI交互模块 (AI Interaction)

**主要组件**:
- `/api/transcribe`: 语音转文字API
- `/api/chat`: AI聊天API
- `extract_appointment_info()`: 信息提取函数

**工作流程**:
```
用户语音 → Whisper转录 → Gemini处理 → 提取信息 → 更新数据库
用户文字 → Gemini处理 → 提取信息 → 更新数据库
```

**关键函数**:
```python
@app.route("/api/transcribe", methods=["POST"])
def transcribe_audio():
    # 接收音频文件
    # 使用Whisper模型转录
    # 返回文字结果

@app.route("/api/chat", methods=["POST"])
def chat():
    # 接收用户消息
    # 识别意图（查询/创建/修改）
    # 调用相应处理函数
    # 返回AI回复
```

#### 4.1.4 数据库管理模块 (Database Management)

**主要组件**:
- `get_db_connection()`: 获取数据库连接
- `init_db()`: 初始化数据库
- `get_doctors_by_department()`: 获取医师信息

**数据库操作封装**:
```python
def get_db_connection():
    conn = sqlite3.connect(SQLITE_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # 创建表结构
    # 插入初始数据（医师信息）
```

#### 4.1.5 医师排班模块 (Doctor Scheduling)

**主要数据**:
```python
doctor_seed = {
    "内科": [("张内晨", "morning"), ("李内昕", "afternoon")],
    "外科": [("王外晨", "morning"), ("陈外昕", "afternoon")],
    # ... 其他科别
}
```

**功能**:
- 医师信息存储
- 按科别查询医师
- 时刻表显示

### 4.2 模块交互设计

```
┌──────────┐      ┌──────────┐      ┌──────────┐
│  用户界面 │ ───→ │  Flask   │ ───→ │  数据库   │
│  (HTML)  │ ←─── │  Routes  │ ←─── │ (SQLite) │
└──────────┘      └────┬─────┘      └──────────┘
                       │
                   ┌───┴────┐
                   │ AI服务  │
                   │ Gemini │
                   │ Whisper│
                   └────────┘
```

## 第五节、人机介面设计

### 5.1 页面结构设计

#### 5.1.1 欢迎页 (welcome.html)
- Logo和标题
- 系统介绍
- 登入/注册按钮
- 渐变背景动画

#### 5.1.2 主界面 (index.html)
**顶部导航栏**:
- Logo (左上)
- 用户信息 (右上)
- 预约门诊按钮
- 我的预约按钮
- 长辈模式切换
- 登出按钮

**主要内容区**:
- 标题："医疗AI聊天助手"
- 范例对话栏（预约门诊、常见疾病）
- 聊天消息显示区
- 输入区域（文字框、麦克风、发送、清除按钮）
- 状态提示（录音中、处理中）

**长辈模式界面**:
- 隐藏复杂元素
- 显示超大麦克风按钮
- 大字体状态文字
- 简化操作流程

#### 5.1.3 预约表单页 (appointment.html)
- 病历号（选填）
- 病患姓名（自动填充）
- 联络电话（自动填充）
- 科别下拉选单
- 医师下拉选单（动态更新）
- 预约日期（日期选择器）
- 预约时间（时间选择器）
- 症状描述（文字区域）
- 提交/取消按钮

#### 5.1.4 预约列表页 (appointment_list.html)
- 预约记录卡片
- 显示所有预约信息
- 编辑/取消按钮
- 状态标签（待确认/已完成/已取消）

#### 5.1.5 个人资料页 (profile.html)
- 姓名（可编辑）
- 电话（可编辑）
- 身份证号（部分遮蔽，可编辑）
- 用户名（不可编辑）
- 更新按钮

### 5.2 界面设计准则

#### 5.2.1 色彩设计
```css
主色调: #2563eb (蓝色 - 专业医疗感)
成功色: #10b981 (绿色)
警告色: #f59e0b (橙色)
危险色: #ef4444 (红色)
背景色: #f8fafc (浅灰)
文字色: #1e293b (深灰)
```

#### 5.2.2 排版设计
- 字体: 系统默认无衬线字体
- 主标题: 2rem
- 副标题: 1.5rem
- 正文: 1rem
- 行高: 1.6
- 间距: 统一使用8px的倍数

#### 5.2.3 交互设计
- 按钮hover效果（颜色加深）
- 输入框focus效果（边框高亮）
- 加载动画（旋转图标）
- 消息渐入动画
- 模态框淡入淡出

### 5.3 响应式设计

```css
/* 桌面端 */
@media (min-width: 768px) {
    - 导航栏水平布局
    - 表单双列布局
    - 聊天区域最大宽度800px
}

/* 移动端 */
@media (max-width: 767px) {
    - 导航栏垂直布局
    - 表单单列布局
    - 按钮全宽显示
    - 字体适度放大
}
```

## 第六节、档案/资料库设计

### 6.1 数据库设计

#### 6.1.1 数据表结构

**users表 (用户表)**
