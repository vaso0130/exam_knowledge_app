# 學習資料AI內容清理增強建議

## 問題現況
目前系統雖然有基本的HTML清理和AI摘要生成，但缺少專門針對學習資料的深度AI整理功能。

## 建議改進方案

### 1. 在 GeminiClient 中新增內容清理方法

```python
async def clean_and_format_content(self, raw_content: str, subject: str = None) -> Dict[str, Any]:
    """
    使用AI深度清理和格式化學習內容
    專門移除廣告、導航、頁面註腳等雜訊，並重新組織為適合學習的格式
    """
    
    prompt = f"""
你是一位專業的教育內容編輯師，負責將網路上採集來的原始學習資料，清理整理成高品質的教育內容。

**你的任務：**
1. **移除雜訊內容**：廣告文字、導航選單、頁面註腳、社群媒體連結、相關推薦等
2. **保留核心知識**：技術概念、理論說明、實作步驟、程式碼範例、圖表說明等
3. **重新組織結構**：將內容重新排列為邏輯清晰的學習順序
4. **格式化美化**：使用 Markdown 語法，加入適當的標題、列表、程式碼區塊
5. **補充說明**：對於過於簡略或專業的內容，適當補充背景知識

**處理原則：**
- 保持原始技術資訊的準確性
- 移除商業宣傳和不相關內容
- 統一術語和概念表達
- 確保內容的教育價值
- 使用繁體中文撰寫說明文字

**原始內容：**
```
{raw_content}
```

**科目領域：** {subject or '通用'}

請以JSON格式回應：
{{
    "cleaned_content": "清理並格式化後的 Markdown 內容",
    "removed_elements": ["移除的雜訊類型1", "移除的雜訊類型2"],
    "improvements": ["改進說明1", "改進說明2"],
    "confidence": 0.85
}}
"""
    
    try:
        response = await asyncio.to_thread(
            self.intermediate_model.generate_content,
            prompt,
            generation_config=self.generation_config
        )
        
        if response and response.text:
            result = extract_json_from_text(response.text)
            if result and 'cleaned_content' in result:
                return result
                
        return {
            "cleaned_content": raw_content,
            "removed_elements": [],
            "improvements": [],
            "confidence": 0.0
        }
        
    except Exception as e:
        print(f"內容清理失敗: {e}")
        return {
            "cleaned_content": raw_content,
            "removed_elements": [],
            "improvements": ["清理過程發生錯誤"],
            "confidence": 0.0
        }
```

### 2. 在 ContentFlow 中整合內容清理

```python
async def _process_study_material(self, content: str, subject: str, doc_id: int, parsed_data: Dict) -> Dict[str, Any]:
    """學習資料處理流程 - 增加AI內容清理步驟"""
    print("📚 執行學習資料處理流程...")
    
    # 🆕 新增：AI 深度內容清理
    print("🧹 AI 正在清理和整理內容...")
    cleaning_result = await self.gemini.clean_and_format_content(content, subject)
    
    cleaned_content = cleaning_result.get('cleaned_content', content)
    confidence = cleaning_result.get('confidence', 0.0)
    
    if confidence > 0.7:
        print(f"✅ 內容清理完成，信心度: {confidence:.2f}")
        print(f"📝 移除元素: {', '.join(cleaning_result.get('removed_elements', []))}")
        
        # 更新資料庫中的內容為清理後的版本
        self.db.update_document_content(doc_id, cleaned_content, content)  # 保存原始內容作為備份
        
        # 使用清理後的內容進行後續處理
        content_for_processing = cleaned_content
    else:
        print(f"⚠️ 內容清理信心度較低 ({confidence:.2f})，使用原始內容")
        content_for_processing = content
    
    # 後續處理使用清理後的內容...
    generated_questions = await self.gemini.generate_questions_from_text(content_for_processing, subject)
    # ... 其他處理步驟 ...
```

### 3. 資料庫支援原始內容備份

```python
def update_document_content(self, doc_id: int, cleaned_content: str, original_content: str = None):
    """更新文件內容，可選擇保存原始內容備份"""
    with self._session_scope() as session:
        document = session.query(Document).filter_by(id=doc_id).first()
        if document:
            if original_content and not document.original_content:
                document.original_content = original_content  # 備份原始內容
            document.content = cleaned_content  # 使用清理後的內容
```

### 4. 前端顯示改進

在學習摘要頁面中：
- 主要顯示AI清理後的內容
- 提供「查看原始內容」選項讓使用者比較
- 顯示清理過程的改進說明

## 預期效果

1. **內容品質提升**：移除廣告和無關資訊，專注於教育內容
2. **閱讀體驗改善**：清晰的 Markdown 格式，邏輯分明的結構
3. **學習效率提高**：去除干擾，突出重點知識
4. **一致性增強**：統一的術語表達和格式風格

## 實施步驟

1. 在 `GeminiClient` 中實作 `clean_and_format_content` 方法
2. 修改 `ContentFlow._process_study_material` 整合清理步驟
3. 更新資料庫方法支援內容備份
4. 調整前端模板顯示清理結果
5. 測試和調優清理效果

這樣的改進將使系統真正具備「AI智慧內容清理」的能力，為使用者提供高品質的學習資料。
