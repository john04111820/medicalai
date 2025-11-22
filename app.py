from flask import Flask, render_template_string, request, redirect, url_for, session, render_template # <--- 新增 render_template
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

# 模擬使用者資料庫
users = {"admin": generate_password_hash("1234")}

# (原本的 login_html 和 register_html 保持不變，為了版面簡潔我先省略，請保留您原本的程式碼)
# 這裡為了完整性，您可以保留原本那一大段 login_html 和 register_html 字串變數
# ... (Login_html string) ...
# ... (Register_html string) ...

# 如果您不小心刪掉了，可以用原本的程式碼，只要確保 import 和下面的 dashboard 改對就好

# --- 為了讓程式碼能跑，我還是把 login_html 簡化放這裡 (您用原本的即可) ---
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
<button type="submit" style="width:100%; padding:10px; background:#5563DE; color:white; border:none;">登入</button>
</form>
<p>{{ message }}</p>
<a href="/register">註冊新帳號</a>
</div></body></html>
"""

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
<button type="submit" style="width:100%; padding:10px; background:#5563DE; color:white; border:none;">註冊</button>
</form>
<p>{{ message }}</p>
<a href="/">返回登入</a>
</div></body></html>
"""

# 路由設定
@app.route("/")
def index():
    msg = ""
    return render_template_string(login_html, message=msg)

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    if username in users and check_password_hash(users[username], password):
        session["user"] = username
        return redirect(url_for("dashboard"))
    msg = "帳號或密碼錯誤"
    return render_template_string(login_html, message=msg)

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

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("index"))
    return render_template("index.html", username=session["user"]) 

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)