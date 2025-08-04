
# 🚀 AI 智慧考題知識整理系統 v3.1 開發計畫

## 🎯 v3.1 主要目標：AI 驅動的個人筆記系統

### 📝 優先任務：個人筆記功能架構

**背景**：v3.0 已完成完整的安全與權限管理系統，現在要實現個人化學習筆記功能，打造真正的個人學習助手。

### 核心設計理念
1. **模組化架構**：個人筆記系統與主程式適度解耦，便於獨立維護
2. **AI 驅動**：利用 Gemini AI 提供智慧筆記整理、關聯分析、知識提取
3. **用戶隔離**：每個用戶的筆記完全隔離，確保資料安全
4. **知識整合**：可調用主程式的知識點、題庫資源，形成學習閉環

---

## 📋 v3.1 開發任務清單

### 🏗️ Phase 1: 個人筆記系統架構設計

#### 1.1 模組化架構設計
```text
exam_knowledge_app/
├── 🧠 主程式（現有系統）
│   ├── web_app.py                    # 主應用入口
│   └── src/                          # 現有核心模組
│       ├── core/                     # 核心模組（共用）
│       ├── flows/                    # 處理流程（現有）
│       ├── utils/                    # 工具函式（現有）
│       ├── webapp/                   # Web 介面
│       │   ├── templates/            # � 主程式模板（共用入口）
│       │   │   ├── notes/            # �📝 筆記系統模板（新增）
│       │   │   │   ├── note_list.html
│       │   │   │   ├── note_edit.html
│       │   │   │   ├── note_detail.html
│       │   │   │   └── category_management.html
│       │   │   └── ...existing templates...
│       │   └── notes_blueprint.py   # 📝 筆記系統路由（新增）
│       └── notes/                    # 📝 個人筆記系統模組（新增）
│           ├── __init__.py
│           ├── database.py           # 筆記專用資料庫操作
│           ├── ai_client.py          # 筆記專用 AI 客戶端
│           ├── note_manager.py       # 筆記核心管理邏輯
│           ├── knowledge_integrator.py # 與主程式知識整合
│           └── utils/                # 筆記專用工具函式
│               ├── text_analyzer.py  # 文字分析與標籤提取
│               ├── link_detector.py  # 智慧關聯檢測
│               └── export_manager.py # 筆記匯出功能
```

#### 1.2 資料庫設計（筆記專用表）
```sql
-- 個人筆記主表
CREATE TABLE user_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    content_type ENUM('markdown', 'rich_text', 'code', 'mixed') DEFAULT 'markdown',
    tags TEXT,                        -- JSON 陣列格式的標籤
    ai_summary TEXT,                  -- AI 生成的筆記摘要
    ai_keywords JSON,                 -- AI 提取的關鍵字
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_archived BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 筆記分類表
CREATE TABLE note_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    color VARCHAR(7),                 -- HEX 顏色碼
    icon VARCHAR(50),                 -- 圖示名稱
    parent_id INTEGER,                -- 支援階層分類
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (parent_id) REFERENCES note_categories(id)
);

-- 筆記與分類關聯表
CREATE TABLE note_category_links (
    note_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (note_id, category_id),
    FOREIGN KEY (note_id) REFERENCES user_notes(id),
    FOREIGN KEY (category_id) REFERENCES note_categories(id)
);

-- 筆記與主程式知識點關聯表
CREATE TABLE note_knowledge_links (
    note_id INTEGER NOT NULL,
    knowledge_point_id INTEGER NOT NULL,
    relevance_score FLOAT DEFAULT 0.8,  -- AI 計算的關聯度
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (note_id, knowledge_point_id),
    FOREIGN KEY (note_id) REFERENCES user_notes(id),
    FOREIGN KEY (knowledge_point_id) REFERENCES knowledge_points(id)
);

-- 筆記間關聯表（雙向關聯）
CREATE TABLE note_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_note_id INTEGER NOT NULL,
    target_note_id INTEGER NOT NULL,
    relationship_type ENUM('reference', 'follow_up', 'related', 'contrast') DEFAULT 'related',
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_note_id) REFERENCES user_notes(id),
    FOREIGN KEY (target_note_id) REFERENCES user_notes(id)
);

-- AI 筆記分析記錄
CREATE TABLE note_ai_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    analysis_type ENUM('summary', 'keywords', 'knowledge_links', 'suggestions') NOT NULL,
    result JSON NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES user_notes(id)
);
```

#### 1.3 權限與隔離設計
- **完全用戶隔離**：每個用戶只能存取自己的筆記
- **繼承主程式權限**：基於現有的 admin/viewer 角色系統
- **限定只有管理員可以使用，檢視者無法使用此功能**

### 🤖 Phase 2: AI 驅動功能設計

