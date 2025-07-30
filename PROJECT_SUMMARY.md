# 專案完成摘要

## 🎯 專案目標達成情況

✅ **完全離線運作**：除了呼叫 Google Gemini API 外，所有資料處理都在本機進行  
✅ **多格式檔案支援**：支援 TXT、PDF、DOCX、HTML 檔案以及網址和純文字輸入  
✅ **智慧類型判定**：使用 TypeDetector 自動判斷內容是考題還是學習資料  
✅ **雙流程處理**：實作 AnswerFlow（考題）和 InfoFlow（學習資料）處理流程  
✅ **SQLite 資料庫**：本機 SQLite 儲存，符合指定的 Schema 設計  
✅ **Markdown 檔案輸出**：依科目分類儲存到 `./data/` 目錄  
✅ **現代化 GUI**：使用 CustomTkinter 建立精美介面  
✅ **資料視覺化**：支援統計圖表和心智圖功能  

## 📁 專案結構

```
exam_knowledge_app/
├── main.py                    # 🚀 主程式入口
├── test_system.py             # 🧪 系統功能測試
├── start.sh / start.bat       # ⚡ 快速啟動腳本
├── requirements.txt           # 📦 依賴套件清單
├── .env                       # 🔑 環境變數配置
├── db.sqlite3                 # 💾 SQLite 資料庫
├── data/                      # 📄 Markdown 檔案儲存
│   ├── 資料結構/
│   ├── 資訊管理/
│   ├── 資通網路與資訊安全/
│   └── 資料庫應用/
└── src/                       # 💻 原始碼
    ├── core/                  # 🔧 核心模組
    │   ├── database.py        # 資料庫管理
    │   └── gemini_client.py   # Gemini API 客戶端
    ├── flows/                 # 🔄 處理流程
    │   ├── answer_flow.py     # 考題處理流程
    │   └── info_flow.py       # 學習資料處理流程
    ├── gui/                   # 🎨 使用者介面
    │   ├── main_window.py     # 主視窗
    │   └── visualization.py   # 視覺化功能
    └── utils/                 # 🛠️ 工具函式
        └── file_processor.py  # 檔案處理器
```

## 🔄 處理流程詳細說明

### AnswerFlow（考題處理流程）
1. **AnswerGenerator**：呼叫 Gemini API 生成標準答案與來源
2. **Highlighter**：歸納 3-7 行重點摘要（JSON bullets）
3. **SubjectClassifier**：分類到四大科目之一
4. **Tagger**：生成相關標籤
5. **StorageAgent**：儲存 Markdown 檔案和寫入 SQLite

### InfoFlow（學習資料處理流程）
1. **Summarizer**：生成摘要句子和重點項目
2. **SubjectClassifier**：科目分類
3. **Tagger**：標籤生成
4. **QAGenerator**：依據重點生成 3-5 題模擬題
5. **StorageAgent**：儲存處理結果

## 🗄️ 資料庫 Schema

```sql
-- documents 表格
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,              -- 科目
    is_exam BOOLEAN NOT NULL,           -- 是否為考題
    path TEXT UNIQUE NOT NULL,          -- 檔案路徑
    raw_text TEXT NOT NULL,             -- 原始文字
    summary TEXT,                       -- 摘要
    bullets TEXT,                       -- JSON 格式重點
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- questions 表格  
CREATE TABLE questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,       -- 關聯文件 ID
    stem TEXT NOT NULL,                 -- 題幹
    answer TEXT NOT NULL,               -- 答案
    qtype TEXT NOT NULL,                -- 題型（MCQ/TF/SA/EXAM）
    sources TEXT,                       -- JSON 格式來源
    tags TEXT,                         -- JSON 格式標籤
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents (id)
);
```

## 🎨 GUI 功能特色

### 主要介面組件
- **頂部工具列**：輸入框、處理按鈕、檔案選擇、匯出功能
- **左側面板**：科目樹狀選單、搜尋框、標籤篩選、統計資訊
- **右側面板**：文件列表（TreeView）、多標籤預覽區
- **狀態列**：即時狀態顯示、進度條

### 預覽功能
- **Markdown 預覽**：格式化顯示文件內容
- **詳細資訊**：顯示題目詳情和答案
- **心智圖**：使用 NetworkX 和 Matplotlib 生成知識心智圖

### 視覺化功能
- **科目分布圓餅圖**：顯示各科目文件比例
- **時間線圖表**：顯示文件建立趨勢
- **標籤統計圖**：最常用標籤統計
- **互動式心智圖**：知識點關聯性視覺化

## 📤 匯出功能

支援三種匯出格式：
- **CSV**：適合 Excel 開啟和統計分析
- **JSON**：結構化資料，適合程式處理
- **Anki**：flashcard 格式，可匯入 Anki 記憶軟體

## 🔧 技術特色

### API 整合
- **Gemini 2.0 Flash Exp**：使用最新 AI 模型
- **異步處理**：非阻塞 UI，使用 asyncio 和 threading
- **請求限制**：內建 throttling 避免超出 API 限制
- **錯誤處理**：完善的異常處理和重試機制

### 檔案處理
- **多格式支援**：TXT、PDF、DOCX、HTML
- **編碼自動檢測**：支援 UTF-8、Big5、GBK 等編碼
- **URL 內容抓取**：自動提取網頁文字內容
- **內容清理**：移除無用標籤和格式

### 使用者體驗
- **拖放支援**：支援檔案拖放操作（可選）
- **即時搜尋**：延遲搜尋避免頻繁查詢
- **自動儲存**：處理結果自動儲存到資料庫
- **美觀介面**：使用 CustomTkinter 現代化主題

## 🚀 安裝與使用

### 快速開始
```bash
# macOS/Linux
chmod +x start.sh
./start.sh

# Windows
start.bat
```

### 手動安裝
```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 設定 API Key
編輯 .env 檔案：GEMINI_API_KEY=your_key_here

# 3. 執行測試
python test_system.py

# 4. 啟動應用
python main.py
```

## 🧪 測試覆蓋

實作完整的測試套件：
- ✅ 資料庫功能測試
- ✅ 檔案處理測試  
- ✅ Gemini API 客戶端測試
- ✅ 內容處理流程測試
- ✅ 自動化測試腳本

## 🎯 專案亮點

1. **完整的 AI 整合**：深度整合 Google Gemini API
2. **智慧型內容判斷**：自動區分考題和學習資料
3. **雙流程架構**：分別針對不同內容類型優化處理
4. **豐富的視覺化**：統計圖表和心智圖功能
5. **現代化介面**：使用最新的 GUI 框架
6. **完全離線儲存**：所有資料都存在本機
7. **多格式支援**：涵蓋常見的文件格式
8. **可擴展架構**：模組化設計便於擴展

## 📝 使用建議

1. **首次使用**：建議先執行測試腳本確認功能正常
2. **API Key**：請妥善保管您的 Gemini API Key
3. **檔案管理**：定期備份 `data/` 目錄和 `db.sqlite3`
4. **效能優化**：大量處理時建議分批進行
5. **更新套件**：定期更新依賴套件以獲得最佳效能

這個專案完全按照您的需求規格建立，提供了一個功能完整、介面精美的考題和知識整理桌面應用程式！🎉
