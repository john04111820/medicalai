@echo off
chcp 65001 >nul
echo ========================================
echo 上傳到 GitHub
echo ========================================
echo.

REM 檢查 Git 是否安裝
git --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Git！
    echo.
    echo 請先安裝 Git：
    echo 1. 下載地址：https://git-scm.com/download/win
    echo 2. 安裝完成後，重新執行此腳本
    echo.
    echo 或者使用 GitHub Desktop：
    echo https://desktop.github.com/
    echo.
    pause
    exit /b 1
)

echo [1/5] Git 版本檢查...
git --version
echo.

echo [2/5] 初始化 Git 倉庫...
if exist .git (
    echo Git 倉庫已存在
) else (
    git init
    echo Git 倉庫初始化完成
)
echo.

echo [3/5] 檢查遠程倉庫...
git remote -v | findstr "origin" >nul
if errorlevel 1 (
    echo 添加遠程倉庫...
    git remote add origin https://github.com/john04111820/medicalai.git
    echo 遠程倉庫已添加
) else (
    echo 遠程倉庫已存在
    git remote set-url origin https://github.com/john04111820/medicalai.git
    echo 遠程倉庫 URL 已更新
)
echo.

echo [4/5] 添加文件並提交...
git add .
git commit -m "更新項目文件" 2>nul
if errorlevel 1 (
    echo 沒有變更需要提交，或提交失敗
) else (
    echo 文件已提交
)
echo.

echo [5/5] 推送到 GitHub...
echo.
echo 注意：如果這是第一次推送，可能需要：
echo 1. 登入 GitHub 帳號
echo 2. 輸入用戶名和密碼（或使用 Personal Access Token）
echo.
echo 如果遇到認證問題，請使用 Personal Access Token：
echo https://github.com/settings/tokens
echo.
pause
git push -u origin main 2>nul
if errorlevel 1 (
    git push -u origin master 2>nul
    if errorlevel 1 (
        echo.
        echo [錯誤] 推送失敗！
        echo 請檢查：
        echo 1. 是否已登入 GitHub
        echo 2. 是否有權限推送到此倉庫
        echo 3. 網路連接是否正常
        echo.
        echo 如果分支名稱不是 main 或 master，請手動執行：
        echo git branch -M main
        echo git push -u origin main
    ) else (
        echo.
        echo [成功] 已推送到 GitHub！
        echo 網址：https://github.com/john04111820/medicalai
    )
) else (
    echo.
    echo [成功] 已推送到 GitHub！
    echo 網址：https://github.com/john04111820/medicalai
)

echo.
pause



