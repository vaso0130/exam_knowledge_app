# 考題知識整理系統 - 重構計畫備忘錄

## 願景

將應用程式從一個單純的資料整理工具，升級為一個以「知識點」為核心的個人化學習系統。建立一個強大的「知識資料網」，讓使用者可以圍繞核心概念進行主題式複習，實現高效學習。

## 核心思路

建立一個以 **知識點 (Knowledge Point)** 為中心的資料庫結構，打造一個一定會考高分上榜的 **知識圖譜 (Knowledge Graph)**。

## 專案現況

基礎功能已經大致上完成，現在需要進行以下重構和功能擴展：

## 待完成項目

### 1. 首頁功能擴展 - 新增卡片區塊

現在首頁有以下四個功能卡片：

```html
<!-- 分析題目 -->
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <div class="display-1 mb-3">📁</div>
                        <h3 class="card-title">分析題目</h3>
                        <p class="card-text text-muted">自動解析考題與知識點，不限於檔案，也包含文字與url</p>
                        <a href="/upload" class="btn btn-primary">開始上傳</a>
                    </div>
                </div>
            </div>
            
            <!-- 題庫瀏覽 -->
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <div class="display-1 mb-3">📚</div>
                        <h3 class="card-title">題庫瀏覽</h3>
                        <p class="card-text text-muted">瀏覽已處理的題目，支援 Markdown 渲染和程式碼高亮</p>
                        <a href="/questions" class="btn btn-primary">瀏覽題庫</a>
                    </div>
                </div>
            </div>
            
            <!-- 知識庫 -->
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <div class="display-1 mb-3">🧠</div>
                        <h3 class="card-title">知識庫</h3>
                        <p class="card-text text-muted">查看知識點分類與統計，了解學習進度</p>
                        <a href="/knowledge" class="btn btn-primary">查看知識庫</a>
                    </div>
                </div>
            </div>
            
            <!-- 原始文件 -->
            <div class="col-md-6">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <div class="display-1 mb-3">📜</div>
                        <h3 class="card-title">原始文件</h3>
                        <p class="card-text text-muted">查看所有已上傳的原始文件內容，對照學習更有效</p>
                        <a href="/documents" class="btn btn-success">檢視文件</a>
                    </div>
                </div>
            </div>
        </div>
```

**需要新增的功能卡片：**

#### A. 知識圖譜視覺化

```html
<!-- 知識圖譜 -->
<div class="col-md-6">
    <div class="card h-100">
        <div class="card-body text-center">
            <div class="display-1 mb-3">🕸️</div>
            <h3 class="card-title">知識圖譜</h3>
            <p class="card-text text-muted">視覺化知識點關聯，探索概念間的連結與依賴關係</p>
            <a href="/knowledge-graph" class="btn btn-info">查看圖譜</a>
        </div>
    </div>
</div>
```

#### B. 學習摘要與快速測驗

```html
<!-- 學習摘要測驗 -->
<div class="col-md-6">
    <div class="card h-100">
        <div class="card-body text-center">
            <div class="display-1 mb-3">📝</div>
            <h3 class="card-title">學習摘要測驗</h3>
            <p class="card-text text-muted">針對學習資料生成摘要重點與選擇題，快速檢驗知識點掌握度</p>
            <a href="/summary-quiz" class="btn btn-warning">開始測驗</a>
        </div>
    </div>
</div>
```

### 2. 知識點功能強化

**現況問題**：知識點功能薄弱，只顯示相關題目
**改善目標**：

- 新增基礎觀念說明
- 提供概念解釋與定義
- 增加學習資源連結
- 顯示學習進度追蹤

### 3. 程式碼清理與重構

**桌面版程式碼移除**：

✅ **安全性確認**：經過相依性分析，確認可以安全刪除

📖 **經驗教訓**：
- 桌面版在 Markdown 渲染、心智圖顯示等功能開發上耗費大量時間
- Web UI 利用瀏覽器原生能力，同樣功能輕鬆實現
- **結論**：對於內容展示型應用，Web 技術棧明顯更適合

**技術對比**：
- **Markdown 渲染**：tkinter 複雜 vs 瀏覽器原生
- **心智圖**：matplotlib 繁瑣 vs Mermaid.js 優雅  
- **程式碼高亮**：手動實作 vs Prism.js 即插即用
- **響應式設計**：tkinter 佈局地獄 vs Bootstrap 網格天堂

