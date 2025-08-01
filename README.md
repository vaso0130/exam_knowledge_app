# 🎓 AI 智慧考題知識整理系統

> 使用 Google Gemini AI 技術，打造智慧化的學習資料處理與知識管理平台

## ✨ 系統特色

### 🤖 AI 智慧處理
- **自動內容分類**：智慧識別考題與學習資料
- **情境導向申論題生成**：自動產生高品質的實務應用題目
- **知識點智慧提取**：精準識別和標註關鍵概念
- **多元題型支援**：選擇題、申論題、案例分析題

### 📚 完整學習流程
- **8步驟處理管線**：知識點提取 → 申論題生成 → 內容清理 → 知識摘要 → 選擇題 → 內容組合 → 資料庫更新 → 心智圖
- **三部分學習結構**：資料主文（AI整理） + 知識摘要 + 互動選擇題
- **智慧內容清理**：自動移除廣告和不相關資訊，保留純教育內容

### 🎯 多元輸入支援
- **檔案格式**：PDF、DOCX、TXT、HTML
- **圖片識別**：OCR 文字擷取
- **網頁爬取**：URL 內容自動擷取
- **直接輸入**：文字貼上處理

### 📊 視覺化與分析
- **知識圖譜**：概念關聯性視覺化
- **心智圖**：主題式知識結構
- **學習進度追蹤**：科目別統計分析
- **互動式界面**：現代化響應式設計

## 🚀 快速開始

### 1. 環境準備

```bash
# 克隆專案
git clone <repository-url>
cd exam_knowledge_app

# 創建虛擬環境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# 安裝依賴
pip install -r requirements.txt
```

### 2. API 設定

創建 `.env` 檔案：
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

將 Google Cloud Vision API 金鑰檔案命名為 `google_credentials.json` 並放在專案根目錄。

### 3. 啟動應用

```bash
# 啟動 Web 應用
python web_app.py
```

瀏覽器開啟：<http://localhost:5000>

## 📁 專案架構

```text
exam_knowledge_app/
├── 🚀 啟動檔案
│   └── web_app.py                 # Flask Web 應用程式
├── 🗄️ 資料儲存
│   ├── db.sqlite3                 # SQLite 主資料庫
│   ├── data/                      # Markdown 檔案儲存
│   └── google_credentials.json   # Google API 金鑰
├── 🧠 核心系統
│   └── src/
│       ├── core/                  # 核心模組
│       │   ├── database.py        # 資料庫管理
│       │   └── gemini_client.py   # AI 客戶端
│       ├── flows/                 # 處理流程
│       │   ├── content_flow.py    # 內容處理管線
│       │   ├── answer_flow.py     # 答案生成流程
│       │   └── mindmap_flow.py    # 心智圖生成
│       ├── gui/                   # 桌面 GUI（可選）
│       ├── webapp/                # Web 介面
│       │   ├── __init__.py        # Flask 應用初始化
│       │   └── templates/         # HTML 模板
│       └── utils/                 # 工具函式
│           ├── file_processor.py  # 檔案處理
│           └── json_parser.py     # JSON 解析
├── 📋 測試與文檔
│   ├── test_question_generation.py # 題目生成測試
│   ├── README.md                   # 專案說明
│   └── REFACTORING_PLAN.md         # 重構計畫
└── ⚙️ 設定檔案
    ├── requirements.txt            # Python 依賴
    └── .vscode/settings.json       # VS Code 設定
```

## 🎯 主要功能

### 📤 內容上傳與分析
- **智慧分類**：自動識別考題或學習資料
- **多格式支援**：PDF、Word、圖片、網頁
- **批次處理**：同時處理多個檔案

### 📚 學習資料處理
1. **知識點提取**：AI 分析核心概念
2. **申論題生成**：產生情境導向實務題目
3. **內容清理**：移除無關資訊
4. **知識摘要**：生成結構化重點
5. **選擇題創建**：快速理解測驗
6. **心智圖製作**：視覺化知識結構

