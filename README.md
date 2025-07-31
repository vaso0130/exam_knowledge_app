# 考題/知識整理 Web 應用程式

## 功能特色
- 支援多種檔案格式 (TXT, PDF, DOCX, HTML)
- 智慧題型判斷與處理
- Google Gemini AI 整合
- 現代化 Web 介面
- 離線資料庫儲存
- 知識點管理與分類

## 安裝與執行

1. 安裝依賴套件：

```bash
pip install -r requirements.txt
```

2. 設定 API Keys：

- 編輯 `.env` 檔案，填入您的 Google Gemini API Key
- 將 Google Cloud Vision API 的服務帳號金鑰檔案命名為 `google_credentials.json` 並放在專案根目錄

3. 執行 Web 應用程式：

```bash
python web_app.py
```

然後在瀏覽器開啟 <http://localhost:5000>

## 目錄結構

```text
exam_knowledge_app/
├── web_app.py             # Web 應用程式啟動檔
├── db.sqlite3             # SQLite 資料庫
├── data/                  # 儲存 Markdown 檔案
├── src/
│   ├── core/              # 核心模組
│   ├── flows/             # 處理流程
│   ├── webapp/            # Flask Web UI 模組
│   └── utils/             # 工具函式
└── requirements.txt       # 依賴套件
```

## 資料庫 Schema

- `documents`: 文件資料表
- `questions`: 題目資料表
- `knowledge_points`: 知識點資料表
