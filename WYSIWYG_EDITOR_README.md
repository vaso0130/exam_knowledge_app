# WYSIWYG 筆記編輯器

一個專為考試知識管理系統設計的現代化富文本編輯器，整合了AI智能功能、手寫輸入和LSP支援。

## 🌟 功能特色

### 核心編輯功能
- ✅ **WYSIWYG** - 所見即所得的視覺化編輯
- ✅ **富文本支援** - 完整的格式化選項（粗體、斜體、標題、清單等）
- ✅ **圖片支援** - 直接複製貼上圖片，自動上傳
- ✅ **Markdown雙向轉換** - HTML與Markdown無縫切換
- ✅ **快捷鍵** - 常用格式化快捷鍵支援
- ✅ **響應式設計** - 支援桌面、平板和手機

### AI智能功能
- 🤖 **Ghost AI** - 即時智能寫作建議
- 🤖 **內容補完** - AI驅動的內容自動補完
- 🤖 **智能格式化** - 自動優化文檔結構
- 🤖 **摘要生成** - 快速生成內容摘要
- 🤖 **問答生成** - 從內容自動提取問答對

### 手寫輸入
- ✍️ **手寫板支援** - 支援手寫板和觸控設備
- ✍️ **壓力感應** - 支援壓力感應筆刷
- ✍️ **智能轉換** - 手寫內容可轉換為文字或保存為圖片
- ✍️ **多種工具** - 筆刷、橡皮擦等繪圖工具

### 技術整合
- 🔌 **LSP支援** - 語言伺服器協議整合
- 🔌 **WebSocket** - 即時通訊支援
- 🔌 **模組化設計** - 易於擴展和維護

## 📁 檔案結構

```
src/webapp/static/
├── js/
│   ├── wysiwyg_editor.js       # 主編輯器類別
│   ├── markdown_converter.js   # Markdown轉換工具
│   └── ai_editor.js            # 原有AI編輯器（向下相容）
├── css/
│   ├── wysiwyg_editor.css      # 編輯器樣式
│   └── note_edit.css           # 原有樣式
└── demo.html                   # 功能演示頁面

src/webapp/templates/notes/
├── note_edit_wysiwyg.html      # WYSIWYG編輯頁面
└── note_edit.html              # 原有編輯頁面

src/webapp/
└── notes_blueprint.py          # 路由和API處理
```

## 🚀 快速開始

### 1. 基本使用

```html
<!-- 引入必要的CSS和JS檔案 -->
<link rel="stylesheet" href="/static/css/wysiwyg_editor.css">
<script src="/static/js/markdown_converter.js"></script>
<script src="/static/js/wysiwyg_editor.js"></script>

<!-- 創建編輯器容器 -->
<div id="my-editor"></div>

<script>
// 初始化編輯器
const editor = new WYSIWYGEditor('my-editor', {
    theme: 'light',
    placeholder: '開始寫作...',
    enableHandwriting: true,
    enableLSP: true,
    enableGhost: true
});

// 監聽內容變更
editor.on('contentChange', function(content) {
    console.log('內容已變更:', content);
});
</script>
```

### 2. 設置選項

```javascript
const options = {
    theme: 'light',              // 主題：'light' 或 'dark'
    placeholder: '請輸入內容...',  // 佔位符文字
    autoSave: true,              // 自動儲存
    enableHandwriting: true,     // 啟用手寫功能
    enableLSP: true,            // 啟用LSP支援
    enableGhost: true           // 啟用Ghost AI
};

const editor = new WYSIWYGEditor('container-id', options);
```

### 3. API方法

```javascript
// 取得內容
const htmlContent = editor.getContent('html');
const markdownContent = editor.getContent('markdown');
const textContent = editor.getContent('text');

// 設置內容
editor.setContent('<h1>標題</h1><p>內容</p>', 'html');
editor.setContent('# 標題\n\n內容', 'markdown');

// 執行命令
editor.executeCommand('bold');
editor.executeCommand('insertImage');
editor.executeCommand('toggleGhost');

// 事件監聽
editor.on('ready', function() {
    console.log('編輯器已就緒');
});

editor.on('contentChange', function(content) {
    console.log('內容變更:', content);
});

editor.on('error', function(error) {
    console.error('編輯器錯誤:', error);
});
```

## 🛠️ 系統整合

### 路由設定

在 `notes_blueprint.py` 中已添加以下路由：

```python
# WYSIWYG編輯器頁面
@notes_bp.route('/new-wysiwyg', methods=['GET', 'POST'])
def create_note_wysiwyg():
    # 創建新筆記（WYSIWYG模式）

@notes_bp.route('/edit-wysiwyg/<int:note_id>', methods=['GET', 'POST'])
def edit_note_wysiwyg(note_id):
    # 編輯筆記（WYSIWYG模式）

# API端點
@notes_bp.route('/upload-image', methods=['POST'])
def upload_image():
    # 圖片上傳

@notes_bp.route('/handwriting-to-text', methods=['POST'])
def handwriting_to_text():
    # 手寫轉文字

@notes_bp.route('/ai/ghost-suggestion', methods=['POST'])
def ghost_suggestion():
    # Ghost AI建議

@notes_bp.route('/ai/completion', methods=['POST'])
def ai_completion():
    # AI內容補完
```

### 資料庫整合

編輯器與現有的筆記系統完全相容，使用相同的資料結構：

```python
# 筆記資料結構
{
    'id': int,
    'title': str,
    'content': str,      # Markdown格式
    'tags': str,         # 逗號分隔
    'created_at': datetime,
    'updated_at': datetime
}
```

## 🎨 自訂化

### 主題系統

編輯器支援明亮和黑暗兩種主題：