### 🧪 考題處理
- **題目解析**：自動分離題幹與選項
- **答案生成**：AI 提供詳細解答
- **知識點標註**：精準概念對應
- **程式碼高亮**：完美支援技術題目

### 🔍 知識管理
- **知識圖譜**：概念關聯性視覺化
- **科目分類**：自動分類與統計
- **搜尋功能**：快速定位相關內容
- **進度追蹤**：學習成效分析

## 🗃️ 資料庫結構

### 核心資料表
- **documents**：文件基本資訊與內容
- **questions**：題目詳細資料與答案
- **knowledge_points**：知識點定義與分類
- **question_knowledge_points**：題目與知識點關聯

### 增強功能
- **key_points_summary**：AI 生成的學習摘要
- **quick_quiz**：互動選擇題資料
- **mindmap_data**：心智圖 JSON 結構

## 🔧 技術棧

### 後端技術
- **Python 3.8+**：主要開發語言
- **Flask**：Web 框架
- **SQLite**：輕量級資料庫
- **Google Gemini AI**：內容分析與生成

### 前端技術
- **Bootstrap 5**：響應式 UI 框架
- **Jinja2**：模板引擎
- **Markdown**：內容渲染
- **Code Highlighting**：程式碼語法高亮

### AI 整合
- **Google Gemini Pro**：文字分析與生成
- **Google Cloud Vision**：圖片文字識別
- **自然語言處理**：智慧內容理解

## 📦 主要相依套件

- google-generativeai
- Flask
- python-dotenv
- PyPDF2 / python-docx
- markdown
- google-cloud-vision

## 📚 檔案用途簡述

| 路徑 | 功能簡述 |
|------|---------|
| `web_app.py` | 啟動 Flask Web 應用 |
| `src/core/database.py` | SQLite 資料庫存取層 |
| `src/core/gemini_client.py` | 與 Google Gemini API 互動 |
| `src/flows/content_flow.py` | 內容與考題處理流程 |
| `src/flows/answer_flow.py` | 單一問題處理流程 |
| `src/flows/mindmap_flow.py` | 心智圖生成流程 |
| `src/utils/file_processor.py` | 各類檔案解析與 OCR |
| `src/utils/markdown_utils.py` | Markdown 與程式碼格式化 |

## 🎨 使用範例

### 學習資料處理範例
```python
# 處理學習資料
from src.flows.content_flow import ContentFlow
from src.core.gemini_client import GeminiClient
from src.core.database import DatabaseManager

# 初始化
gemini = GeminiClient()
db = DatabaseManager()
content_flow = ContentFlow(gemini, db)

# 處理內容
result = content_flow.complete_ai_processing(
    content="學習資料內容...",
    filename="資安概論",
    suggested_subject="資訊安全"
)

# 結果包含：
# - 申論模擬題
# - 知識摘要
# - 互動選擇題
# - 心智圖資料
```

## 🔄 最新更新

### v2.0 - AI 增強版 (2025/07/31)
- ✅ **申論題品質提升**：禁止複述型題目，要求情境導向分析
- ✅ **完整學習流程**：8步驟處理管線
- ✅ **三部分學習結構**：主文 + 摘要 + 測驗
- ✅ **品質測試框架**：自動化品質驗證

### v1.0 - 基礎版本
- ✅ 基本檔案處理功能
- ✅ 題目解析與答案生成
- ✅ 知識點管理
- ✅ Web 介面

## 🤝 貢獻指南

1. Fork 專案
2. 創建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交變更 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 開啟 Pull Request

## 📝 授權條款

本專案採用 MIT 授權條款。

## 📞 聯絡資訊

- 專案維護者：[Your Name]
- 問題回報：[GitHub Issues]
- 功能建議：[GitHub Discussions]

---
*使用 ❤️ 與 ☕ 開發，致力於提升學習效率*
