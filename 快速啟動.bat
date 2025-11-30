@echo off
chcp 65001 >nul
echo ========================================
echo 醫療AI語音助理 - 快速啟動
echo ========================================
echo.

REM 檢查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Python！
    echo.
    echo 請先安裝 Python 3.8 或更高版本
    echo 下載地址：https://www.python.org/downloads/
    echo.
    echo 安裝時請記得勾選 "Add Python to PATH"
    pause
    exit /b 1
)

echo [1/4] Python 版本檢查...
python --version
echo.

echo [2/4] 檢查依賴套件...
python -m pip list | findstr /i "flask whisper" >nul
if errorlevel 1 (
    echo 檢測到缺少依賴，正在安裝...
    echo 這可能需要幾分鐘時間，請耐心等待...
    echo.
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [錯誤] 依賴安裝失敗！
        echo 請檢查網路連接或手動執行：pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo 依賴安裝完成！
) else (
    echo 依賴套件已安裝
)
echo.

echo [3/4] 檢查 FFmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 FFmpeg
    echo Whisper 需要 FFmpeg 來處理音頻
    echo 下載地址：https://ffmpeg.org/download.html
    echo 或使用：choco install ffmpeg
    echo.
    echo 如果已安裝但未添加到 PATH，請手動添加
    echo.
) else (
    echo FFmpeg 已安裝
)
echo.

echo [4/4] 啟動應用...
echo.
echo ========================================
echo 網頁將在以下網址開啟：
echo http://localhost:5000
echo http://127.0.0.1:5000
echo ========================================
echo.
echo 首次運行時，Whisper 會下載模型（約 150MB）
echo 這可能需要 5-10 分鐘，請耐心等待...
echo.
echo 按 Ctrl+C 可停止伺服器
echo.

python app.py

pause



