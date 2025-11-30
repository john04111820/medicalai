# ChatGPT API 設置說明

## 功能說明

已成功整合 ChatGPT API，現在您的醫療AI助手具備以下功能：

1. ✅ **聊天式對話界面** - 類似 ChatGPT 的對話體驗
2. ✅ **語音輸入** - 使用 Whisper 將語音轉換為文字
3. ✅ **智能回應** - 使用 ChatGPT 生成專業的醫療相關回答
4. ✅ **對話歷史** - 自動保存對話上下文
5. ✅ **清除對話** - 可以清除對話歷史重新開始

## 設置步驟

### 1. 獲取 OpenAI API Key

1. 訪問 [OpenAI 官網](https://platform.openai.com/)
2. 註冊或登入帳號
3. 前往 [API Keys 頁面](https://platform.openai.com/api-keys)
4. 點擊 "Create new secret key"
5. 複製生成的 API Key（只會顯示一次，請妥善保存）

### 2. 設置環境變數

#### Windows (PowerShell)
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

#### Windows (CMD)
```cmd
set OPENAI_API_KEY=your-api-key-here
```

#### 永久設置（Windows）
1. 右鍵「此電腦」→「內容」
2. 點擊「進階系統設定」
3. 點擊「環境變數」
4. 在「使用者變數」中點擊「新增」
5. 變數名稱：`OPENAI_API_KEY`
6. 變數值：您的 API Key
7. 確定並重新啟動終端機

#### Linux/Mac
```bash
export OPENAI_API_KEY="your-api-key-here"
```

或在 `~/.bashrc` 或 `~/.zshrc` 中添加：
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### 3. 驗證設置

運行應用後，查看終端機輸出：
- 如果看到 "OpenAI API 客戶端已初始化"，表示設置成功
- 如果看到 "警告: 未設置 OPENAI_API_KEY"，請檢查環境變數

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

## 注意事項

1. **API 費用**：使用 OpenAI API 會產生費用，請查看 [OpenAI 定價](https://openai.com/pricing)
2. **API 限制**：注意 API 的使用限制和配額
3. **隱私保護**：對話內容會發送到 OpenAI，請注意隱私
4. **模型選擇**：目前使用 `gpt-3.5-turbo`，可在 `app.py` 中修改為 `gpt-4` 獲得更佳效果

## 修改模型

在 `app.py` 中找到：
```python
model="gpt-3.5-turbo",  # 或使用 "gpt-4" 獲得更佳效果
```

可以改為：
- `gpt-3.5-turbo` - 速度快，成本低
- `gpt-4` - 更準確，但速度較慢，成本較高

## 故障排除

### 問題 1：顯示 "OpenAI API 未配置"
**解決**：檢查環境變數是否正確設置

### 問題 2：API 調用失敗
**解決**：
- 檢查 API Key 是否正確
- 檢查帳號是否有餘額
- 檢查網路連接

### 問題 3：回應速度慢
**解決**：
- 使用 `gpt-3.5-turbo` 而非 `gpt-4`
- 檢查網路速度

## 安裝依賴

如果還沒安裝 OpenAI 套件：
```bash
pip install openai
```

或安裝所有依賴：
```bash
pip install -r requirements.txt
```

