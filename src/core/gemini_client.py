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
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
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
        請分析以下文本內容，這可能是一份考卷或包含多個題目的學習資料。

        任務：
        1. 自動識別考科類別（從：資料結構、資訊管理、資通網路與資訊安全、資料庫應用、或其他）
        2. 判斷內容類型（exam_paper or study_material）
        3. 如果是考卷，請將每個題目分割開來（注意：一個題目可能包含多個小問題，這些應該視為同一題）
        4. 如果是學習資料，請提取核心知識點
        5. **新增**：對每個考題進行難度分級分析

        **重要：題目分割原則**
        - 一個題目可能包含多個部分（如：問題描述 + 程式碼 + 多個小問題）
        - 只有明確的題號分隔（如「第一題」、「1.」、「題目二」）才分割
        - 同一題目內的不同部分（如「(10分)」、「請分析」、「請說明」）應合併為一題
        - 程式碼和相關問題應該保持在同一題中
        - **程式碼/虛擬碼格式**：如果題目包含程式碼或虛擬碼，請務必使用 Markdown 的 fenced code blocks (```) 包裹起來，並指定語言（如 ````python` 或 ````pseudocode`）。**特別注意：請務必保留原始程式碼/虛擬碼的縮排和換行，如果原始格式有誤（例如縮排丟失或單行顯示），請根據程式語言的慣例進行正確的排版和縮排，使其易於閱讀。
        - **關聯題目處理**：如果題目提到「承上題」、「接上題」、「延續上題」、「根據上題」、「基於前題」等字樣，應將相關聯的題目合併為同一題
        - **連續性題目**：如果某題的解答需要依賴前一題的結果或內容，應考慮將它們視為同一題的不同部分
        - **合併方式**：合併題目時，使用較前面的題號，標題可以概括兩題內容，stem 包含兩題的完整文字

        **題目難度分級標準：**

        ### 🟢 簡單題目（高引導）
        - **特徵**：明確指定分析框架或方法（如「從 CIA 三要素的角度」、「運用 SWOT 分析法」）
        - **關鍵詞**：「從...的角度」、「運用...分析」、「依據...框架」、「請說明...」、「請解釋...」
        - **題目類型**：定義型、說明型、按框架分析型

        ### 🟡 中等題目（中引導）
        - **特徵**：提供部分引導但不指定具體分析框架
        - **關鍵詞**：「請分析...」、「請比較...」、「請評估...」、「討論...的影響」
        - **題目類型**：分析型、比較型、評估型

        ### 🔴 困難題目（低引導）
        - **特徵**：開放性問題，需要綜合多種知識和創新思維
        - **關鍵詞**：「請設計...」、「制定策略...」、「提出解決方案...」、「綜合論述...」
        - **題目類型**：設計型、策略型、綜合應用型

        文本內容：
        {text}

        **處理步驟：**
        1. 首先識別所有明確的題號和題目
        2. 檢查每個題目是否包含關聯性關鍵字（承上題、接上題、延續上題、根據上題、基於前題等）
        3. 如果發現關聯性關鍵字，將該題與前一題合併為一個項目
        4. 對每個最終的題目項目進行難度分級
        5. 有關包含程式碼題目說明，假設碰上這種問題：「根據下列的虛擬碼,若n=21則傳回的答案為何?請說明。其中 floor() 為數學上的地板函數(floor function)。(20分) function splitSum(n: integer) returns integer if n <= 1 then return 1 a<- floor(n/2) b<- floor(n/3) return splitSum(a) + splitSum(b)」，其中包含了虛擬碼，應該是因為前面處理檔案時沒有處理好，導致虛擬碼/程式碼變成一整排，切記一定把它變成程式碼/虛擬碼區塊，並且一定要把排版/縮排整理到正常樣子，如以下樣子：
        
        根據下列的虛擬碼,若n=21則傳回的答案為何?請說明。其中 floor() 為數學上的地板函數(floor function)。(20分)
        ```
        function splitSum(n: integer) returns integer
            if n <= 1 then 
                return 1
            a<- floor(n/2)
            b<- floor(n/3)
                return splitSum(a) + splitSum(b)
        ```

        像這樣正確的虛擬碼程式碼縮排，讀者才知道題目在問什麼，才方便閱讀。
        
        6. 有關包含程式碼題目說明，假設碰上這種問題：根據下列的虛擬碼，若n=10則傳回的答案為何?請說明。其中 floor() 為數學上的地板函數(floor function)。
        ```
        function splitSum(n: integer) returns integer
        if n <= 0 then 
        return 0
        a<- floor(n/4)
        b<- floor(n/5)
        return splitSum(a) + splitSum(b)
        ```
        其中包含了程式碼，應該是因為前面處理檔案時沒有處理好，導致縮排消失，請試著把他縮排/排版整理到以下樣子：

        根據下列的虛擬碼，若n=10則傳回的答案為何?請說明。其中 floor() 為數學上的地板函數(floor function)。
        ```
        function splitSum(n: integer) returns integer
            if n <= 0 then 
                return 0
            a<- floor(n/4)
            b<- floor(n/5)
                return splitSum(a) + splitSum(b)
        ```
        像這樣正確的虛擬碼程式碼縮排，讀者才知道題目在問什麼，才方便閱讀。

        以上第五、六點是針對虛擬碼/程式碼的特殊處理，請務必注意，不是只有示範題目才需要整理，任何題目如果有虛擬碼/程式碼，都需要這樣處理。

        請以JSON格式回應：
        {{
            "content_type": "exam_paper" or "study_material",
            "subject": "推測的考科名稱",
            "questions": [
                {{
                    "title": "題目的簡短標題（5-10個字）",
                    "stem": "完整題目內容（包含所有部分：問題描述、程式碼、所有小問題，**不包含任何解析或答案**）",
                    "knowledge_points": ["相關知識點1", "相關知識點2"],
                    "difficulty": "簡單|中等|困難",
                    "guidance_level": "高|中|低",
                    "difficulty_reason": "分級理由（說明為什麼是這個難度）"
                }}
            ]
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
                    "difficulty": "簡單|中等|困難",
                    "knowledge_points": ["相關知識點1", "相關知識點2", "相關知識點3"],
                    "guidance_level": "引導程度（高|中|低）"
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
        你是一位頂尖的領域專家，也是一個台灣國考補習班老師，請針對以下問題，提供一個專業、深入、且結構化的詳盡回答且符合台灣國考常用作答方式。

        **問題：**
        ```
        {question_text}
        ```

        **回答要求：**
        1.  **深入分析**：不僅僅是表面答案，要提供背景、原理、和多角度的解釋。
        2.  **結構清晰**：使用點列、標題、或分段來組織內容，使其易於理解。
        3.  **專業準確**：確保所有資訊都是最新且準確的。
        4.  **程式碼/虛擬碼格式**：如果答案包含程式碼或虛擬碼，請務必使用 Markdown 的 fenced code blocks (```) 包裹起來，並指定語言（如 ````python` 或 ````pseudocode`）。
        5.  **答案內容必須是純文字字串**：即使答案內容包含多個部分或結構化資訊，最終的 `answer` 欄位值也必須是一個單一的、格式化好的 Markdown 字串，而不是巢狀的 JSON 物件。
        6.  **表格（可選）**：如果適合在作答中加入表格，請加入表格，但是不能整個答案都只有表格。
        7.  **列出參考來源**：若有可靠的網路資源，請提供 1-3 筆來源資料，包含 `url`、`title` 與簡短 `snippet`。

        **請以嚴格的JSON格式回應：**
        ```json
        {{
            "answer": "（在這裡填寫你詳細、結構化的專業回答）",
            "sources": [{{"url": "來源連結", "title": "網站標題", "snippet": "簡短說明"}}]
        }}
        ```
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