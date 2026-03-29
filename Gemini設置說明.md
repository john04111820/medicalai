# Google Gemini API 設置說明

## 功能說明

已成功整合 Google Gemini API，現在您的醫療AI助手具備以下功能：

1. ✅ **聊天式對話界面** - 類似 ChatGPT 的對話體驗
2. ✅ **語音輸入** - 使用 Whisper 將語音轉換為文字
3. ✅ **智能回應** - 使用 Google Gemini 生成專業的醫療相關回答
4. ✅ **對話歷史** - 自動保存對話上下文
5. ✅ **清除對話** - 可以清除對話歷史重新開始
6. ✅ **完全免費** - Gemini 提供免費額度，無需付費！

## 免費額度說明

### Google Gemini 免費方案

- ✅ **完全免費**：每月 60 次請求（免費層級）
- ✅ **無需信用卡**：註冊即可使用
- ✅ **穩定可靠**：Google 官方 API
- ✅ **功能完整**：與付費版本功能相同

**注意**：免費額度用盡後，可以升級到付費方案，或等待下個月重置。

## 設置步驟

### 1. 獲取 Google Gemini API Key

1. 訪問 [Google AI Studio](https://makersuite.google.com/app/apikey)
2. 使用 Google 帳號登入
3. 點擊 "Create API Key"
4. 選擇或創建 Google Cloud 專案
5. 複製生成的 API Key（妥善保存）

### 2. 設置環境變數

#### Windows (PowerShell)
```powershell
$env:GEMINI_API_KEY="your-api-key-here"
```

#### Windows (CMD)
```cmd
set GEMINI_API_KEY=your-api-key-here
```

#### 永久設置（Windows）
1. 右鍵「此電腦」→「內容」
2. 點擊「進階系統設定」
3. 點擊「環境變數」
4. 在「使用者變數」中點擊「新增」
5. 變數名稱：`GEMINI_API_KEY`
6. 變數值：您的 API Key
7. 確定並重新啟動終端機

#### Linux/Mac
```bash
export GEMINI_API_KEY="your-api-key-here"
```

或在 `~/.bashrc` 或 `~/.zshrc` 中添加：
```bash
export GEMINI_API_KEY="your-api-key-here"
```

### 3. 驗證設置

運行應用後，查看終端機輸出：
- 如果看到 "Google Gemini API 客戶端已初始化"，表示設置成功
- 如果看到 "警告: 未設置 GEMINI_API_KEY"，請檢查環境變數

## 使用方式

### 文字輸入
1. 在輸入框中輸入問題
2. 點擊「發送」按鈕或按 `Enter` 鍵
3. AI 會自動回應

### 語音輸入
1. 點擊麥克風按鈕開始錄音
2. 說出您的問題
3. 再次點擊停止錄音
4. 語音會自動轉換為文字並發送給 AI

### 清除對話
點擊垃圾桶圖標可以清除所有對話歷史

## 功能特點

- **醫療專業助手**：專門針對醫療相關問題優化
- **繁體中文**：使用繁體中文回答
- **上下文理解**：記住之前的對話內容
- **語音+文字**：支援多種輸入方式
- **完全免費**：使用免費額度，無需付費

## 注意事項

1. **API 限制**：免費層級每月 60 次請求
2. **隱私保護**：對話內容會發送到 Google，請注意隱私
3. **模型選擇**：目前使用 `gemini-pro` 模型

## 修改模型

在 `app.py` 中找到：
```python
gemini_model = genai.GenerativeModel('gemini-pro')
```

可以改為：
- `gemini-pro` - 標準模型（推薦）
- `gemini-pro-vision` - 支援圖像輸入（如果需要）

## 故障排除

### 問題 1：顯示 "Gemini API 未配置"
**解決**：檢查環境變數是否正確設置

### 問題 2：API 調用失敗
**解決**：
- 檢查 API Key 是否正確
- 檢查是否超過免費額度
- 檢查網路連接
- 確認 API Key 已啟用

### 問題 3：回應速度慢
**解決**：
- 檢查網路速度
- 減少對話歷史長度

### 問題 4：超過免費額度
**解決**：
- 等待下個月重置
- 或升級到付費方案（如果需要更多請求）

## 安裝依賴

如果還沒安裝 Google Generative AI 套件：
```bash
pip install google-generativeai
```

或安裝所有依賴：
```bash
pip install -r requirements.txt
```

## 與 ChatGPT 對比

| 項目 | ChatGPT (OpenAI) | Gemini (Google) |
|------|------------------|-----------------|
| 費用 | 付費 | **免費**（有額度） |
| 設置難度 | 簡單 | 簡單 |
| 性能 | 優秀 | 優秀 |
| 免費額度 | 新用戶 $5 | 每月 60 次請求 |

## 優勢

✅ **完全免費** - 無需付費即可使用  
✅ **穩定可靠** - Google 官方 API  
✅ **功能完整** - 與付費版本功能相同  
✅ **易於設置** - 簡單的 API Key 設置  



