# Render 部署說明

## Render 支援情況

✅ **Render 支援部署 Flask 應用**，但需要注意以下幾點：

### 優點
- ✅ 支援 Python/Flask 應用
- ✅ 自動 HTTPS
- ✅ 自動部署（連接 GitHub）
- ✅ 免費層可用（但資源有限）

### 限制與注意事項

⚠️ **重要限制**：
1. **無 GPU 支援**：Render 只提供 CPU，Whisper 在 CPU 上運行較慢
2. **免費層資源有限**：
   - 512MB RAM
   - 0.1 CPU
   - 可能無法運行較大的 Whisper 模型
3. **啟動超時**：免費層啟動時間限制較短
4. **FFmpeg 依賴**：需要系統級 FFmpeg

## 部署步驟

### 1. 準備工作

確保以下文件存在：
- ✅ `Procfile` - 已存在
- ✅ `requirements.txt` - 已存在
- ✅ `render.yaml` - 已創建（可選）

### 2. 在 Render 上創建服務

1. 登入 [Render.com](https://render.com)
2. 點擊 "New +" → "Web Service"
3. 連接您的 GitHub 倉庫
4. 配置設置：
   - **Name**: `medicalai`（或您喜歡的名稱）
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: 選擇 **Starter**（$7/月）或更高，免費層可能無法運行 Whisper

### 3. 環境變數設置

在 Render 控制台添加環境變數：
- `SECRET_KEY`: 生成一個隨機密鑰（用於 Flask session）
- `PYTHON_VERSION`: `3.11.0`（可選）

### 4. 部署選項

#### 選項 A：使用 render.yaml（推薦）
- Render 會自動讀取 `render.yaml` 配置
- 更易於管理配置

#### 選項 B：手動配置
- 在 Render 控制台手動設置所有參數

## 優化建議

### 1. 使用較小的 Whisper 模型

代碼已優化為使用 `tiny` 模型（而非 `base`），原因：
- 更小的內存占用
- 更快的載入速度
- 適合 Render 免費層

如需更高準確度，可在 `app.py` 中修改：
```python
whisper_model = whisper.load_model("base")  # 或 "small"
```

### 2. 延遲載入模型

代碼已實現延遲載入，避免啟動超時：
- 模型只在第一次使用時載入
- 加快應用啟動速度

### 3. 考慮付費計劃

如果免費層無法運行，建議：
- **Starter Plan** ($7/月): 512MB RAM, 0.5 CPU
- **Standard Plan** ($25/月): 2GB RAM, 1 CPU

## 替代方案

如果 Render 無法滿足需求，可考慮：

1. **Heroku** - 類似 Render，但價格較高
2. **Railway** - 提供更好的免費層
3. **Fly.io** - 支援更多資源
4. **AWS/GCP/Azure** - 企業級解決方案，支援 GPU

## 故障排除

### 問題 1：啟動超時
**解決方法**：
- 確保使用延遲載入（已實現）
- 使用更小的模型（`tiny`）

### 問題 2：內存不足
**解決方法**：
- 升級到付費計劃
- 使用 `tiny` 模型

### 問題 3：FFmpeg 未找到
**解決方法**：
- Render 應該自動安裝，如果沒有，聯繫 Render 支援

### 問題 4：模型下載失敗
**解決方法**：
- 檢查網路連接
- 確保有足夠的磁盤空間

## 測試部署

部署完成後，測試以下功能：
1. 訪問首頁
2. 測試錄音功能
3. 檢查語音轉文字是否正常

## 注意事項

- 首次部署可能需要 10-15 分鐘（下載依賴和模型）
- 免費層應用在 15 分鐘無活動後會休眠
- 建議使用付費計劃以獲得更好的性能





