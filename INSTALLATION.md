# 考題/知識整理桌面應用 - 安裝指南

## 系統需求

- Python 3.7 或更高版本
- 作業系統：Windows 10/11, macOS 10.14+, Linux
- 記憶體：建議 4GB 以上
- 硬碟空間：至少 1GB 可用空間

## 安裝步驟

### 1. 下載專案
```bash
# 如果您有 git，可以 clone 專案
git clone <repository-url>
cd exam_knowledge_app

# 或者直接下載解壓縮到資料夾
```

### 2. 安裝 Python 依賴套件
```bash
# 使用 pip 安裝必要套件
pip install -r requirements.txt

# 如果遇到安裝問題，可以逐一安裝核心套件
pip install google-generativeai python-dotenv customtkinter Pillow
pip install python-docx PyPDF2 beautifulsoup4 requests
```

### 3. 設定 Google Gemini API Key

1. 前往 [Google AI Studio](https://makersuite.google.com/app/apikey)
2. 建立新的 API Key
3. 編輯專案根目錄下的 `.env` 檔案：
```
GEMINI_API_KEY=your_actual_api_key_here
```

### 4. 執行應用程式
```bash
# 執行主程式
python main.py

# 或者先執行測試確認功能正常
python test_system.py
```

## 功能說明

### 主要功能
1. **多格式檔案支援**：TXT, PDF, DOCX, HTML
2. **智慧類型判斷**：自動識別考題或學習資料
3. **AI 內容處理**：使用 Gemini AI 生成答案、摘要、標籤
4. **資料庫儲存**：SQLite 本地儲存，支援搜尋和篩選
5. **精美 GUI**：現代化使用者介面，支援拖放操作
6. **資料視覺化**：統計圖表和心智圖

### 處理流程
1. **AnswerFlow（考題處理）**：
   - 自動生成標準答案
   - 歸納重點摘要
   - 科目分類和標籤生成
   - 儲存為 Markdown 格式

2. **InfoFlow（資料處理）**：
   - 文本摘要和重點提取
   - 科目分類和標籤生成
   - 生成模擬練習題
   - 儲存為 Markdown 格式

### 資料結構
```
data/
├── 資料結構/
├── 資訊管理/
├── 資通網路與資訊安全/
└── 資料庫應用/
```

## 使用方法

### 1. 輸入內容
- **拖放檔案**：直接將檔案拖到應用程式視窗
- **選擇檔案**：點擊「選擇檔案」按鈕
- **貼上網址**：在輸入框貼上網頁連結
- **直接輸入**：在輸入框直接輸入文字內容

### 2. 自動處理
系統會自動：
- 判斷內容類型（考題或學習資料）
- 選擇對應的處理流程
- 呼叫 Gemini AI 進行處理
- 儲存結果到資料庫和檔案

### 3. 瀏覽和搜尋
- **科目篩選**：左側面板選擇科目
- **關鍵字搜尋**：輸入關鍵字搜尋內容
- **標籤篩選**：選擇標籤進行篩選
- **預覽文件**：點擊文件查看詳細內容

### 4. 資料匯出
支援匯出格式：
- **CSV**：表格格式，可用 Excel 開啟
- **JSON**：結構化資料格式
- **Anki**：flashcard 格式，可匯入 Anki 記憶軟體

## 常見問題

### Q: 無法連接 Gemini API
A: 請檢查：
1. API Key 是否正確設定在 `.env` 檔案中
2. 網路連線是否正常
3. API Key 是否有效且有足夠的使用額度

### Q: 某些檔案無法處理
A: 請確認：
1. 檔案格式是否支援（TXT, PDF, DOCX, HTML）
2. 檔案是否損壞
3. 對於 PDF，請確認是否包含可提取的文字內容

### Q: GUI 無法正常顯示
A: 請嘗試：
1. 更新 tkinter：`pip install --upgrade tkinter`
2. 安裝 customtkinter：`pip install customtkinter`
3. 確認系統支援圖形介面

### Q: 處理速度很慢
A: 這是正常現象，因為：
1. AI 處理需要時間
2. 網路請求需要等待
3. 系統有請求頻率限制

## 開發資訊

### 專案結構
```
exam_knowledge_app/
├── main.py                 # 主程式入口
├── test_system.py          # 系統測試
├── requirements.txt        # 依賴套件
├── .env                   # 環境變數設定
├── db.sqlite3             # SQLite 資料庫
├── data/                  # Markdown 檔案儲存
└── src/                   # 原始碼
    ├── core/              # 核心模組
    ├── flows/             # 處理流程
    ├── gui/               # 使用者介面
    └── utils/             # 工具函式
```

### 資料庫 Schema
```sql
-- 文件表
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    is_exam BOOLEAN NOT NULL,
    path TEXT UNIQUE NOT NULL,
    raw_text TEXT NOT NULL,
    summary TEXT,
    bullets TEXT,  -- JSON 格式
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 題目表
CREATE TABLE questions (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL,
    stem TEXT NOT NULL,
    answer TEXT NOT NULL,
    qtype TEXT NOT NULL,
    sources TEXT,  -- JSON 格式
    tags TEXT,     -- JSON 格式
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents (id)
);
```

## 技術支援

如果您遇到問題或需要協助，請：
1. 先執行 `python test_system.py` 檢查系統功能
2. 檢查是否有錯誤訊息
3. 確認所有依賴套件都已正確安裝
4. 檢查 API Key 設定是否正確

## 更新日誌

### v1.0.0
- 基本功能實作
- 支援多種檔案格式
- Gemini AI 整合
- 現代化 GUI 介面
- 資料庫儲存和搜尋
- 資料視覺化功能
