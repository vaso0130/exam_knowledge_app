import google.generativeai as genai
import asyncio
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import os
from ..utils.json_parser import extract_json_from_text

class GeminiClient:
    def __init__(self, api_key: str = None):
        load_dotenv()
        self.api_key = api_key or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("請設定 GEMINI_API_KEY 或 GOOGLE_API_KEY 環境變數")
        
        genai.configure(api_key=self.api_key)
        model_name = os.getenv('GEMINI_MODEL_NAME', 'gemini-2.5-flash') # Default to gemini-2.5-flash if not set
        self.model = genai.GenerativeModel(model_name)
        
        self.generation_config = genai.types.GenerationConfig(
            temperature=0.2,
            top_p=0.9,
            max_output_tokens=8192,
            response_mime_type="application/json"
        )
    
    async def _generate_with_json_parsing(self, prompt: str) -> Optional[Dict[str, Any]]:
        raw_response = await self.generate_async(prompt)
        if not raw_response:
            return None
        
        parsed_json = extract_json_from_text(raw_response)
        return parsed_json

    async def generate_async(self, prompt: str, is_json: bool = True) -> str:
        try:
            config = self.generation_config if is_json else genai.types.GenerationConfig(
                temperature=0.3,
                top_p=0.9,
                max_output_tokens=4096
            )
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=config
            )
            return response.text
        except Exception as e:
            print(f"Gemini API 錯誤: {e}")
            return ""

    async def parse_exam_paper(self, text: str) -> Dict[str, Any]:
        """
        解析考卷內容，自動分割題目並識別考科，並進行難度分級
        """
        prompt = f"""
        你是一位專精於解析台灣國家考試題庫的 AI 分析師。你的核心任務是將輸入的文本，精準地轉換為結構化的 JSON 格式，並確保最終輸出的可讀性。請嚴格遵循以下所有準則進行分析。

        ### I. 核心任務概覽
        1.  **內容定性**：判斷文本類型（考卷或學習資料）與專業考科。
        2.  **題目整合**：若為考卷，依據「黃金準則」將關聯在一起的題組整合為單一題目物件，但切記無將不同題組混淆，比方說:
        -   **承上題、接上題、延續上題、根據上題、基於前題等**：這些關鍵字表示當前題目與前一題有關聯，應將它們合併為一個項目。
        -   **無關聯的題目**：如果題目與題目之間提到相同關鍵字，比方說虛擬碼、資訊安全等，但是沒有上面的關鍵字，勿將他們視為同一題，因為他們可能是在同一個科目的考卷上。
        3.  **學習資料提取**：若為學習資料，則提取其摘要與核心知識點。
        4.  **智能格式化**：處理程式碼、理解語意格式，並優化排版。
        5.  **難度分析**：為每個考題進行難度分級。


        ---

        ### II. 題目分割黃金準則：
        **這是最重要的準則。你的目標是確保每一個輸出的 `stem` 都是一個「可以獨立作答」的完整問題。**

        *   **核心概念：題目主要題幹 (Shared Context)**
            *   一份考卷的大題，通常包含兩部分：
                1.  **題目主要題幹**：在頂層題號（如「一、」）之後、第一個子問題（如「(一)」）之前的所有前導描述。
                2.  **子問題列表**：以 `(一)`、`(二)` 或 `(1)`、`(2)` 標示的多個具體問題。

        *   **分割與重組的執行演算法**：
            1.  **識別大題**：找到「一、」、「二、」等頂層題號。
            2.  **完整提取I**：將從一個頂層題號開始，直到下一個頂層題號出現之前（或文件結束）的所有內容，視為**一個完整的大題**。
            3.  **完整提取II**：如果出現承上題、接上題、延續上題、根據上題、基於前題等，無視頂層題號，將兩個大題目視為同一題，如果沒有出現承上題、接上題、延續上題、根據上題、基於前題等關鍵字，**請勿將他們視為同一題**。
        
        **目標**：將一個邏輯上完整的大題（包含所有子問題）放在一個 `stem` 內。    
        
        ---

        ### III. 其他分析準則

        *   **準則 A：內容類型與考科判斷**
            *   **內容類型判斷**：
                *   **判斷為「考卷 (exam_paper)」的訊號**：出現明確題號、配分、考試時間、座號等。
                *   **判斷為「學習資料 (study_material)」的訊號**：出現章節標題、大段連續的說明性文字。
            *   **考科識別 (嚴格限制)**：
                1.  **分析**：首先，根據文本中的關鍵術語進行分析。
                2.  **選擇**：然後，**務必**從以下**固定列表**中選擇最符合的一個考科填入 `subject` 欄位。
                    *   `資料結構` - 通常是演算法、資料結構相關的題目。
                    *   `資訊管理` - 通常是資訊系統、管理相關的題目。
                    *   `資通網路與資訊安全` - 通常是網路安全、資安相關的題目，如果題目有提到個資法條或是資安相關議題，也請放入這裡。
                    *   `資料庫應用` - 通常是實體關聯圖、資料庫設計、SQL 查詢相關的題目。
                3.  **後備選項**：如果內容明顯不屬於以上任何一項，請統一使用 `資訊管理`。**禁止**創造列表中不存在的考科名稱。

        *   **準則 B：題目難度分級標準**
            *   請根據以下標準，為**每一個**最終組合好的 `stem` 評定難度。
            *   **🟢 簡單題目（高引導）**
                *   **特徵**：明確指定分析框架或方法。
                *   **關鍵詞**：「請說明...」、「請解釋...」、「依據...框架」。
                *   **題目類型**：定義型、說明型。
            *   **🟡 中等題目（中引導）**
                *   **特徵**：提供部分引導，但不指定具體分析框架。
                *   **關鍵詞**：「請分析...」、「請比較...」、「請評估...」。
                *   **題目類型**：分析型、比較型。
            *   **🔴 困難題目（低引導）**
                *   **特徵**：開放性問題，需要綜合多種知識。
                *   **關鍵詞**：「請設計...」、「制定策略...」、「提出解決方案...」。
                *   **題目類型**：設計型、策略型、綜合應用型。

        *   **準則 C：格式化規則**
            *   **程式碼格式化**：信任輸入的縮排，只需用 ```pseudocode ... ``` 包裹程式碼區塊。**絕對不要**修改縮排。
            *   **語意格式化 (處理底線等)**：
                1.  **掃描關鍵句**：在文本中尋找描述格式意義的句子，例如「**加底線的屬性為該表格之主鍵**」。
                2.  **理解規則**：理解這句話的含義（底線 = 主鍵）。
                3.  **應用規則**：在最終輸出的 `stem` 中，將這個語意資訊以文字形式**明確標註**出來。例如，將 `員工 (員工編號)` 轉換為 `員工 (員工編號 (主鍵))`。
            *   **語意重排版 (Readability Reformatting - 新增)**：
                1.  **檢查結構**：在組合完 `stem` 後，檢查其排版。
                2.  **識別邏輯區塊**：找出文本中的「前導說明」、「表格綱要」、「子問題列表」等邏輯區塊。
                3.  **優化排版**：如果這些區塊都擠在同一個段落，請使用換行和 Markdown 列表（例如，將 `(一)...(二)...` 轉換成一個清晰的點列或編號列表）來重新組織 `stem` 的內容，使其結構清晰、易於閱讀，以下是範例:
                ```台灣是一個多山國家，依據這格條件回答下列問題:(一) 台灣的地理特徵是什麼？(二) 台灣的氣候特徵是什麼？(三) 台灣的文化特徵是什麼？```
                應變成:
                ```
                台灣是一個多山國家，依據這格條件回答下列問題:
                (一) 台灣的地理特徵是什麼？
                (二) 台灣的氣候特徵是什麼？
                (三) 台灣的文化特徵是什麼？
                ```
        ---

        ### IV. 輸入文本
        ```
        {text}
        ```

        ### V. 輸出格式 (JSON)

        **處理步驟：**
        1. 首先識別資料的屬性為何 - 準則 A
        2. 檢查每個題目是否包含關聯性關鍵字（承上題、接上題、延續上題、根據上題、基於前題等）- 題目分割黃金準則
        3. 如果發現關聯性關鍵字，將該題與前一題合併為一個項目 - 題目分割黃金準則
        4. 如果是共享上下文的大題，將其與所有子問題組合成一個完整的題目項目 - 題目分割黃金準則
        5. 對每個最終的題目項目進行難度分級 - 準則 B
        6. 將題目格式化產生一定的可讀性 - 準則 C
        7. 分析題目或學習資料的相關知識點。
        8. 最後，將所有項目組合成一個完整的 JSON 結構

        
        你的輸出結構必須根據你在【準則A】中判斷的 content_type 來動態改變，請嚴格遵守！
        **情況一：如果 content_type 是 exam_paper**

        {{
            "content_type": "exam_paper",
            "subject": "從【準則A】的固定列表中選擇的考科名稱",
            "questions": [
                {{
                    "title": "整個大題的簡短標題",
                    "stem": "一個大題的全部內容，並經過【準則C】的排版優化與語意標註。",
                    "knowledge_points": ["相關知識點1", "相關知識點2"],
                    "difficulty": "對整個大題的綜合難度評級 - 用🟢🟡🔴來表示",
                    "guidance_level": "高|中|低",
                    "difficulty_reason": "分級理由"
                }}
            ]
        }}

        **情況二：如果 content_type 是 study_material**
        {{
            "content_type": "study_material",
            "subject": "從【準則A】的固定列表中選擇的考科名稱",
            "summary": "學習資料的摘要。",
            "knowledge_points": ["從資料中提取出的核心知識點1", "核心知識點2", "核心知識點3"]
        }}
        """
        
        return await self._generate_with_json_parsing(prompt) or {}

    async def generate_questions_from_text(self, text: str, subject: str) -> List[Dict[str, Any]]:
        """
        根據完整文本內容生成高品質申論模擬題，並為每個問題自動標註知識點標籤
        專注於生成需要深入分析和應用的題目，而非單純複述知識
        """
        prompt = f"""
        你是一位專業的{subject}科申論題出題專家。請根據提供的學習資料，設計2-4道高品質的申論模擬題。

        **核心要求：**
        1. **絕對禁止**生成「請說明...」、「請解釋...」、「請詳述...」、「...是什麼」等直接複述型題目
        2. **必須創造應用情境**：每道題目都要設計一個虛構但合理的實務情境
        3. **要求深度分析**：題目應該測試學生的分析、比較、評估、設計能力
        4. **多元思考**：題目應該允許多角度思考和論述

        **重要：題目格式要求**
        - **題目內容**：只能包含情境描述和問題要求，絕對不能包含答案步驟、分析過程或解決方案
        - **題目長度**：應該控制在100-200字內，簡潔明確
        - **問題導向**：題目必須以問句結尾，如「請分析...」、「試論述...」、「請提出...」

        **題目設計原則：**
        - 情境導向：創造具體的公司、組織或個人案例
        - 問題解決：要求學生提出解決方案或建議
        - 批判思考：要求分析優缺點、比較不同方法
        - 實務應用：將理論知識應用到實際情況

        **題目難度分級標準**
            *   請根據以下標準，設計申論題難度。
            *   **🟢 簡單題目（高引導）**
                *   **特徵**：明確指定分析框架或方法。
                *   **關鍵詞**：「請說明...」、「請解釋...」、「依據...框架」。
                *   **題目類型**：定義型、說明型。
            *   **🟡 中等題目（中引導）**
                *   **特徵**：提供部分引導，但不指定具體分析框架。
                *   **關鍵詞**：「請分析...」、「請比較...」、「請評估...」。
                *   **題目類型**：分析型、比較型。
            *   **🔴 困難題目（低引導）**
                *   **特徵**：開放性問題，需要綜合多種知識。
                *   **關鍵詞**：「請設計...」、「制定策略...」、「提出解決方案...」。
                *   **題目類型**：設計型、策略型、綜合應用型。

        **學習資料：**
        ```
        {text}
        ```

        **請以JSON格式回應，包含2-4道不同難度的申論題：**
        {{
            "questions": [
                {{
                    "title": "簡潔標題（5-8個字）",
                    "question": "純粹的題目內容（只包含情境描述和問題要求，不包含答案或分析過程）",
                    "answer": "簡潔的參考答案（包含核心要點，**必須提供，不可為空或佔位符，絕對不能出現「This is not included in the prompt.」或類似的佔位符，例如：'This is not included in the prompt.' 或 'The answer is not provided.'**）",
                    "difficulty": "對整個模擬題的綜合難度評級 -用🟢🟡🔴來表示 ", 
                    "knowledge_points": ["相關知識點1", "相關知識點2", "相關知識點3"],
                    "guidance_level": "引導程度 -用 高|中|低 回答"。
                }}
            ]
        }}
        """
        parsed_json = await self._generate_with_json_parsing(prompt)
        return parsed_json.get("questions", []) if parsed_json else []

    async def generate_answer(self, question_text: str) -> Optional[Dict[str, Any]]:
        """
        根據提供的問題文本，生成詳細的答案。

        Args:
            question_text: 問題的完整文字。

        Returns:
            一個包含答案的字典，例如：{'answer': '這是詳細的回答...'}
        """
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
    - **禁止使用口語化、非正式或隨意的語氣，像是親愛的朋友您好，以下是有關... 這樣的回答方式是不對的，沒有人會在考卷上這樣回答**

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

