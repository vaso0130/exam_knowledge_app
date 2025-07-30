# 考題/知識整理桌面應用

## 功能特色
- 支援多種檔案格式 (TXT, PDF, DOCX, HTML)
- 智慧題型判斷與處理
- Google Gemini AI 整合
- 精美 GUI 介面
- 離線資料庫儲存
- 資料視覺化與心智圖

## 安裝與執行

1. 安裝依賴套件：
```bash
pip install -r requirements.txt
```

2. 設定 Gemini API Key：
編輯 `.env` 檔案，填入您的 Google Gemini API Key

3. 執行應用程式：
```bash
python main.py
```

## 目錄結構
```
exam_knowledge_app/
├── main.py                 # 主程式入口
├── db.sqlite3             # SQLite 資料庫
├── data/                  # 儲存 Markdown 檔案
├── src/
│   ├── core/              # 核心模組
│   ├── flows/             # 處理流程
│   ├── gui/               # 使用者介面
│   └── utils/             # 工具函式
└── requirements.txt       # 依賴套件
```

## 資料庫 Schema
- `documents`: 文件資料表
- `questions`: 題目資料表
