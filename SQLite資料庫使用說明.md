# SQLite 資料庫使用說明

## 概述

本專案現在支援兩種資料庫：
1. **SQLite**（預設，推薦用於開發和測試）
2. **MySQL/Azure MySQL**（用於生產環境）

## 快速開始

### 1. 初始化 SQLite 資料庫

執行以下命令創建資料庫和表結構：

```bash
python init_sqlite_db.py
```

這會創建 `medical_appointments.db` 檔案，並自動建立所需的資料表。

### 2. 配置應用程式

應用程式預設使用 SQLite。如果需要切換到 MySQL，請在 `.env` 文件中添加：

```env
USE_SQLITE=false
```

### 3. 啟動應用程式

```bash
python app.py
```

應用程式會自動：
- 連接到 SQLite 資料庫
- 如果表不存在，自動創建表結構
- 開始提供預約服務

## SQLite vs MySQL

### SQLite 優點
- ✅ 無需安裝額外服務
- ✅ 資料庫是單一檔案，易於備份和遷移
- ✅ 適合開發和測試
- ✅ 零配置，開箱即用

### MySQL 優點
- ✅ 適合生產環境
- ✅ 支援多用戶並發
- ✅ 更好的效能（大量資料時）
- ✅ 支援遠端連接（如 Azure）

## 資料庫檔案位置

SQLite 資料庫檔案位於專案根目錄：
```
medical_appointments.db
```

## 資料表結構

`medical_appointments` 表包含以下欄位：

| 欄位 | 類型 | 說明 |
|------|------|------|
| id | INTEGER | 主鍵，自動遞增 |
| username | VARCHAR(100) | 使用者帳號 |
| patient_name | VARCHAR(100) | 病患姓名 |
| patient_phone | VARCHAR(20) | 聯絡電話 |
| department | VARCHAR(100) | 科別 |
| doctor_name | VARCHAR(100) | 醫師姓名 |
| appointment_date | DATE | 預約日期 |
| appointment_time | TIME | 預約時間 |
| symptoms | TEXT | 症狀描述（可選） |
| status | VARCHAR(20) | 預約狀態（pending/confirmed/cancelled） |
| created_at | TIMESTAMP | 建立時間 |
| updated_at | TIMESTAMP | 更新時間 |

## 備份資料庫

SQLite 資料庫是單一檔案，備份非常簡單：

```bash
# Windows
copy medical_appointments.db medical_appointments.db.backup

# Linux/Mac
cp medical_appointments.db medical_appointments.db.backup
```

## 查看資料庫內容

可以使用 SQLite 命令行工具查看資料：

```bash
sqlite3 medical_appointments.db

# 在 SQLite 提示符下：
.tables                    # 查看所有表
.schema medical_appointments  # 查看表結構
SELECT * FROM medical_appointments;  # 查看所有記錄
```

## 測試連接

執行測試腳本驗證資料庫連接：

```bash
python test_sqlite_connection.py
```

## 切換資料庫

### 從 SQLite 切換到 MySQL

1. 在 `.env` 文件中設置：
   ```env
   USE_SQLITE=false
   DB_HOST=your_mysql_host
   DB_USER=your_username
   DB_PASSWORD=your_password
   DB_NAME=your_database
   ```

2. 重新啟動應用程式

### 從 MySQL 切換到 SQLite

1. 在 `.env` 文件中設置：
   ```env
   USE_SQLITE=true
   ```

2. 執行初始化腳本：
   ```bash
   python init_sqlite_db.py
   ```

3. 重新啟動應用程式

## 常見問題

### Q: 資料庫檔案在哪裡？
A: `medical_appointments.db` 位於專案根目錄。

### Q: 如何重置資料庫？
A: 刪除 `medical_appointments.db` 檔案，然後重新執行 `init_sqlite_db.py`。

### Q: 資料庫檔案可以上傳到 GitHub 嗎？
A: 不建議。資料庫檔案已添加到 `.gitignore`，不會被上傳。

### Q: SQLite 和 MySQL 的資料可以互相遷移嗎？
A: 可以，但需要手動匯出和匯入資料。表結構是兼容的。

## 注意事項

- SQLite 資料庫檔案會隨著使用而增長，請定期備份
- 如果資料量很大（超過 100MB），建議使用 MySQL
- 多個進程同時寫入 SQLite 可能會導致鎖定，建議單進程使用

