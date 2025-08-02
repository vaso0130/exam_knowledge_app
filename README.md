# 🎓 AI 智慧考題知識整理系統

> 使用 Google Gemini AI 技術，打造智慧化的學習資料處理與知識管理平台

## ✨ 系統特色

### 🤖 AI 智慧處理
- **自動內容分類**：智慧識別考題與學習資料
- **情境導向申論題生成**：自動產生高品質的實務應用題目
- **知識點智慧提取**：精準識別和標註關鍵概念
- **多元題型支援**：選擇題、申論題、案例分析題
- **🆕 解題技巧生成**：AI 智慧分析題目特點，提供專業解題策略與學習建議
- **🆕 完全信任 AI 輸出**：移除人工二次加工，完全採用 AI 原始輸出，確保內容自然流暢

### 📚 完整學習流程
- **8步驟處理管線**：知識點提取 → 申論題生成 → 內容清理 → 知識摘要 → 選擇題 → 內容組合 → 資料庫更新 → 心智圖
- **🚀 並行處理架構**：**重大技術突破**！使用 asyncio.gather 實現真正並行處理，多題目同時分析，處理速度提升 3-5 倍
- **三部分學習結構**：資料主文（AI整理） + 知識摘要 + 互動選擇題
- **智慧內容清理**：自動移除廣告和不相關資訊，保留純教育內容

### 🎯 多元輸入支援
- **檔案格式**：PDF、DOCX、TXT、HTML
- **圖片識別**：OCR 文字擷取
- **網頁爬取**：URL 內容自動擷取
- **直接輸入**：文字貼上處理

### 📊 視覺化與分析
- **知識圖譜**：概念關聯性視覺化
- **🆕 心智圖優化**：全新的 Mermaid.js 心智圖生成邏輯，支援複雜知識結構與概念關聯
- **學習進度追蹤**：科目別統計分析
- **互動式界面**：現代化響應式設計

### 🚀 生產環境部署
- **WSGI 支援**：使用 Waitress 作為生產級 WSGI 伺服器
- **🆕 資料庫架構完善**：MySQL 生產環境完整支援，包含 async_jobs 非同步工作管理表
- **環境變數配置**：彈性的部署設定管理
- **🆕 資料庫級非同步處理**：AsyncProcessor 改用資料庫儲存工作狀態，告別檔案系統，提升穩定性與可擴展性

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

### 2. 環境變數設定

創建 `.env` 檔案並設定以下參數：

#### Windows 環境
```env
# Google Gemini AI API 金鑰
GEMINI_API_KEY=your_gemini_api_key_here

# 資料庫設定（預設使用 SQLite）
DATABASE_URL=sqlite:///./db.sqlite3
# MySQL 範例：DATABASE_URL=mysql+mysqlconnector://user:password@localhost/exam_db

# Flask 設定
FLASK_SECRET_KEY=your-super-secret-key-here

# 檔案儲存路徑（使用相對路徑避免問題）
FILE_STORAGE_PATH=./uploads
```

#### WSL 環境（推薦配置）
```env
# Google Gemini AI API 金鑰
GEMINI_API_KEY=your_gemini_api_key_here

# 資料庫設定（建議使用絕對路徑或相對路徑）
DATABASE_URL=sqlite:////home/username/exam_app/db.sqlite3
# 或使用相對路徑：DATABASE_URL=sqlite:///./db.sqlite3

# Flask 設定
FLASK_SECRET_KEY=your-super-secret-key-here

# 檔案儲存路徑（WSL 原生路徑）
FILE_STORAGE_PATH=/home/username/exam_app/uploads
# 或使用相對路徑：FILE_STORAGE_PATH=./uploads
```

**Google Cloud Vision API 設定**：
將 Google Cloud Vision API 金鑰檔案命名為 `google_credentials.json` 並放在專案根目錄。

### 🔐 FLASK_SECRET_KEY 詳細說明

`FLASK_SECRET_KEY` 是 Flask 應用程式的安全核心，用於：

