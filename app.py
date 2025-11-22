from flask import Flask, render_template_string, request, redirect, url_for, session, render_template
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

# 模擬使用者資料庫
users = {"admin": generate_password_hash("1234")}

# --- HTML 模板 (微調了連結路徑) ---

# 1. 登入頁面 HTML
login_html = """
<!DOCTYPE html>
<html>
<head><title>登入</title></head>
<body style="font-family: Arial; background:#eef1f7; display:flex; justify-content:center; align-items:center; height:100vh;">
<div style="background:white; padding:30px; border-radius:10px; width:300px; text-align:center;">
<h2>登入</h2>
<form method="POST" action="/login">
    <input type="text" name="username" placeholder="帳號" required style="width:100%; padding:10px; margin:8px 0;"><br>
    <input type="password" name="password" placeholder="密碼" required style="width:100%; padding:10px; margin:8px 0;"><br>
    <button type="submit" style="width:100%; padding:10px; background:#5563DE; color:white; border:none; border-radius:5px; cursor:pointer;">登入</button>
</form>
<p style="color:red;">{{ message }}</p>
<a href="/register" style="color:#5563DE; text-decoration:none;">註冊新帳號</a> | 
<a href="/" style="color:#888; text-decoration:none;">暫不登入 (回首頁)</a>
</div></body></html>
"""

# 2. 註冊頁面 HTML
register_html = """
<!DOCTYPE html>
<html>
<head><title>註冊</title></head>
<body style="font-family: Arial; background:#eef1f7; display:flex; justify-content:center; align-items:center; height:100vh;">
<div style="background:white; padding:30px; border-radius:10px; width:300px; text-align:center;">
<h2>註冊</h2>
<form method="POST">
    <input type="text" name="username" placeholder="帳號" required style="width:100%; padding:10px; margin:8px 0;"><br>
    <input type="password" name="password" placeholder="密碼" required style="width:100%; padding:10px; margin:8px 0;"><br>
    <button type="submit" style="width:100%; padding:10px; background:#5563DE; color:white; border:none; border-radius:5px; cursor:pointer;">註冊</button>
</form>
<p style="color:red;">{{ message }}</p>
<a href="/login" style="color:#5563DE; text-decoration:none;">返回登入</a>
</div></body></html>
"""

# --- 路由設定 ---

# 1. 首頁路由：現在直接顯示「語音助理介面」
@app.route("/")
def index():
    # session.get("user") 會嘗試抓取使用者名稱
    # 如果沒登入，它會回傳 None，HTML 那邊的 {% if %} 就會判斷正確
    return render_template("index.html", username=session.get("user"))

# 2. 登入路由：同時處理「顯示頁面 (GET)」和「處理登入 (POST)」
@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    # 如果是按下登入按鈕 (POST)
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        if username in users and check_password_hash(users[username], password):
            session["user"] = username
            # 登入成功後，導回首頁 (index)
            return redirect(url_for("index"))
        
        msg = "帳號或密碼錯誤"
    
    # 如果是直接輸入網址進入 (GET)，或是登入失敗，都顯示登入畫面
    return render_template_string(login_html, message=msg)

# 3. 註冊路由
@app.route("/register", methods=["GET","POST"])
def register():
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

# 4. 登出路由
@app.route("/logout")
def logout():
    session.pop("user", None) # 清除 session
    return redirect(url_for("index")) # 登出後留在首頁 (變成未登入狀態)

if __name__ == "__main__":
    app.run(debug=True)