📤 **請以以下 JSON 結構回應，切記勿為回傳其他任何內容或格式：**
```json
{{
    "answer": "（請在此填入你的完整繁體中文書面作答，符合台灣考試風格）",
    "sources": [{{"url": "來源連結", "title": "網站標題", "snippet": "簡短說明"}}]
}}
"""
        return await self._generate_with_json_parsing(prompt) or {'answer': '', 'sources': []}

    async def generate_summary(self, text: str) -> Dict[str, Any]:
        """
        生成摘要
        """
        prompt = f"""
        請為以下內容生成結構化的知識重點摘要。請特別注意：

        1. **提取表格資訊**：如果內容包含表格，請將表格資訊轉換為清晰的重點項目
        2. **技術術語整理**：將專業術語、技術名稱、攻擊手法等整理成學習要點，**每個術語都要提供簡潔的解釋**
        3. **避免重複**：不要直接複述原文，而是要歸納出關鍵概念和要點
        4. **實用性導向**：重點應該是便於學習和記憶的知識點
        5. **分類整理**：將知識點分為核心概念、技術術語、分類資訊、實務應用等類別
        6. **去品牌化**：避免使用具體的品牌名稱或產品名稱，專注於技術和概念本身，除非品牌名稱是學習重點的一部分。

        **內容：**
        {text[:6000]}

        請以JSON格式回應，生成高品質的學習摘要：
        {{
            "summary": "一句話概括整體內容的核心主題",
            "key_concepts": [
                {{"name": "核心概念1", "description": "簡潔的解釋說明"}},
                {{"name": "核心概念2", "description": "簡潔的解釋說明"}}
            ],
            "technical_terms": [
                {{"name": "技術術語1", "description": "一句話解釋這個術語的含義和作用"}},
                {{"name": "技術術語2", "description": "一句話解釋這個術語的含義和作用"}}
            ],
            "classification_info": [
                {{"name": "分類項目1", "description": "分類的詳細說明或等級內容"}},
                {{"name": "分類項目2", "description": "分類的詳細說明或等級內容"}}
            ],
            "practical_applications": [
                {{"name": "實務應用1", "description": "具體的應用場景或實施方法"}},
                {{"name": "實務應用2", "description": "具體的應用場景或實施方法"}}
            ],
            "bullets": ["整合性重點1：包含詳細說明", "整合性重點2：包含詳細說明", "整合性重點3：包含詳細說明"]
        }}
        """
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'summary' in parsed_json and 'bullets' in parsed_json:
            return parsed_json
        return {"summary": "無法生成摘要", "bullets": []}

    async def generate_quick_quiz(self, content: str, subject: str) -> List[Dict[str, Any]]:
        """生成快速測驗選擇題"""
        
        prompt = f"""
        你是一位專業的教育測驗設計師。請根據以下學習資料，設計5道選擇題來快速檢驗學習者對重點知識的掌握。

        **設計原則：**
        1. 題目應該測試對核心概念的理解，而非細節記憶
        2. 避免涉及具體的公司名稱、產品名稱或時事新聞
        3. 專注於知識點本身的原理、概念和應用
        4. 每題提供4個選項，其中只有1個正確答案
        5. 提供簡潔明確的解析說明

        **科目領域：** {subject}

        **學習資料：**
        {content}

        **請以JSON格式回應，包含5道選擇題：**
        {{
            "quiz": [
                {{
                    "question": "題目內容",
                    "type": "multiple_choice",
                    "options": ["A. 選項1", "B. 選項2", "C. 選項3", "D. 選項4"],
                    "correct_answer": "A",
                    "explanation": "解析說明"
                }}
            ]
        }}
        """
        
        try:
            parsed_response = await self._generate_with_json_parsing(prompt)
            if parsed_response and 'quiz' in parsed_response:
                return parsed_response['quiz']
            else:
                print("警告：無法解析快速測驗JSON回應")
                return []
        except Exception as e:
            print(f"生成快速測驗錯誤: {e}")
            return []

    async def generate_mindmap(self, subject: str, knowledge_points: List[str]) -> str:
        """
        根據輸入的文本，生成 Mermaid.js 格式的心智圖 Markdown。
        """
        # 將知識點列表轉換為 Mermaid 節點
        nodes_text = ""
        for kp in knowledge_points:
            # 確保 kp 是字串類型，防止 'dict' object has no attribute 'replace' 錯誤
            if isinstance(kp, dict):
                # 如果是字典，嘗試提取有意義的字串值
                kp_str = kp.get('name', '') or kp.get('title', '') or kp.get('text', '') or str(kp)
            elif kp is None:
                continue  # 跳過 None 值
            else:
                kp_str = str(kp)  # 確保是字串
            
            # 確保知識點不含破壞格式的字元，並加上引號
            safe_kp = kp_str.replace('\\', '\\\\').replace('"', '\"').replace('\n', ' ').replace('\r', '')
            nodes_text += f"""      "{safe_kp}"\n"""

        # 準備知識點字串列表用於顯示
        safe_knowledge_points = []
        for kp in knowledge_points:
            if isinstance(kp, dict):
                kp_str = kp.get('name', '') or kp.get('title', '') or kp.get('text', '') or str(kp)
            elif kp is None:
                continue
            else:
                kp_str = str(kp)
            safe_knowledge_points.append(kp_str)

        prompt = f"""
        請根據以下核心主題和關鍵知識點，生成一個 Mermaid.js 格式的心智圖。
        心智圖應該以核心主題為根節點，並將每個知識點作為其主要分支。
        請確保輸出的格式是純粹的 Mermaid Markdown，以 `mindmap` 開頭。
        重要：節點的文字已用雙引號包起來，請直接使用。

        核心主題：{subject}
        
        知識點：
{', '.join(safe_knowledge_points)}

        Mermaid 心智圖範例格式：
        mindmap
          root(("{subject}"))
{nodes_text}
        
        請直接輸出 Mermaid 代碼，不要包含任何額外的解釋或 ```mermaid ... ``` 標記。
        """
        # 對於心智圖，我們期望純文字輸出，而不是 JSON
        try:
            # 建立一個不要求 JSON 的生成設定
            text_generation_config = genai.types.GenerationConfig(
                temperature=0.3,
                top_p=0.9,
                max_output_tokens=2048,
            )
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=text_generation_config
            )
            # 清理回應，確保是合法的 Mermaid 代碼
            mermaid_code = response.text.strip()
            if not mermaid_code.startswith("mindmap"):
                return "mindmap\n  root((生成失敗))\n    請檢查輸入內容或 API 連線"
            return mermaid_code
        except Exception as e:
            print(f"生成心智圖時發生錯誤: {e}")
            return "mindmap\n  root((錯誤))\n    無法生成心智圖"

    async def extract_knowledge_points(self, text: str, subject: str) -> Optional[List[str]]:
        """從文本中提取知識點"""
        prompt = f"""
        你是一位專業的{subject}科老師，你的任務是從給定的考試題目或文本中，精準地提取出核心的「知識點」。

        **任務說明：**
        1.  **分析文本**：仔細閱讀以下內容。
        2.  **提取知識點**：識別出文本所測驗的2到5個最重要、最核心的觀念或術語。知識點應該是簡潔、具體的名詞或短語。
        3.  **格式化輸出**：將提取的知識點以JSON格式輸出。

        **文本內容：**
        ```
        {text}
        ```

        **輸出要求：**
        -   必須是嚴格的JSON格式。
        -   JSON物件應包含一個鍵 `knowledge_points`。
        -   `knowledge_points` 的值應該是一個字串列表，每個字串就是一個知識點。

        **範例：**
        -   **輸入文本（公民與社會）**：「根據我國《公司法》規定，股東會是公司的最高權力機構。請問，若A公司決定進行合併，應由哪個機構決議？」
        -   **輸出JSON**：
            ```json
            {{
                "knowledge_points": [
                    "公司法",
                    "股東會職權",
                    "公司合併"
                ]
            }}
            ```
        -   **輸入文本（物理）**：「一個質量為2公斤的物體，在光滑水平面上受到10牛頓的水平力作用，請問其加速度為何？」
        -   **輸出JSON**：
            ```json
            {{
                "knowledge_points": [
                    "牛頓第二運動定律",
                    "F=ma",
                    "加速度計算"
                ]
            }}
            ```

        請現在分析給定的文本並返回JSON結果。
        """
        
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'knowledge_points' in parsed_json and isinstance(parsed_json['knowledge_points'], list):
            return parsed_json['knowledge_points']
        
        print(f"無法從回應中解析出知識點: {parsed_json}")
        return None

    async def generate_tags(self, text: str, subject: str) -> List[str]:
        """生成標籤"""
        prompt = f"""
        基於以下「{subject}」領域的內容，請生成3-6個精確且有代表性的標籤關鍵字。
        標籤應該是常見的技術術語、概念或標準。

        內容：
        {text[:2000]}

        請以JSON格式回應：
        {{
            "tags": ["標籤1", "標籤2", "標籤3", ...]
        }}
        """
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'tags' in parsed_json:
            return parsed_json.get("tags", [])
        return []