#### 🎯 **主要用途**
- **Session 加密**：保護使用者 session 資料不被竄改
- **CSRF 保護**：防止跨站請求偽造攻擊
- **Flash 訊息安全**：加密系統訊息
- **Cookie 簽名**：確保 cookies 完整性

#### 🔑 **安全金鑰生成**

```bash
# 方法 1：使用 Python secrets 模組（推薦）
python -c "import secrets; print(secrets.token_hex(32))"

# 方法 2：使用 openssl
openssl rand -hex 32

# 方法 3：使用 uuid4
python -c "import uuid; print(str(uuid.uuid4()).replace('-', ''))"
```

#### ⚠️ **安全注意事項**
- 🚫 **絕對不要使用**：`"your-secret-key"`、`"dev"`、`"123456"` 等簡單字串
- ✅ **必須使用**：至少 32 字元的隨機字串
- 🔒 **保密性**：不要提交到版本控制系統
- 🔄 **定期更換**：生產環境建議定期更新

#### 💡 **在程式中的使用**
```python
# Flask 應用程式會這樣使用
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

# 支援的功能
session['user_data'] = data    # 加密 session
flash('操作成功')              # 安全 flash 訊息
csrf_token = generate_csrf()   # CSRF 保護
```

### ⚠️ WSL 路徑配置特別注意事項

#### 問題分析
1. **Windows 路徑格式在 WSL 中失效**
2. **相對路徑基準點可能不同** 
3. **檔案權限問題**

#### 解決方案
```bash
# 1. 建議將專案完全放在 WSL 檔案系統中
cd ~
git clone <repository-url>
cd exam_knowledge_app

# 2. 檢查路徑設定
pwd  # 確認當前路徑
ls -la  # 檢查檔案權限

# 3. 創建 WSL 專用的 .env
cat > .env << 'EOF'
GEMINI_API_KEY=your_key_here
DATABASE_URL=sqlite:///./db.sqlite3
FLASK_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
FILE_STORAGE_PATH=./uploads
EOF

# 4. 確保目錄存在且有正確權限
mkdir -p uploads
chmod 755 uploads
```

#### 路徑策略建議
| 檔案 | Windows | WSL | 建議 |
|------|---------|-----|------|
| 專案目錄 | `C:\project` | `~/exam_app` | 🟢 WSL 原生 |
| 資料庫 | 相對路徑 | 相對路徑 | 🟢 `./db.sqlite3` |
| 上傳檔案 | 相對路徑 | 相對路徑 | 🟢 `./uploads` |
| Google 金鑰 | 專案根目錄 | 專案根目錄 | 🟢 相對路徑 |

### 3. 資料庫初始化

系統啟動時會自動創建所需的資料表，支援：
- **SQLite**（預設）：適合開發和小型部署
- **MySQL**：適合生產環境，需要設定 `DATABASE_URL`

### 4. 啟動應用

#### 開發模式
```bash
# 啟動開發伺服器
python web_app.py
```

#### 生產模式
```bash
# 使用 Waitress（推薦用於 Windows 或簡單部署）
python wsgi.py

# 使用 Gunicorn（推薦用於 Linux 生產環境，需額外安裝）
# 注意：Gunicorn 在 Windows 上支援有限，建議 Linux 環境使用
# 安裝：pip install gunicorn
gunicorn --bind 0.0.0.0:8001 --workers 4 wsgi:app

# 使用 Granian（最新高性能選擇，支援 WSL/Linux）
# 安裝：pip install granian
granian --interface wsgi --host 0.0.0.0 --port 8001 --workers 4 wsgi:app

# Gunicorn 進階配置
gunicorn --bind 0.0.0.0:8001 \
         --workers 4 \
         --worker-class gevent \
         --worker-connections 1000 \
         --timeout 120 \
         --keep-alive 2 \
         --max-requests 1000 \
         --max-requests-jitter 100 \
         wsgi:app
```

瀏覽器開啟：<http://localhost:8001>

## 🔧 常見問題解決

### Cloudflare 524 Timeout 錯誤

