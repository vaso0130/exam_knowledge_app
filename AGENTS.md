# 🛠️ 任務：排查題庫抽取流程錯誤

> 你是 **「題庫抽取診斷 Agent」**  
> **工作目標**  
> 1. 比對 **原始題目** 與 **節錄結果**，找出「答案混入」「內容缺失」或「格式錯誤」的原因。  
> 2. 針對每個 Issue，指出問題可能出現在 **程式流程** 或 **AI API Prompt** 哪一段，並提出修改建議。  
> 3. 最終回報：  
>    - 🔎 **Root-Cause**（程式邏輯 / Regex / Prompt / Chunk Strategy …）  
>    - 📝 **Fix Plan**（具體步驟或範例程式碼）  
>    - ✅ **Validation**（單元測試或範例輸入輸出）

---

## Issue 1 — 題目節錄包含解析與答案

### 原始題目
```text
一、一棵空的階數為3的B-Tree（B-Tree of order 3）。由左而右依序插入下列鍵值（key value）：10, 80, 2, 9, 45, 62。請問插入完畢後，根節點中的鍵值有哪些？請依序由小到大列出，用逗號分隔，並請說明樹節點的變化。（10分）
有一棵階數為5的B-Tree（B-Tree of order 5），其高度（height）為3，請問這棵樹中最多可以儲存多少個鍵值？(10分)
```

### 節錄結果（含錯誤）
```text
🎯 題目內容
一、B-Tree 插入與儲存量計算
(1) B-Tree 插入 (10分)
一棵空的階數為3的B-Tree…（以下省略）

樹節點變化說明： ← ⚠️ 解析開始

插入 10: 根節點: [10]
…（完整解析與答案）
最終根節點中的鍵值：10, 62

(2) B-Tree 最大儲存量計算 (10分)
…（解析＋答案 624 也被帶入）
```

#### 預期行為  
僅保留兩小題題幹，不應含解析或答案。  

#### 實際行為  
節錄內容混入完整解析與答案。  

---

## Issue 2 — 節錄結果內容缺失

### 原始題目（來自 `test.pdf` 第四題）
```text
根據下列虛擬碼，若 n = 21 則傳回的答案為何？請說明。（20分）
function splitSum(n: integer) returns integer
    if n <= 1 then
        return 1
    a ← floor(n / 2)
    b ← floor(n / 3)
    return splitSum(a) + splitSum(b)
```

### 節錄結果
```text
function splitSum(n: integer) returns integer
    if n <= 1 then
        return 1
    a ← floor(n / 2)
    b ← floor(n / 3)
    return splitSum(a) + splitSum(b)
```

#### 問題  
題幹文字「若 n = 21 則傳回的答案為何？請說明。（20分）」被截斷遺失。  

---

## Issue 3 — 參考答案與心智圖輸出錯誤

### 節錄＋解析（錯誤示例）
```text
🎯 題目內容
演算法分析
以下虛擬碼是…（整段題幹）
✅ 參考答案
無法解析答案           ← ⚠️ 答案跑到題幹裡面
心智圖:
Syntax error in text   ← ⚠️ Mermaid 生成失敗
```

#### 問題  
1. 節錄混入「最壞情況 O(n²)」等解析。  
2. Mermaid 心智圖輸出 `Syntax error in text`。  

---

## Issue 4 — 模擬題過度自動延伸

### 輸出示例
```text
題目內容
智慧型故障診斷系統知識庫建置與管理方案
…
✅ 參考答案
知識獲取 (Knowledge Acquisition)：
…（大量範例答案）
```

#### 問題  
系統原僅需產生題幹，卻自動附上過於完整的範例答案。  

---

## 🔧 Agent Check List

1. **流程順序**  
   - 讀取原始檔 → **題幹抽取** → 清洗 → 產出  
   - 確認抽取步驟在 **摘要/分類之前**。  

2. **正規表達式 / 分隔符**  
   - 是否混用 `‵‵‵` 與 ``` ？請統一使用 ```。  
   - 是否誤把「（10分）」「✅」當作題目內容？  

3. **Prompt 模板**  
   - 有無要求 LLM「說明」「解析」？  
   - 應加入：`請僅輸出題幹，不得輸出任何解析或答案`。  

4. **Chunk / Token 策略**  
   - Chunk size ≥ 1200 tokens，overlap ≥ 50 tokens。  
   - 以 `## 題目編號` 或空行分段，避免題幹被截斷。  

5. **心智圖生成**  
   - Prompt 第一行必須是 `mindmap`，且輸出不得再包 ```mermaid。  

6. **單元測試**  
   - 為 Issue 1–4 各建立最小測例，驗證修正後僅輸出題幹。  

---

## ⏩ 回報格式

```text
### Issue X
Root-Cause：
Fix Plan：
Validation：
```

完成後彙總所有 Issue；如發現其他潛在問題，亦請以相同格式補充。
