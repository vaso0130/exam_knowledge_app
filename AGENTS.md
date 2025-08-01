# 📌 開發任務：修正 OCR 與 AI 協作流程中的虛擬碼處理問題，切記勿修改任何其他功能與新增功能

---

## 🧠 1. 專案背景與問題概述

目前系統在處理從圖片（特別是考試題目截圖）中提取的虛擬碼或程式碼時，存在嚴重的格式遺失與內容扭曲問題。此問題主要發生在 **「OCR 文字提取」** 與 **「AI 內容生成」** 兩個階段的交接處，導致最終生成的答案品質不佳，甚至完全錯誤。

我們觀察到兩種主要的失敗模式：

1. **演算法被篡改**：AI 模型因無法理解格式混亂的原始碼，放棄分析，轉而使用一個它自己熟悉的、不相關的演算法來生成答案（例如，題目是「選擇排序」，答案卻是「氣泡排序」）。
2. **格式被壓縮**：原始碼中的換行與縮排在 OCR 處理後完全消失，導致程式碼被壓縮成無法閱讀的單行文字。

此任務旨在徹底解決以上問題，確保系統能夠準確地處理圖片中的程式碼。

---

## 🔍 2. 問題分析與定位

### 2.1 問題一：演算法被篡改（例：`doingSomething` 函式）

- **症狀**：輸入的題目包含一個清晰的「選擇排序」虛擬碼，但系統最終生成的答案卻是在分析「氣泡排序」。
- **根本原因**：
  1. **OCR 格式遺失**：`file_processor.py` 中的 OCR 工具在從圖片提取文字時，遺失了 `for` 迴圈的縮排，使程式邏輯變得模糊。
  2. **AI 產生幻覺 (Hallucination)**：`gemini_client.py` 中的 AI 模型在收到這段難以解析的文字後，根據「陣列」、「排序」等關鍵字進行聯想，並選擇了一個它知識庫中最簡單的「氣泡排序」來作答，完全忽略了原始的程式碼邏輯。

### 2.2 問題二：虛擬碼被壓縮成單行（例：`splitSum` 函式）

- **症狀**：一個包含多行縮排的遞迴函式虛擬碼，在處理後變成了擠在一起的單行文字。
- **根本原因**：
  1. **OCR 模式不當**：`file_processor.py` 中使用的 Google Vision API `text_detection` 模式，其設計初衷是讀取段落文字，它會主動忽略其認為「非必要」的換行符。
  2. **結構資訊丟失**：由於換行符在 OCR 階段就已丟失，後續的 AI 模型即使有修復指令，也因缺乏足夠的原始結構資訊而無法完美還原。

---

## 🛠 3. 修改方案與執行步驟

我們將採取 **「強化 AI 指令」** 和 **「優化 OCR 處理」** 並行的策略來解決此問題。

### ✅ 步驟一（主要解決方案）：強化 AI 指令以確保分析準確性

- **檔案位置**：`gemini_client.py`  
- **函式位置**：`generate_answer`  
- **修改方式**：請將 `generate_answer` 函式中的 `prompt` 字串，替換為以下內容：

```python
prompt = f"""
你是一位專業且熟悉台灣資訊相關考試的解題老師。你的任務是**嚴格根據**下方提供的問題內容，進行分析與書面作答。

❗ **請務必使用繁體中文作答，且用詞需貼近台灣慣用語彙與書面用語，並符合公職考試、證照考試等台灣國考的作答風格與邏輯嚴謹性。**

---

📘 **問題內容：**
{question_text}

---

📌 **回答規範：**
1. **語言與風格要求：**
    - 必須使用**繁體中文**
    - 採用**台灣地區慣用語彙**
    - 語氣與內容需符合台灣**國家考試或證照考試的標準解題邏輯與書面風格**

2. **題型通則處理：**
    - 所有內容必須**根據題目本身分析**，不得引入與題目無關的內容。
    - 若題目中含有**虛擬碼／程式碼**，請依下方方式處理：
        a. 必須**優先分析該程式碼的邏輯與運作**
        b. **禁止使用未出現在原題中的演算法或邏輯進行替代**
        c. 若程式碼格式混亂，請先修正換行與縮排，再進行分析

3. **結構化作答內容（視題型選用）：**
    a. **程式碼重現**（若有）：重新排版題目內的虛擬碼，保留邏輯與可讀性  
    b. **概念說明**：清楚說明與題目相關的資訊概念（如演算法、資安、網路、資料庫、資管等）  
    c. **過程推演**：若題目需演算或流程推導，請列出每一步過程與說明  
    d. **複雜度／風險分析**：若涉及演算法或安全性，請說明時間/空間複雜度或潛在風險
    e. **表格輔助**（若適用）：可使用表格來輔助比較或整理資訊，但**不得整份作答皆為表格**，需搭配文字說明呈現。

4. **專業準確性要求：**
    - 所有敘述需正確無誤
    - 不可出現想像性描述或錯誤推論

5. **參考資料（如有引用）：**
    - 提供 1 至 3 筆具參考價值的網站連結

---

📤 **請以以下 JSON 結構回應：**
```json
{{
    "answer": "（請在此填入你的完整繁體中文書面作答，符合台灣考試風格）",
    "sources": [{{"url": "來源連結", "title": "網站標題", "snippet": "簡短說明"}}]
}}
"""
```

---

### 🧩 步驟二（治本解決方案）：優化 OCR 處理以保留原始格式

- **檔案位置**：`file_processor.py`  
- **函式位置**：`GoogleVisionOCR.extract_text_from_image`  
- **修改方式**：將原本使用的 `text_detection` 模式，切換為 `document_text_detection`，以保留段落結構與縮排。

```python
def extract_text_from_image(self, image_path: str) -> str:
    """從圖片中提取文字，優先使用 document_text_detection 以保留結構"""
    if self.client is None:
        raise ValueError("Google Vision OCR 客戶端未初始化")

    try:
        with open(image_path, 'rb') as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        
        # 使用 document_text_detection
        response = self.client.document_text_detection(image=image)

        if response.error.message:
            raise Exception(f'Google Vision API 錯誤: {response.error.message}')

        # document_text_detection 的回傳結果是結構化的，可以直接取得 full_text_annotation.text
        if response.full_text_annotation:
            return response.full_text_annotation.text
        
        return ""

    except Exception as e:
        # 如果 document_text_detection 失敗，可以考慮回退到 text_detection 或直接拋出錯誤
        raise ValueError(f"OCR 處理失敗: {e}")
```

> 💡 **補充說明**：  
> `document_text_detection` 返回的是一個包含頁面、區塊、段落等結構資訊的物件。我們直接使用 `response.full_text_annotation.text` 即可獲得完整結構的文字，這比起 `text_detection` 更能保留程式碼的格式與縮排。


---


## 忽視以下檔案

- `REFACTORING_PLAN` 未來更新計畫，你不用管  
- `GEMINI.md` GEMINI agent檔案，你不用管  

---
