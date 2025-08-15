# WYSIWYG 編輯器列表換行修復報告

## 問題描述

在 WYSIWYG 編輯器中，HTML 轉換為 Markdown 時會出現換行消失的問題，特別是在處理嵌套列表項目時。這導致：

1. 列表項目之間的換行符被移除
2. 嵌套列表的縮進格式錯誤
3. 存檔後的 Markdown 格式與預期不符

### 原始問題示例

**HTML 輸入:**
```html
<ol>
<li><strong>裝置識別與註冊</strong>：
<ul>
<li>所有嘗試連接企業資源的裝置都必須被唯一識別、註冊並納入管理。</li>
</ul>
</li>
<li><strong>裝置健康狀態評估</strong>：
<ul>
<li>持續監控裝置的安全性狀態，包括：
<ul>
<li>作業系統和應用程式是否已安裝最新安全補丁。</li>
<li>防毒軟體或EDR代理程式是否正常運行且定義檔最新。</li>
</ul>
</li>
</ul>
</li>
</ol>
```

**問題輸出 (修復前):**
```markdown
1. **裝置識別與註冊**：- 所有嘗試連接企業資源的裝置都必須被唯一識別、註冊並納入管理。2. **裝置健康狀態評估**：- 持續監控裝置的安全性狀態，包括：- 作業系統和應用程式是否已安裝最新安全補丁。- 防毒軟體或EDR代理程式是否正常運行且定義檔最新。
```

## 解決方案

### 修復策略

1. **重寫列表處理邏輯**: 從基於正則表達式的處理改為基於 DOM 節點的遞歸處理
2. **保留換行符**: 確保列表項目之間和嵌套內容中的換行符被正確保留
3. **正確縮進**: 為嵌套列表項目添加適當的縮進空格
4. **改進格式化**: 增強最終格式化階段，避免破壞列表結構

### 具體修改

#### 1. wysiwyg_editor.js 修改

**文件**: `src/webapp/static/js/wysiwyg_editor.js`

**主要變更**:
- 第 1275-1295 行：重寫列表處理邏輯
- 新增方法：
  - `processOrderedList(olNode, indent = '')`
  - `processUnorderedList(ulNode, indent = '')`
  - `processListItem(liNode, marker, indent = '')`
  - `processNodeContent(node)`

**核心改進**:
```javascript
// 舊的正則表達式方法（有問題）
markdown = markdown.replace(/<ol[^>]*>(.*?)<\/ol>/gis, (match, content) => {
    // ... 複雜的嵌套正則表達式處理
});

// 新的 DOM 解析方法（修復後）
const listTempDiv = document.createElement('div');
listTempDiv.innerHTML = markdown;

const orderedLists = listTempDiv.querySelectorAll('ol');
orderedLists.forEach(ol => {
    const listMarkdown = this.processOrderedList(ol);
    ol.outerHTML = listMarkdown;
});
```

#### 2. markdown_converter.js 修改

**文件**: `src/webapp/static/js/markdown_converter.js`

**主要變更**:
- 第 213-258 行：改進 `processListItems` 方法
- 新增 `processListItemContent` 方法
- 第 394-426 行：改進 `formatMarkdown` 方法

**關鍵改進**:
- 更好的嵌套列表處理
- 保留適當的縮進和換行
- 避免在格式化階段破壞列表結構

### 修復後的輸出示例

**期望輸出 (修復後):**
```markdown
#### (二) 裝置安全與健康狀態監控（Device Security and Health Monitoring）

在零信任環境中，任何嘗試連接資源的裝置都必須被視為潛在威脅，並經過嚴格的健康檢查。

1. **裝置識別與註冊**：
  - 所有嘗試連接企業資源的裝置（筆電、手機、平板、IoT設備等）都必須被唯一識別、註冊並納入管理。這通常透過行動裝置管理（MDM）、統一端點管理（UEM）或端點偵測與回應（EDR）工具實現。

2. **裝置健康狀態評估**：
  - 持續監控裝置的安全性狀態，包括：
    - 作業系統和應用程式是否已安裝最新安全補丁。
    - 防毒軟體或EDR代理程式是否正常運行且定義檔最新。
    - 是否存在惡意軟體、配置錯誤或異常行為。
    - 是否符合企業的安全策略（如：是否越獄/Root）。
  - 不符合安全標準的裝置將被自動隔離、限制存取權限，或引導至修復流程，直至其安全狀態恢復正常。
```

## 測試檔案

為了驗證修復效果，創建了以下測試檔案：

1. **test_fixed_conversion.html** - 完整的互動測試頁面
2. **test_list_conversion.js** - 獨立的 Node.js 測試腳本
3. **better_conversion_test.js** - 改進的轉換邏輯測試

## 驗證標準

修復後的轉換應該滿足：

1. ✅ 保留主列表項目的編號 (1., 2., ...)
2. ✅ 正確縮進嵌套的無序列表項目 (  -)
3. ✅ 正確縮進深層嵌套項目 (    -)
4. ✅ 保留標題和段落格式
5. ✅ 保留粗體和斜體格式
6. ✅ 維持適當的行間距
7. ✅ 避免不必要的換行符丟失

## 兼容性

修復保持了與現有 API 的完全兼容性：
- `htmlToMarkdown()` 方法簽名未改變
- `markdownToHtml()` 方法未受影響
- 所有現有的格式化功能都得到保留

## 使用方式

修復後的功能自動生效，無需更改現有代碼：

```javascript
const editor = new WYSIWYGEditor(container);
const markdown = editor.htmlToMarkdown(htmlContent);
// 現在會正確保留列表格式和換行符
```

## 後續建議

1. **性能監控**: 新的 DOM 解析方法可能比正則表達式稍慢，建議監控大型文檔的轉換性能
2. **邊界情況測試**: 繼續測試更複雜的嵌套結構和特殊格式
3. **用戶反馈**: 收集用戶對新格式輸出的反饋，進行微調

## 結論

這次修復成功解決了 WYSIWYG 編輯器中列表換行消失的問題，通過改用基於 DOM 的處理方式，確保了列表結構的正確保留和格式化。修復保持了向後兼容性，同時顯著改善了用戶體驗。
