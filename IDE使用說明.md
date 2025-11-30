# 在 IDE 中開啟和運行網頁

## 使用 VS Code / Cursor 運行 Flask 應用

### 方法 1：使用調試功能（推薦）

1. **打開專案**
   - 在 VS Code/Cursor 中打開專案資料夾
   - 或使用：`文件` → `打開資料夾` → 選擇 `medicalai` 資料夾

2. **安裝 Python 擴展**（如果還沒安裝）
   - 按 `Ctrl+Shift+X` 打開擴展面板
   - 搜索 "Python" 並安裝 Microsoft 的 Python 擴展

3. **運行應用**
   - 按 `F5` 或點擊左側調試圖標（蟲子圖標）
   - 選擇 "Python: Flask 應用"
   - 或選擇 "啟動 Flask 並打開瀏覽器"（會自動打開瀏覽器）

4. **查看輸出**
   - 終端機（Terminal）會顯示應用運行狀態
   - 看到 "Running on http://127.0.0.1:5000" 表示成功

5. **訪問網頁**
   - 瀏覽器會自動打開 http://localhost:5000
   - 或手動在瀏覽器輸入：http://localhost:5000

### 方法 2：使用終端機運行

1. **打開終端機**
   - 按 `` Ctrl+` ``（反引號）或 `Ctrl+Shift+` `
   - 或點擊：`終端` → `新建終端`

2. **運行命令**
   ```bash
   python app.py
   ```

3. **訪問網頁**
   - 在瀏覽器打開：http://localhost:5000

### 方法 3：使用任務運行器

1. **創建任務**（可選）
   - 按 `Ctrl+Shift+P` 打開命令面板
   - 輸入 "Tasks: Configure Task"
   - 選擇 "Create tasks.json file from template"
   - 選擇 "Others"

2. **運行任務**
   - 按 `Ctrl+Shift+B` 運行任務

## 調試配置說明

### 已配置的調試選項

1. **Python: Flask 應用**
   - 直接運行 Flask 應用
   - 在集成終端機中顯示輸出
   - 支援斷點調試

2. **在瀏覽器中打開**
   - 自動在 Edge 瀏覽器中打開網頁
   - 需要先啟動 Flask 應用

3. **啟動 Flask 並打開瀏覽器**（組合）
   - 同時啟動 Flask 和打開瀏覽器
   - 最方便的方式

## 快捷鍵

- `F5` - 開始調試/運行
- `Shift+F5` - 停止調試
- `Ctrl+F5` - 運行（不調試）
- `` Ctrl+` `` - 打開/關閉終端機
- `Ctrl+Shift+P` - 命令面板

## 常見問題

### 問題 1：找不到 Python 解釋器

**解決方法**：
1. 按 `Ctrl+Shift+P`
2. 輸入 "Python: Select Interpreter"
3. 選擇正確的 Python 版本

### 問題 2：模組未找到錯誤

**解決方法**：
1. 在終端機中運行：`pip install -r requirements.txt`
2. 確保選擇了正確的 Python 解釋器

### 問題 3：端口已被占用

**解決方法**：
1. 修改 `app.py` 最後一行：
   ```python
   app.run(debug=True, port=5001)  # 改用其他端口
   ```

### 問題 4：Whisper 模型載入時間過長

**說明**：
- 首次運行需要下載模型（約 150MB）
- 請耐心等待 5-10 分鐘
- 之後運行會快很多

## 推薦的工作流程

1. **首次設置**：
   - 打開專案資料夾
   - 安裝 Python 擴展
   - 在終端機運行：`pip install -r requirements.txt`

2. **日常開發**：
   - 按 `F5` 啟動應用
   - 在瀏覽器中測試
   - 修改代碼後自動重載（Flask debug 模式）

3. **調試**：
   - 在代碼中設置斷點（點擊行號左側）
   - 按 `F5` 開始調試
   - 使用調試工具欄控制執行

## 終端機命令參考

```bash
# 安裝依賴
pip install -r requirements.txt

# 運行應用
python app.py

# 檢查 Python 版本
python --version

# 檢查已安裝的套件
pip list
```

## 提示

- 使用 `Ctrl+C` 可以停止運行的應用
- Flask 的 debug 模式會自動重載代碼更改
- 終端機會顯示所有日誌和錯誤訊息