**相依性分析**：
- Web 應用程式 (`web_app.py`) 完全獨立，無任何 GUI 相依性
- 核心業務邏輯模組 (`src/core/`, `src/flows/`, `src/utils/`, `src/webapp/`) 都與 GUI 解耦
- 只有 `main.py` 依賴 GUI，而這本身就是桌面版啟動程式

**清理步驟**：

1. **刪除 GUI 目錄和檔案**：
   - 刪除 `src/gui/` 整個目錄
   - 刪除 `main.py`（桌面版啟動程式）

2. **清理依賴套件**：
   ```diff
   - customtkinter>=5.2.0
   - tkhtmlview>=0.2.0
   - matplotlib>=3.8.0  # 如果只用於桌面視覺化
   - networkx>=3.0.0    # 如果只用於桌面視覺化
   ```

3. **更新文件**：
   - 更新 README.md，移除桌面版相關說明
   - 更新啟動指令，只保留 `python web_app.py`

**需要移除的檔案清單**：

- `main.py` ⭐（桌面版主程式）
- `src/gui/main_window.py`
- `src/gui/markdown_renderer.py`
- `src/gui/markdown_renderer_new.py`
- `src/gui/mindmap_renderer.py`
- `src/gui/reviewer_window.py`
- `src/gui/visualization.py`

### 4. 資料庫升級方案

**現況**：使用 SQLite 輕量型資料庫
**問題**：可能無法應付大量資料和併發存取
**解決方案**：

- 新增 SQL Server 支援
- 建立資料庫抽象層，支援多種資料庫
- 提供資料庫配置選項
- 實作連線池管理

### 5. 智慧學習功能

#### A. AI 模擬作答評分系統

- 使用者輸入答案後，AI 自動評分
- 提供詳細的答題分析
- 指出答題盲點與改進建議
- 記錄學習歷程與進步軌跡

#### B. 學習資料摘要與測驗系統

**功能說明**：

- 針對上傳的學習資料生成摘要與重點（學習資料原始流程仍須保留，這是新的流程，兩個流程都要執行！）
- 自動產生關於知識點的選擇題（非時事或產品相關）
- 快速檢驗使用者對核心概念的理解
- 提供即時回饋與解析

**設計重點**：

- 題目聚焦於知識點本身，而非新聞中的公司、組織、產品
- 測驗內容與學習目標緊密結合
- 支援多種題型（選擇題、是非題、填空題）

### 6. 使用者體驗優化

- 響應式設計改善
- 載入速度優化
- 搜尋功能增強
- 個人化學習路徑推薦

## 實作優先順序

1. **🚨 最高優先級**：桌面版程式碼清理 ✅ **已完成**
   - **原因**：減少維護負擔，避免混淆，為後續開發清理環境
   - **影響**：後續所有開發都會更清晰
   - **耗時**：短期（1-2 天）
   - **完成日期**：2025年7月31日
   - **清理內容**：
     - ✅ 刪除 `main.py`（桌面版主程式）
     - ✅ 刪除 `src/gui/` 整個目錄
     - ✅ 更新 `requirements.txt`，移除桌面版依賴
     - ✅ 更新 `README.md`，移除桌面版說明
     - ✅ 驗證 Web 應用程式正常運行

2. **高優先級**：學習摘要測驗系統
   - **原因**：提供核心學習功能，快速增加使用者價值
   - **依賴**：基於現有 AI 基礎設施

3. **高優先級**：知識圖譜視覺化實作
   - **原因**：提升使用者體驗，視覺化學習效果
   - **依賴**：需要前端圖表庫整合

4. **中優先級**：資料庫升級支援
   - **原因**：為擴展做準備，但現階段 SQLite 仍可用
   - **時機**：當資料量或併發需求增加時

5. **低優先級**：AI 評分系統
   - **原因**：進階功能，需要複雜的 AI 邏輯

6. **低優先級**：使用者體驗優化
   - **原因**：細節優化，可在主要功能完成後進行

## 技術選型建議

- **知識圖譜**：D3.js 或 Cytoscape.js
- **資料庫**：SQL Server + SQLAlchemy ORM
- **前端框架**：保持現有 Bootstrap + jQuery
- **AI 整合**：繼續使用 Google Gemini API