#### 2.1 智慧筆記分析
```python
class NoteAIClient:
    def analyze_note_content(self, content: str) -> dict:
        """分析筆記內容，提取關鍵資訊"""
        return {
            'summary': str,           # 筆記摘要
            'keywords': list,         # 關鍵字列表
            'main_topics': list,      # 主要主題
            'difficulty_level': str,  # 難易度評估
            'suggested_tags': list,   # 建議標籤
            'knowledge_points': list  # 相關知識點
        }
    
    def suggest_related_content(self, note_id: int) -> dict:
        """建議相關內容"""
        return {
            'related_notes': list,        # 相關筆記
            'knowledge_points': list,     # 相關知識點
            'questions': list,            # 相關題目
            'study_suggestions': list     # 學習建議
        }
    
    def generate_study_plan(self, note_ids: list) -> dict:
        """基於筆記生成學習計畫"""
        return {
            'daily_goals': list,      # 每日學習目標
            'review_schedule': dict,  # 複習排程
            'weak_areas': list,       # 薄弱環節
            'improvement_tips': list  # 改進建議
        }
```

#### 2.2 智慧關聯檢測
- **內容相似性分析**：使用 AI 比對筆記內容的相關性
- **知識點自動關聯**：將筆記內容與主程式的知識點自動關聯
- **題目推薦**：根據筆記內容推薦相關練習題
- **學習路徑建議**：AI 分析學習進度，建議最佳學習順序

#### 2.3 AI 輔助功能
- **自動摘要生成**：為長篇筆記生成精準摘要
- **關鍵字提取**：自動提取重要概念和術語
- **筆記品質評估**：分析筆記的完整性和邏輯性
- **學習盲點檢測**：識別知識盲點，提供補強建議

### 📱 Phase 3: 使用者介面設計

#### 3.1 筆記編輯器
- **多格式支援**：Markdown、富文本、程式碼、混合模式
- **即時預覽**：所見即所得的編輯體驗
- **AI 輔助功能**：
  - **內容摘要**：選取文字後可請 AI 生成摘要
  - **關鍵字提取**：AI 分析筆記內容並建議重要標籤
  - **內容擴充**：選取段落後請 AI 補充相關概念或例子
  - **格式整理**：AI 幫助調整文章結構和段落組織
- **版本控制**：筆記修改歷史追蹤

#### 3.2 知識整合介面
- **知識點瀏覽**：在筆記中直接瀏覽相關知識點
- **題目練習**：從筆記直接跳轉到相關練習題
- **學習進度**：視覺化顯示學習進度和成果
- **復習提醒**：基於記憶曲線的智慧提醒

#### 3.3 組織與搜尋
- **階層分類**：支援多層次的筆記分類
- **標籤系統**：靈活的標籤管理和篩選
- **全文搜尋**：強大的搜尋功能，支援模糊搜尋
- **AI 搜尋**：語意搜尋，理解用戶意圖

### 🔗 Phase 4: 主程式整合

#### 4.1 路由整合
```python
# 在 src/webapp/__init__.py 中整合筆記系統
from .notes_blueprint import notes_bp

def create_app():
    # 現有主程式初始化
    app = Flask(__name__)
    # ... 現有設定 ...
    
    # 註冊現有藍圖
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # 整合筆記系統藍圖
    app.register_blueprint(notes_bp, url_prefix='/notes')
    
    return app
```

#### 4.2 模板共用架構
```python
# src/webapp/notes_blueprint.py 使用共用模板系統
from flask import Blueprint, render_template
from ..notes.note_manager import NoteManager

notes_bp = Blueprint('notes', __name__)

@notes_bp.route('/list')
def note_list():
    # 筆記列表邏輯
    return render_template('notes/note_list.html', **data)

@notes_bp.route('/edit/<int:note_id>')
def note_edit(note_id):
    # 筆記編輯邏輯
    return render_template('notes/note_edit.html', **data)
```

#### 4.3 導航整合
```html
<!-- 在 src/webapp/templates/layout.html 中加入筆記系統導航 -->
<nav class="navbar navbar-expand-lg">
    <div class="navbar-nav">
        <a class="nav-link" href="{{ url_for('main.index') }}">首頁</a>
        <a class="nav-link" href="{{ url_for('main.knowledge') }}">知識管理</a>
        <a class="nav-link" href="{{ url_for('notes.note_list') }}">📝 我的筆記</a>
        <a class="nav-link" href="{{ url_for('main.documents_list') }}">文件庫</a>
    </div>
</nav>
```

#### 4.4 資料整合
```python
class KnowledgeIntegrator:
    def get_related_knowledge_points(self, note_content: str) -> list:
        """獲取與筆記相關的知識點"""
        pass
    
    def get_related_questions(self, note_id: int) -> list:
        """獲取與筆記相關的題目"""
        pass
    
    def sync_learning_progress(self, user_id: int) -> dict:
        """同步學習進度到主程式"""
        pass
```