#### 問題描述
當上傳檔案進行 AI 分析時，可能遇到：
```
A timeout occurred Error code 524
Visit cloudflare.com for more information.
```

#### 原因分析
- **Cloudflare 超時限制**：免費方案 100 秒，Pro 方案 600 秒
- **AI 處理耗時**：Gemini 分析大文件、OCR 識別、8 步驟處理管線
- **服務實際正常**：後端仍在處理，只是 CDN 誤判為超時

#### ✅ 解決方案：非同步處理

系統已內建**非同步處理模式**來解決此問題：

1. **上傳檔案時**：
   - ✅ 勾選「🚀 非同步處理模式」（預設已勾選）
   - 📤 檔案立即上傳，返回處理狀態頁面
   - ⏱️ 即時查看處理進度和狀態

2. **處理流程**：
   ```
   上傳檔案 → 立即回應 → 背景處理 → 即時更新進度 → 完成通知
   ```

3. **技術優勢**：
   - 🚫 避免 Cloudflare 超時
   - 📊 即時進度追蹤
   - 🔄 自動狀態更新
   - 📱 支援大檔案處理

#### 🎛️ 手動選擇模式

- **非同步模式**（推薦）：適合生產環境、大檔案、複雜處理
- **同步模式**：適合小檔案、測試環境

#### 📋 進度監控

非同步處理期間可以：
- 📈 查看即時處理進度
- 📝 了解當前處理步驟
- 🔔 接收完成/錯誤通知
- 🔗 直接跳轉到結果頁面

## 🏭 生產環境部署建議

### WSGI 伺服器選擇

| 伺服器 | 適用場景 | 優勢 | 注意事項 |
|--------|----------|------|----------|
| **Waitress** | Windows 部署、中小型應用 | 跨平台兼容、配置簡單 | 單進程，適合 1-10 並發 |
| **Gunicorn** | Linux 生產環境、高負載應用 | 高性能、豐富配置選項 | ⚠️ Windows 支援有限 |
| **Granian** | WSL/Linux 高性能部署 | 🚀 極高性能（Rust）、HTTP/2 | 🆕 較新，需 Python 3.8+ |

### 完整生產環境架構

#### Linux 環境（推薦）
```bash
# 1. 安裝 Gunicorn（Linux 環境）
pip install gunicorn[gevent]

# 2. 或安裝 Granian（推薦高性能選擇）
pip install granian

# 3. 使用 systemd 服務管理
sudo nano /etc/systemd/system/exam-app.service

# 4. 配置 Nginx 反向代理
sudo nano /etc/nginx/sites-available/exam-app

# 5. 啟動服務
sudo systemctl enable exam-app
sudo systemctl start exam-app
```

#### WSL 環境（Windows 用戶推薦）
```bash
# 1. 在 WSL2 中安裝 Granian
pip install granian

# 2. 啟動高性能伺服器
granian --interface wsgi --host 0.0.0.0 --port 8001 --workers 4 wsgi:app

# 3. 進階配置
granian --interface wsgi \
        --host 0.0.0.0 \
        --port 8001 \
        --workers 4 \
        --threads 2 \
        --backlog 1024 \
        --http2 \
        wsgi:app

# 4. Windows 主機可透過 localhost:8001 存取
```

#### Windows 環境
```powershell
# 1. 使用 Waitress（Windows 原生支援）
pip install waitress

# 2. 創建 Windows 服務（使用 NSSM 或 sc）
# 下載 NSSM: https://nssm.cc/
nssm install "ExamApp" python "C:\path\to\wsgi.py"

# 3. 配置 IIS 或 Apache 作為反向代理（可選）
# 或直接使用 Waitress 的內建伺服器
```

## 📁 專案架構