```javascript
// 切換主題
const editorElement = document.querySelector('.wysiwyg-editor');
editorElement.setAttribute('data-theme', 'dark');
```

### 自訂樣式

可以通過CSS變數自訂編輯器外觀：

```css
.wysiwyg-editor {
    --editor-bg: #ffffff;
    --editor-text: #212529;
    --toolbar-bg: #f8f9fa;
    --border-color: #e0e0e0;
    --accent-color: #007bff;
}

.wysiwyg-editor[data-theme="dark"] {
    --editor-bg: #1e1e1e;
    --editor-text: #ffffff;
    --toolbar-bg: #2d2d2d;
    --border-color: #404040;
    --accent-color: #0d6efd;
}
```

### 自訂工具列

可以通過修改 `createEditorStructure()` 方法來自訂工具列：

```javascript
// 在wysiwyg_editor.js中修改工具列結構
createEditorStructure() {
    // 添加自訂按鈕
    const customButton = `
        <button class="toolbar-btn" data-command="customAction" title="自訂功能">
            <i class="fas fa-star"></i>
        </button>
    `;
    
    // 將按鈕添加到工具列
}
```

## 📱 手寫功能詳解

### 支援的設備
- 🖱️ 滑鼠繪製
- 👆 觸控螢幕
- ✍️ 手寫筆/觸控筆
- 📱 平板電腦

### 繪圖工具
- **筆刷** - 可調整大小和顏色
- **橡皮擦** - 清除不要的筆跡
- **清除** - 清空整個畫布

### 輸出選項
1. **插入為圖片** - 將手寫內容保存為PNG圖片
2. **AI轉換為文字** - 使用OCR技術將手寫轉換為文字

### 使用技巧
- 在平板上使用手寫筆獲得最佳體驗
- 調整筆刷大小以適應不同的字體大小
- 使用橡皮擦工具修正錯誤
- 轉換為文字前確保手寫清晰

## 🤖 AI功能配置

### Ghost AI設定

```javascript
// 在編輯器初始化時配置Ghost模式
const editor = new WYSIWYGEditor('container', {
    enableGhost: true,
    ghostMode: 'supplement'  // 可選：supplement, summary, outline, qa
});

// 動態切換Ghost模式
editor.ghostMode = 'qa';
```

### AI命令列表

| 命令 | 描述 | 用途 |
|------|------|------|
| `summary` | 摘要生成 | 產生內容重點摘要 |
| `outline` | 大綱生成 | 建立文檔結構大綱 |
| `bullets` | 條列整理 | 轉換為條列式要點 |
| `qa` | 問答生成 | 提取問答對 |
| `supplement` | 內容補充 | 延續寫作內容 |
| `rewrite-formal` | 正式化 | 改寫為正式文體 |
| `format-note` | 格式化 | 整體格式優化 |

## 🔧 開發指南

### 擴展編輯器功能

1. **添加新命令**

```javascript
// 在executeCommand方法中添加新case
case 'myCustomCommand':
    this.handleCustomCommand();
    break;
```

2. **添加新的工具列按鈕**

```javascript
// 在createEditorStructure中添加按鈕HTML
<button class="toolbar-btn" data-command="myCustomCommand" title="我的功能">
    <i class="fas fa-custom-icon"></i>
</button>
```

3. **實現自訂處理邏輯**

```javascript
handleCustomCommand() {
    // 實現您的自訂功能
    const selection = window.getSelection();
    // 處理選擇的文字或執行其他操作
}
```

### 調試技巧

```javascript
// 啟用調試模式
window.WYSIWYG_DEBUG = true;

// 監聽所有事件
editor.on('debug', function(data) {
    console.log('Debug info:', data);
});

// 取得編輯器狀態
console.log('Editor state:', {
    isReady: editor.isReady,
    content: editor.getContent(),
    ghostEnabled: editor.ghostEnabled,
    lspEnabled: editor.lspEnabled
});
```

## 📋 待辦事項與發展計畫

### 短期目標
- [ ] 完善圖片上傳功能的後端實現
- [ ] 整合真實的OCR手寫辨識服務
- [ ] 添加更多格式化選項（表格編輯器、顏色選擇等）
- [ ] 優化行動裝置體驗

### 中期目標
- [ ] 協作編輯功能
- [ ] 版本歷史和復原功能
- [ ] 更多AI模型整合
- [ ] 插件系統

### 長期目標
- [ ] 語音輸入功能
- [ ] 更智能的內容建議
- [ ] 多語言支援
- [ ] 離線編輯能力

## 🐛 已知問題

1. **LSP連接** - 在某些環境下LSP WebSocket連接可能不穩定
2. **圖片上傳** - 目前為演示實現，需要配置實際的儲存後端
3. **手寫辨識** - 使用模擬數據，需要整合真實的OCR服務
4. **瀏覽器相容性** - 某些舊版瀏覽器可能不支援所有功能

## 🤝 貢獻指南

歡迎提交問題報告和功能請求！在開發新功能時，請遵循以下原則：

1. 保持代碼簡潔和可讀性
2. 添加適當的註釋和文檔
3. 確保向下相容性
4. 測試所有主要瀏覽器
5. 遵循現有的程式碼風格

## 📄 授權

本專案採用MIT授權條款。

## 🙏 致謝

感謝以下開源項目的貢獻：
- [Monaco Editor](https://microsoft.github.io/monaco-editor/) - 程式碼編輯器靈感
- [Marked.js](https://marked.js.org/) - Markdown解析
- [Bootstrap](https://getbootstrap.com/) - UI框架
- [Font Awesome](https://fontawesome.com/) - 圖標庫

---

**享受全新的筆記編輯體驗！** 🎉