#### 4.3 權限整合
- **會話共享**：與主程式共享用戶登入狀態
- **權限繼承**：基於主程式的權限系統
- **限定只有管理員可以使用，檢視者無法使用此功能**

---

## 🚀 v3.1 實作順序

### Week 1: 筆記系統架構建立
1. 🔨 設計並建立筆記相關資料表
2. 🔨 實作 `notes/database.py` 筆記專用資料庫操作，與主程式共同一個資料庫
3. 🔨 建立 `notes/ai_client.py` 筆記專用 AI 客戶端
4. 🔨 實作基礎的筆記 CRUD 功能

### Week 2: AI 功能開發
1. 🔨 實作筆記內容分析功能
2. 🔨 開發智慧關聯檢測系統
3. 🔨 建立知識點自動關聯機制
4. 🔨 實作 AI 輔助寫作功能

### Week 3: 使用者介面開發
1. 🔨 在 `src/webapp/templates/notes/` 中建立筆記模板（共用主程式模板系統）
2. 🔨 創建 `src/webapp/notes_blueprint.py` 筆記系統路由
3. 🔨 實作分類和標籤管理介面
4. 🔨 建立搜尋、篩選和知識整合顯示功能

### Week 4: 主程式整合與測試
1. 🔨 在 `src/webapp/__init__.py` 中註冊筆記藍圖
2. 🔨 更新主程式首頁個人筆記連結到正確的功能頁面，並且刪除現有的預告頁面`personal_notes.html`。
2. 🔨 更新主程式導航選單，加入筆記系統入口
3. 🔨 限定只有管理員可以使用，檢視者無法使用此功能，也看不到相關區域卡片或是連結按鈕。
4. 🔨 完整系統測試與優化

---

## 📚 v3.1 技術需求

### 新增依賴套件
```requirements
# 筆記編輯相關
markdown>=3.7.0              # Markdown 解析
bleach>=6.0.0                # HTML 清理（安全性）
python-slugify>=8.0.0        # 生成 URL 友善的 slug

# 文字分析
jieba>=0.42.1                # 中文分詞
scikit-learn>=1.3.0          # 文字相似性計算
textdistance>=4.6.0          # 文字距離計算

# 匯出功能
reportlab>=4.0.0             # PDF 生成
openpyxl>=3.1.0              # Excel 匯出
```

### 個人筆記功能特色

#### 🎯 核心亮點
1. **AI 驅動的智慧筆記**：
   - 自動摘要和關鍵字提取
   - 智慧建議相關內容
   - 學習盲點檢測

2. **與主程式深度整合**：
   - 筆記內容自動關聯知識點
   - 推薦相關練習題目
   - 學習進度同步追蹤

3. **強大的組織能力**：
   - 階層分類系統
   - 靈活標籤管理
   - AI 驅動的關聯檢測

4. **個人化學習助手**：
   - 基於筆記內容的學習計畫
   - 記憶曲線復習提醒
   - 個人化學習建議

#### 🔒 安全與隔離
- **完全用戶隔離**：每個用戶的筆記完全獨立
- **繼承權限系統**：基於 v3.0 的安全框架

#### 🎨 使用體驗
- **直觀的編輯介面**：支援多種格式的筆記編輯
- **即時 AI 輔助**：寫作過程中的智慧建議
- **豐富的檢視模式**：時間線、分類、關聯圖等多種檢視
- **無縫整合體驗**：與主程式功能自然銜接

---

## 🔮 v3.2+ 未來規劃

### 高級 AI 功能
- **語音筆記**：語音轉文字，AI 自動整理
- **圖片筆記**：OCR 識別，圖文混合筆記
- **協作筆記**：團隊共享筆記（保持個人隱私）

### 學習分析
- **學習行為分析**：深度分析學習模式
- **個人化推薦**：AI 推薦學習內容和方法

---

## ⚠️ v3.1 開發注意事項

1. **模組化原則**：
   - 筆記系統保持相對獨立，便於維護和擴展
   - 通過明確的介面與主程式整合
   - 避免過度耦合，確保系統穩定性

2. **效能考量**：
   - AI 分析功能設計為非同步處理
   - 大量文字分析使用快取機制
   - 資料庫查詢優化，建立適當索引

3. **用戶體驗**：
   - 筆記編輯介面響應迅速
   - AI 功能提供即時回饋
   - 支援離線編輯（本地暫存）

4. **資料安全**：
   - 筆記內容加密存儲（敏感資訊）
   - 定期自動備份用戶資料
   - 完整的操作記錄追蹤

---

**注意**：v2.0 的知識圖譜功能將延後到 v4.0，v3.1 專注於個人筆記系統建設。