```text
exam_knowledge_app/
├── 🚀 啟動檔案
│   ├── web_app.py                 # Flask 開發伺服器
│   └── wsgi.py                    # WSGI 生產伺服器
├── 🗄️ 資料儲存
│   ├── db.sqlite3                 # SQLite 主資料庫
│   ├── uploads/                   # 上傳檔案暫存
│   └── google_credentials.json   # Google API 金鑰
├── 🧠 核心系統
│   └── src/
│       ├── core/                  # 核心模組
│       │   ├── database.py        # 資料庫管理（支援 SQLite/MySQL）
│       │   └── gemini_client.py   # AI 客戶端
│       ├── flows/                 # 處理流程
│       │   ├── content_flow.py    # 內容處理管線
│       │   ├── answer_flow.py     # 答案生成流程
│       │   ├── mindmap_flow.py    # 心智圖生成
│       │   └── flow_manager.py    # 統一流程管理
│       ├── webapp/                # Web 介面
│       │   ├── __init__.py        # Flask 應用初始化
│       │   └── templates/         # HTML 模板
│       └── utils/                 # 工具函式
│           ├── file_processor.py  # 檔案處理
│           ├── json_parser.py     # JSON 解析
│           ├── markdown_utils.py  # Markdown 工具
│           └── playwright_scraper.py # 網頁爬取
├── 📋 設定與文檔
│   ├── .env                       # 環境變數設定
│   ├── requirements.txt           # Python 依賴
│   ├── README.md                  # 專案說明
│   └── REFACTORING_PLAN.md        # 重構計畫
└── ⚙️ 額外檔案
    └── .vscode/settings.json      # VS Code 設定
```

## 📂 主要程式檔案用途

| 檔案 | 說明 |
|------|------|
| `web_app.py` | 啟動 Flask Web 應用 |
| `src/core/gemini_client.py` | Gemini API 封裝與提示組裝 |
| `src/core/database.py` | SQLite 資料存取層 |
| `src/flows/content_flow.py` | 學習資料與考題處理流程 |
| `src/flows/answer_flow.py` | 單一問題解析與知識點提取 |
| `src/flows/mindmap_flow.py` | 依知識點產生心智圖 |
| `src/flows/flow_manager.py` | 對外統一流程介面 |
| `src/utils/file_processor.py` | 檔案/網址讀取與預處理 |
| `src/utils/json_parser.py` | 文字中擷取 JSON 結構 |
| `src/utils/markdown_utils.py` | Markdown 與程式碼格式化工具 |
| `src/webapp/__init__.py` | Flask 路由與模板配置 |

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
7. **🆕 解題技巧生成**：智慧分析提供學習策略
8. **🚀 並行處理加速**：多題目同時處理，效能提升 3-5 倍

### 🧪 考題處理

- **題目解析**：自動分離題幹與選項
- **🆕 並行答案生成**：多題目同時分析，大幅縮短處理時間
- **知識點標註**：精準概念對應
- **程式碼高亮**：完美支援技術題目
- **🆕 解題技巧整合**：自動生成學習建議與解題策略

### 🔍 知識管理
- **知識圖譜**：概念關聯性視覺化
- **科目分類**：自動分類與統計
- **搜尋功能**：快速定位相關內容
- **進度追蹤**：學習成效分析

## 🗃️ 資料庫結構

### 核心資料表

- **documents**：文件基本資訊與內容
- **questions**：題目詳細資料與答案，支援解題技巧與摘要欄位
- **knowledge_points**：知識點定義與分類
- **question_knowledge_links**：題目與知識點關聯（多對多關係）
- **🆕 async_jobs**：非同步工作狀態管理表，支援並行處理監控

### 增強功能

- **key_points_summary**：AI 生成的學習摘要
- **quick_quiz**：互動選擇題資料
- **mindmap_data**：心智圖 JSON 結構
- **🆕 solving_tips 欄位**：問題解題技巧與策略建議
- **🆕 question_summary 欄位**：問題摘要與學習重點

## 🔧 技術棧

### 後端技術

- **Python 3.8+**：主要開發語言
- **Flask 3.1+**：Web 框架
- **SQLAlchemy 2.0+**：ORM 資料庫抽象層
- **SQLite/MySQL**：支援多種資料庫後端
- **WSGI 伺服器**：
  - **Waitress**：跨平台，適合 Windows 或簡單部署
  - **Gunicorn**：高性能，Linux 生產環境首選
  - **Granian**：🚀 極高性能（Rust 核心），支援 HTTP/2

