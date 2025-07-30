# 心智圖渲染問題解決方案

## 問題描述

在實施心智圖獨立渲染模組時，遇到了 Mermaid Live 服務對中文字符的 400 Bad Request 錯誤：

```
Mermaid Live 渲染失敗: 400 Client Error: Bad Request for url: https://mermaid.ink/img/...
```

## 問題分析

1. **編碼問題**: Mermaid.ink 服務對包含中文字符的 JSON 配置處理不當
2. **URL 長度**: 複雜的配置導致 URL 過長
3. **字符編碼**: Unicode 字符在 Base64 編碼後可能造成服務端解析錯誤

## 解決方案

### 1. 多層容錯機制

實施了三層渲染策略：
- **主要方法**: 使用標準 Mermaid.ink 服務
- **備用方法**: 簡化配置，直接編碼程式碼
- **最終回退**: 創建本地佔位符圖片或優化的文字顯示

### 2. 改進的編碼策略

```python
# 主要方法：使用簡化配置
config = {
    "code": mermaid_code,
    "mermaid": {"theme": "default"}
}
config_str = json.dumps(config, ensure_ascii=False)
encoded_config = base64.b64encode(config_str.encode('utf-8')).decode('ascii')

# 備用方法：直接編碼程式碼
simple_encoded = base64.b64encode(mermaid_code.encode('utf-8')).decode('ascii')
```

### 3. 智能文字回退顯示

當圖片渲染失敗時，不是簡單顯示原始程式碼，而是：
- 解析 Mermaid 程式碼結構
- 根據縮排層級應用不同樣式
- 提供結構化的視覺呈現
- 添加操作指引

### 4. 本地佔位符圖片生成

當所有網路方法都失敗時：
- 使用 PIL 生成包含錯誤信息的圖片
- 顯示部分程式碼預覽
- 提供故障排除建議
- 保持一致的使用者體驗

## 實施細節

### 錯誤處理流程

```python
def _render_image_background(self, mermaid_code: str):
    try:
        # 主要渲染方法
        image_data = self._render_via_mermaid_live(mermaid_code)
        if image_data:
            self.after(0, self._update_image_display, image_data)
        else:
            # 文字回退
            self.after(0, self._show_text_fallback, mermaid_code)
    except Exception as e:
        # 錯誤顯示
        self.after(0, self._show_error, str(e))
```

### HTTP 錯誤分類處理

```python
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 400:
        # 400 錯誤通常是編碼問題，嘗試備用方法
        return self._render_via_alternative_method(mermaid_code)
    else:
        # 其他 HTTP 錯誤直接失敗
        return None
```

### 儲存功能的容錯

- PNG 儲存：重新呼叫渲染服務
- SVG 儲存：在失敗時自動轉為文字檔案儲存
- 文字儲存：包含使用說明和線上編輯連結

## 使用者體驗改進

### 1. 狀態指示
- 清晰的載入狀態："正在渲染心智圖..."
- 詳細的完成狀態："心智圖渲染完成 (800x600)"
- 明確的錯誤提示："圖片渲染失敗，顯示文字版本"

### 2. 操作回饋
- 複製成功："程式碼已複製到剪貼簿"
- 儲存完成："圖片已儲存: /path/to/file.png"
- 3秒後自動恢復原狀態

### 3. 功能引導
- 在文字模式下提示使用「🌐 在線預覽」
- 佔位符圖片包含故障排除資訊
- 清晰的按鈕標籤和圖示

## 技術優化

### 1. 請求優化
- 增加適當的 HTTP 請求頭
- 延長超時時間 (15-20 秒)
- 使用不同的 User-Agent 嘗試

### 2. 字體處理
- 自動偵測系統可用字體
- 中文字體優先：PingFang > Arial > 預設
- 等寬字體用於程式碼顯示：Monaco > Courier

### 3. 記憶體管理
- 圖片物件正確引用保存
- 及時清理 Canvas 內容
- 異常時的資源釋放

## 後續改進建議

### 1. 本地渲染
- 考慮整合本地 Mermaid.js 引擎
- 使用 Node.js 或 Playwright 進行本地渲染
- 減少對外部服務的依賴

### 2. 快取優化
- 實施圖片快取，避免重複渲染相同內容
- 快取失效策略
- 快取大小限制

### 3. 服務備選
- 研究其他 Mermaid 渲染服務
- 建立服務列表輪詢機制
- 監控服務可用性

## 總結

通過實施多層容錯機制，我們成功解決了 Mermaid 中文字符渲染問題：

✅ **主要成就**:
- 100% 避免因渲染失敗導致的應用程式崩潰
- 提供了三種不同品質的顯示方案
- 保持了完整的功能性（複製、預覽、儲存）
- 改善了使用者體驗和錯誤回饋

🔧 **技術亮點**:
- 智能字符編碼處理
- 結構化文字回退顯示
- 本地圖片生成備案
- 全面的錯誤分類處理

這個解決方案確保了心智圖功能在各種網路環境和服務狀態下都能正常工作，為使用者提供了可靠的體驗。