### 前端技術

- **Bootstrap 5**：響應式 UI 框架
- **Jinja2**：模板引擎
- **Markdown**：內容渲染
- **Mermaid.js**：心智圖與流程圖
- **Code Highlighting**：程式碼語法高亮

### AI 整合

- **Google Gemini Pro**：文字分析與生成
- **Google Cloud Vision**：圖片文字識別
- **自然語言處理**：智慧內容理解

### 檔案處理

- **pdfplumber**：PDF 內容精確解析
- **python-docx**：Word 文件處理
- **pdf2image + Pillow**：PDF 轉圖片與圖像處理
- **Playwright**：進階網頁內容擷取

## 📦 主要相依套件

以下列出專案執行時最重要的套件，完整清單請見 `requirements.txt`。

```requirements
# 核心 AI 功能
google-generativeai>=0.8.0    # Gemini AI 整合
google-cloud-vision>=3.7.0    # 圖片 OCR 識別

# Web 應用程式
Flask>=3.1.0                  # Web 框架
waitress>=2.1.0               # WSGI 伺服器（跨平台）
# gunicorn>=21.0.0             # WSGI 伺服器（Linux 推薦，可選）
# granian>=1.3.0               # WSGI 伺服器（高性能 Rust，可選）

# 資料庫
SQLAlchemy>=2.0.0             # ORM 層
mysql-connector-python>=8.0.0 # MySQL 驅動

# 檔案處理
pdfplumber>=0.7.0             # PDF 解析
python-docx>=1.1.0            # Word 文件
pdf2image>=1.17.0             # PDF 轉圖片
Pillow>=10.4.0                # 圖像處理

# 網頁爬取
playwright>=1.54.0            # 瀏覽器自動化
beautifulsoup4>=4.12.0        # HTML 解析
requests>=2.32.0              # HTTP 請求

# 內容處理
markdown>=3.7.0               # Markdown 渲染
python-dotenv>=1.0.0          # 環境變數管理
```

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

### v2.3 - 架構大升級 (2025/08/02)

- ✅ **資料庫架構完善**：MySQL 生產環境支援，完整的資料表結構設計
- ✅ **AI 輸出完全信任**：移除二次加工邏輯，完全相信 AI 輸出品質，改善排版與內容流暢度
- ✅ **心智圖生成優化**：完善心智圖邏輯，支援複雜知識結構視覺化
- ✅ **解題技巧功能**：新增智慧解題技巧生成，提供學習策略建議
- ✅ **並行處理架構**：**重大架構升級**！採用 asyncio.gather 實現真正的並行處理，大幅提升多題目處理效能
- ✅ **非同步工作資料庫化**：AsyncProcessor 改用資料庫儲存，告別檔案系統，提升穩定性
- ✅ **並行效能實測**：實測證明多題目並行處理顯著縮短處理時間，系統吞吐量大幅提升

### v2.2 - 生產環境優化 (2025/08/02)

- ✅ **WSGI 部署支援**：新增 `wsgi.py` 使用 Waitress 伺服器
- ✅ **高性能伺服器**：新增 Granian 支援，提供極致性能
- ✅ **WSL 最佳化**：完整的 WSL 路徑配置指南
- ✅ **資料庫彈性**：支援 SQLite 與 MySQL 資料庫
- ✅ **環境變數配置**：完整的 `.env` 設定支援
- ✅ **批次刪除修復**：修正變數名稱錯誤問題
- ✅ **心智圖參數優化**：改善知識點格式處理
- ✅ **非同步處理系統**：解決 Cloudflare 524 Timeout 問題
- ✅ **Flask Secret Key 安全強化**：完整的安全配置與警告系統

### v2.1 - OCR 改進 (2025/08/01)

- ✅ **PDF 解析升級**：以 `pdfplumber` 取代 `PyPDF2`，改善版面還原
- ✅ **影像 OCR 強化**：切換 `document_text_detection`，提高圖片與 PDF 解析度

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
