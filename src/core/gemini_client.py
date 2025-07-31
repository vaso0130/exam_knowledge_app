import google.generativeai as genai
import asyncio
import json
import time
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
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        # 已移除所有配額與頻率限制
        
        # 生成配置
        self.generation_config = genai.types.GenerationConfig(
            temperature=0.2,
            top_p=0.9,
            max_output_tokens=8192,
            response_mime_type="application/json"  # 要求 JSON 格式輸出
        )
    
    # 已移除配額計數與限制相關方法
    
    # 已移除配額查詢方法
    
    async def _generate_with_json_parsing(self, prompt: str) -> Optional[Dict[str, Any]]:
        """異步生成並解析 JSON 回應"""
        raw_response = await self.generate_async(prompt)
        if not raw_response:
            return None
        
        parsed_json = extract_json_from_text(raw_response)
        return parsed_json

    async def generate_async(self, prompt: str) -> str:
        """異步生成回應，無配額與頻率限制"""
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=self.generation_config
            )
            return response.text
        except Exception as e:
            print(f"Gemini API 錯誤: {e}")
            return ""
    
    def generate_sync(self, prompt: str) -> str:
        """同步生成回應"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            return response.text
        except Exception as e:
            print(f"Gemini API 錯誤: {e}")
            return ""

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
    
    async def detect_type(self, text: str) -> bool:
        """判斷文本是否為考試題目"""
        prompt = f"""
請判斷以下文本是否為考試題目。如果是考試題目（包含選擇題、填充題、問答題等），請回答「是」，否則回答「否」。

文本內容：
{text[:2000]}  # 限制長度避免超出限制

請只回答「是」或「否」，不要其他說明。
"""
        response = await self.generate_async(prompt)
        return "是" in response.strip() if response else False
    
    async def generate_answer(self, question_text: str) -> Dict[str, Any]:
        """生成標準答案，並附上網路搜尋來源"""
        prompt = f"""
        請針對以下考試題目，執行網路搜尋以尋找相關資料，然後提供一個詳盡的標準答案。

        題目：
        {question_text}

        請遵循以下步驟：
        1.  **網路搜尋**：根據題目內容，搜尋權威的學術文章、官方文件或專業網站。
        2.  **綜合答案**：基於搜尋結果，撰寫一份完整、準確的標準答案。如果答案適合用表格呈現（如比較、分類），請使用 Markdown 表格。
        3.  **提供來源**：列出2-4個最主要且最相關的參考來源。

        請以JSON格式回應，包含以下欄位：
        {{
            "answer": "詳細的標準答案（如果適合，請包含 Markdown 表格）。",
            "sources": [
                {{
                    "title": "來源1的標題",
                    "url": "https://example.com/source1",
                    "snippet": "來源1與題目最相關的簡短摘要或片段。"
                }},
                {{
                    "title": "來源2的標題",
                    "url": "https://example.com/source2",
                    "snippet": "來源2與題目最相關的簡短摘要或片段。"
                }}
            ]
        }}

        請確保答案的專業性和準確性，並且來源是真實可查的。
        """
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'answer' in parsed_json and 'sources' in parsed_json:
            return parsed_json
        return {"answer": "無法解析答案", "sources": []}
    
    async def generate_highlights(self, text: str) -> List[str]:
        """生成重點摘要"""
        prompt = f"""
請將以下內容歸納成3-7個重點項目，每個項目一行。

內容：
{text[:3000]}

請以JSON格式回應，格式如下：
{{
    "highlights": ["重點1", "重點2", "重點3", ...]
}}
"""
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'highlights' in parsed_json:
            return parsed_json.get("highlights", [])
        return []
    
    async def classify_subject(self, text: str) -> str:
        """分類科目"""
        subjects = ["資料結構", "資訊管理", "資通網路與資訊安全", "資料庫應用"]
        
        prompt = f"""
請將以下內容歸類到四大科目之一：
1. 資料結構
2. 資訊管理  
3. 資通網路與資訊安全
4. 資料庫應用

內容：
{text[:2000]}

請只回答科目名稱，不要其他說明。
"""
        response = await self.generate_async(prompt)
        
        # 找到最匹配的科目
        if response:
            for subject in subjects:
                if subject in response:
                    return subject
        
        return "資訊管理"  # 預設分類
    
    async def web_search(self, query: str) -> Dict[str, Any]:
        """執行網路搜尋並整理結果"""
        prompt = f"""
        請針對以下查詢進行網路搜尋，並整理出一個簡潔的摘要和3-5個主要來源連結。

        查詢: "{query}"

        請以JSON格式回應，包含以下欄位：
        {{
            "summary": "針對查詢的綜合摘要，約100-150字。",
            "sources": [
                {{
                    "title": "來源1的標題",
                    "url": "https://example.com/source1",
                    "snippet": "來源1的簡短摘要或相關片段。"
                }},
                {{
                    "title": "來源2的標題",
                    "url": "https://example.com/source2",
                    "snippet": "來源2的簡短摘要或相關片段。"
                }}
            ]
        }}
        """
        # 注意：Gemini 模型本身具有即時的網路存取能力
        # 我們只需要建構正確的提示詞來觸發這個功能
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'summary' in parsed_json and 'sources' in parsed_json:
            return parsed_json
        return {
            "summary": "無法執行網路搜尋或解析結果。",
            "sources": []
        }

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
    
    async def generate_summary(self, text: str) -> Dict[str, Any]:
        """生成摘要"""
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

**重要要求：**
- 每個技術術語都必須提供一句話的清晰解釋
- 分類資訊要包含具體的分級內容（如A-E級的具體說明）
- 實務應用要說明具體的實施方法或場景
- 核心概念要有簡潔的定義說明
"""
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'summary' in parsed_json and 'bullets' in parsed_json:
            return parsed_json
        return {"summary": "無法生成摘要", "bullets": []}
    
    async def generate_questions(self, bullets: List[str]) -> List[Dict[str, Any]]:
        """依據重點生成模擬申論題"""
        prompt = f"""
基於以下重點內容，請生成2-4題模擬申論題。所有題目都應該是需要深入分析、論述的申論題型。

**重點內容：**
{chr(10).join(f'- {bullet}' for bullet in bullets)}

**申論題要求：**
1.  **應用與分析**：題目需要學生進行深入分析、比較、評述或論證，而不是單純複述重點內容。
2.  **創造情境**：請設計一個虛構但合理的情境，讓學生在該情境下應用這些知識點。
3.  **答案深度**：答案應該包含多個要點，需要條理清晰的論述。如果適合，可以要求學生用表格方式整理比較。
4.  **開放性**：題目應具有開放性，允許多角度思考。

**重要：** 絕對不要生成「請解釋...」、「...是什麼」或「請詳述...」這類直接要求複述知識點的題目。題目必須是應用題或分析題。

**請以JSON格式回應：**
{{
    "questions": [
        {{
            "stem": "申論題目內容（要求深入分析或論述，並包含一個應用情境）",
            "answer": "詳細的參考答案（如果適合用表格，請使用 Markdown 表格格式）",
            "type": "Essay",
            "points": "評分要點或考查重點"
        }}
    ]
}}

**範例申論題類型：**
-   **情境分析**：一間新創公司正在開發一個需要處理大量用戶敏感資料的社交平台，請你作為資安顧問，根據CIA三要素，為他們設計一套資安基礎架構的建議方案。方案需包含具體的技術或策略建議。
-   **比較評估**：請分析並比較對稱加密與非對稱加密在確保資料「機密性」與「完整性」方面的優缺點，並論述在何種情境下應優先選擇哪種加密方式。
-   **趨勢評述**：請評述零信任（Zero Trust）架構的發展趨勢，並分析其對傳統邊界安全模型的挑戰與影響。
"""
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'questions' in parsed_json:
            return parsed_json.get("questions", [])
        return []
    
    async def parse_exam_paper(self, text: str) -> Dict[str, Any]:
        """
        解析考卷內容，自動分割題目並識別考科，並進行難度分級
        """
        prompt = f"""
請分析以下文本內容，這可能是一份考卷或包含多個題目的學習資料。

任務：
1. 自動識別考科類別（從：資料結構、資訊管理、資通網路與資訊安全、資料庫應用、或其他）
2. 判斷內容類型（考卷題目 or 學習資料）
3. 如果是考卷，請將每個題目分割開來（注意：一個題目可能包含多個小問題，這些應該視為同一題）
4. 如果是學習資料，請提取核心知識點
5. **新增**：對每個考題進行難度分級分析

**重要：題目分割原則**
- 一個題目可能包含多個部分（如：問題描述 + 程式碼 + 多個小問題）
- 只有明確的題號分隔（如「第一題」、「1.」、「題目二」）才分割
- 同一題目內的不同部分（如「(10分)」、「請分析」、「請說明」）應合併為一題
- 程式碼和相關問題應該保持在同一題中
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

請以JSON格式回應：
{{
    "content_type": "exam" 或 "study_material",
    "subject": "推測的考科名稱",
    "confidence": 0.8,
    "items": [
        {{
            "type": "question" 或 "knowledge_section",
            "number": "題號或章節號",
            "title": "題目的簡短標題（5-10個字）",
            "stem": "完整題目內容（包含所有部分：問題描述、程式碼、所有小問題）",
            "answer": "答案（如果有的話）",
            "points": "分數或重點",
            "knowledge_points": ["相關知識點1", "相關知識點2"],
            "difficulty": "簡單|中等|困難",
            "guidance_level": "高|中|低",
            "difficulty_reason": "分級理由（說明為什麼是這個難度）"
        }}
    ]
}}

分析指引：
- **首先檢查關聯性**：在分題之前，先掃描整個文本，找出所有包含「承上題」、「接上題」、「延續上題」、「根據上題」、「基於前題」等關聯性字樣的題目
- **關聯題目合併處理**：如發現關聯性字樣，必須將該題與其前一題合併為同一個題目單位，合併後的題目應包含兩題的完整內容
- 如果看到明確的題號（「第一題」、「1.」、「(1)」、「題目一」），才進行題目分割，但要注意關聯性
- 同一題目內的程式碼、圖表、多個小問題都應該包含在同一個 "stem" 中
- 考科判斷依據：關鍵字、專業術語、內容領域
- 每個題目都要完整提取，不要遺漏任何部分
- **難度分級**：仔細分析題目的引導程度和複雜度，準確判定難度等級

**關聯題目處理步驟：**
1. 掃描文本，識別關聯題目（包含關聯性關鍵字的題目）
2. 對於每個關聯題目，將其與前一題的內容合併
3. **處理連續關聯**：如果一個題目被關聯到另一個已經被合併的題目，則應該將所有相關題目形成一個群組
   - 例如：第三題 → 第四題（基於前題）→ 第五題（接上題）= 形成一個包含三題的群組
4. 合併後的題目應該有統一的題號（使用較前面的題號）
5. 合併後的 stem 應該包含所有相關題目的完整內容，用適當分隔符分開

範例：
1. **一般題目分割**：「請分析以下演算法...（程式碼）...請說明演算法名稱（10分）...請列出處理過程（10分）」
   這應該視為**一個完整題目**，包含程式碼和兩個小問題。

2. **關聯題目合併**：
   範例1 - 簡單關聯：
   原文：
   「第一題：請設計一個排序演算法...
    第二題：承上題，請分析您設計的演算法的時間複雜度...」
   
   處理結果：應該將第一題和第二題**合併為同一個題目**：
   題號："第一題"
   標題："排序演算法設計與分析"
   內容："第一題：請設計一個排序演算法...\\n\\n第二題：承上題，請分析您設計的演算法的時間複雜度..."

   範例2 - 連續關聯（重要！）：
   原文：
   「第三題：請說明對稱式加密和非對稱式加密的基本原理。
    第四題：基於前題的加密方式，請設計一個混合式加密系統...
    第五題：接上題，請分析您設計的混合式加密系統的效能特性...」
   
   處理結果：第三、四、五題應該**合併為同一個題目群組**：
   題號："第三題"
   標題："加密原理與混合系統設計分析"
   內容：包含三題的完整內容

3. **難度分級範例**：
   - 如果是「請說明演算法名稱」：簡單（高引導，要求說明）
   - 如果是「分析演算法效率並比較不同實現方式」：中等（中引導，要求分析比較）
   - 如果是「設計一個更優化的演算法解決此問題」：困難（低引導，要求創新設計）
"""
        parsed_json = await self._generate_with_json_parsing(prompt)
        return parsed_json or {}

    async def auto_classify_and_process(self, text: str) -> Dict[str, Any]:
        """
        自動分類內容並選擇適當的處理方式
        """
        # 先解析內容
        parsed_content = await self.parse_exam_paper(text)
        
        if not parsed_content:
            return {"error": "無法解析內容"}
        
        content_type = parsed_content.get('content_type', 'study_material')
        subject = parsed_content.get('subject', '其他')
        # Normalize常見科目別稱，避免分類為「其他」
        subject_aliases = {
            '資訊安全': '資通網路與資訊安全',
            '資安': '資通網路與資訊安全',
            '資通安全': '資通網路與資訊安全',
            '網路安全': '資通網路與資訊安全',
        }
        for key, normalized in subject_aliases.items():
            if key in subject:
                subject = normalized
                break
        items = parsed_content.get('items', [])
        
        result = {
            'content_type': content_type,
            'subject': subject,
            'confidence': parsed_content.get('confidence', 0.5),
            'items': items,
            'questions': []
        }
        
        # 根據內容類型進行後續處理
        if content_type == 'exam' and items:
            # 考卷題目：直接轉換為問題格式，包含難度分級資訊
            questions = []
            for item in items:
                if item.get('type') == 'question':
                    question = {
                        'title': item.get('title', '無標題'),
                        'stem': item.get('stem', ''),
                        'answer': item.get('answer', ''),
                        'type': 'Essay',  # 預設為申論題
                        'points': item.get('points', ''),
                        'knowledge_points': item.get('knowledge_points', []),
                        'difficulty': item.get('difficulty', '中等'),  # 新增：難度等級
                        'guidance_level': item.get('guidance_level', '中'),  # 新增：引導程度
                        'difficulty_reason': item.get('difficulty_reason', ''),  # 新增：分級理由
                        'tags': [subject, content_type]
                    }
                    questions.append(question)
            result['questions'] = questions
            
        elif content_type == 'study_material':
            # 學習資料：生成相關問題
            generated_questions = await self.generate_questions_from_text(text, subject)
            result['questions'] = generated_questions
        
        return result

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
- **題目長度**：應該盡可能控制在100-200字內，簡潔明確，且不能出現該題目相關知識的解釋，比方說問CIA要素，結果下還好心附上CIA三要素的解釋，這是不對的。
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
            "answer": "詳細的參考答案（結構化論述，包含多個要點）",
            "difficulty": "簡單|中等|困難",
            "knowledge_points": ["相關知識點1", "相關知識點2", "相關知識點3"],
            "guidance_level": "引導程度（高|中|低）"
        }}
    ]
}}

**難度分級的關鍵判斷標準：**

### 🟢 簡單題目（高引導）
- **必須包含明確分析框架**：如「從 CIA 三要素的角度」、「運用 SWOT 分析法」、「依據 NIST 框架」
- **引導特徵**：直接告知使用什麼理論或模型分析
- **禁止特徵**：絕對不能讓學生自選分析框架
- **範例關鍵字**：「從...的角度」、「運用...分析」、「依據...框架」

### 🟡 中等題目（中引導）
- **禁止提及具體分析框架**：不能出現「CIA三要素」、「SWOT」、「NIST」等具體框架名稱
- **引導特徵**：暗示分析方向但讓學生自選框架
- **允許用詞**：「分析...風險」、「評估...影響」、「提出...策略」
- **範例關鍵字**：「分析風險」、「評估影響」、「提出策略」

### 🔴 困難題目（低引導）
- **完全開放**：不提供任何分析框架或具體方向
- **引導特徵**：只描述情境，完全由學生自主決定分析方法
- **用詞特徵**：「制定方案」、「設計策略」、「綜合評估」
- **範例關鍵字**：「制定完整方案」、「設計最佳策略」、「綜合評估並建議」

**重要提醒：**
- 只要題目中出現「從 CIA 三要素的角度」就必須標記為「簡單」
- 只要題目中出現具體分析框架名稱就必須標記為「簡單」
- 中等題目絕對不能包含任何具體分析框架的名稱

**重要：題目與答案分離原則**
- **question 欄位**：只能包含題目描述和問題要求，絕對不能包含答案、分析過程或解決方案
- **answer 欄位**：包含完整的參考答案和分析
- 題目應該以問句結尾，例如：「請分析...」、「試論述...」、「請提出...」

**正確的題目格式範例：**
```
question: "某電商平台近期頻繁遭受惡意攻擊，導致網站服務不穩定。身為資安顧問，請從 CIA 三要素的角度分析該平台可能面臨的資安威脅，並針對每個要素提出具體的防禦措施。"

answer: "1. 機密性威脅與防禦措施：[詳細分析]... 2. 完整性威脅與防禦措施：[詳細分析]... 3. 可用性威脅與防禦措施：[詳細分析]..."
```

**範例申論題類型（按難度分級）：**

**🟢 簡單題目範例（高引導）：**
```
question: "某小型企業的客戶資料遭到外洩。請從 CIA 三要素（機密性、完整性、可用性）的角度，分析此事件的影響，並針對每個要素提出一項改善建議。"
difficulty: "簡單"
guidance_level: "高"
```

**🟡 中等題目範例（中引導）：**
```
question: "某金融機構導入雲端服務後，面臨多重資安挑戰。請分析可能的風險類型，並評估不同防護策略的適用性。"
difficulty: "中等"  
guidance_level: "中"
```

**🔴 困難題目範例（低引導）：**
```
question: "一家跨國企業在數位轉型過程中，需要在效率提升與資安防護間取得平衡。請針對此挑戰，提出一套完整的策略規劃。"
difficulty: "困難"
guidance_level: "低"
```

**❌ 錯誤範例（包含答案內容）：**
```
question: "某電商平台近期頻繁遭受惡意攻擊。從 CIA 三要素分析：1. 機密性威脅：資料外洩、未授權存取... 2. 完整性威脅：資料篡改... 3. 可用性威脅：DDoS攻擊..."
```
此範例錯誤在於：題目內容已經包含了答案的分析過程，違反了題目與答案分離的原則。

```
question: "主要資安風險分析 導入雲端電子病歷系統可能衍生的主要資安風險包括：資料外洩風險：雲端服務供應商（CSP）的安全性不足，導致病患資料遭駭客入侵或內部人員洩漏........。"
```
此範例錯誤在於：這應該是知識點，不是題目。

**✅ 正確的分級範例：**

**🟢 簡單題目（高引導）：**
```
question: "某電商平台近期頻繁遭受惡意攻擊，導致網站服務不穩定，客戶投訴不斷。身為資安顧問，請從 CIA 三要素的角度，分析該平台可能面臨的資安威脅，並針對每個要素提出至少兩項具體的防禦措施。"
difficulty: "簡單"
guidance_level: "高"
```

**🟡 中等題目（中引導）：**
```
question: "某電商平台近期頻繁遭受惡意攻擊，導致網站服務不穩定，客戶投訴不斷。身為資安顧問，請分析該平台面臨的主要資安風險，並提出相應的防護策略建議。"
difficulty: "中等"
guidance_level: "中"
```

**🔴 困難題目（低引導）：**
```
question: "某電商平台近期頻繁遭受惡意攻擊，導致網站服務不穩定，客戶投訴不斷。身為資安顧問，請為該平台制定一套完整的資安改善方案。"
difficulty: "困難"
guidance_level: "低"
```

請現在基於學習資料生成高品質申論題：
"""
        try:
            parsed_json = await self._generate_with_json_parsing(prompt)
            if parsed_json and 'questions' in parsed_json:
                return parsed_json.get("questions", [])
            else:
                print("  ⚠️ 申論題生成失敗，返回空列表")
                return []
        except Exception as e:
            print(f"  ❌ 申論題生成錯誤: {e}")
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
            kp_str = kp_str.strip()
            safe_kp = kp_str.replace('"', "'")
            nodes_text += f'      "{safe_kp}"\n'

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
        另外！！！請一定要輸出Mermaid格式可以接收的文字排版，要注意縮排與標點符號。
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
            # 去除可能的程式碼區塊標記
            if mermaid_code.startswith('```'):
                lines = mermaid_code.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                mermaid_code = '\n'.join(lines).strip()
            if not mermaid_code.startswith("mindmap"):
                return "mindmap\n  root((生成失敗))\n    請檢查輸入內容或 API 連線"
            return mermaid_code
        except Exception as e:
            print(f"生成心智圖時發生錯誤: {e}")
            return "mindmap\n  root((錯誤))\n    無法生成心智圖"

    async def split_exam_paper(self, exam_text: str) -> List[Dict[str, Any]]:
        """自動分割考卷內容為個別題目"""
        prompt = f"""
請分析以下考卷內容，將其精確分割為個別的考題。

考卷內容：
{exam_text[:8000]}

請仔細識別題目分隔標記，包括：
- 一、二、三、四、五、六、七、八、九、十
- 1.、2.、3.、4.、5.、6.、7.、8.、9.、10.
- （一）、（二）、（三）、（四）、（五）
- 第一題、第二題、第三題、第四題
- Q1、Q2、Q3、Q4、Q5

分題規則：
1. 每個題目從編號開始到下個編號之前的所有內容
2. 包含題目描述、分數標記（如25分）
3. 如果有子題或多個段落，全部包含在同一題中
4. 保持原始格式和換行

請以JSON格式回應：
{{
    "questions": [
        {{
            "number": "一",
            "stem": "題目完整內容，包含所有描述和分數標記",
            "type": "ESSAY"
        }},
        {{
            "number": "二",
            "stem": "題目完整內容，包含所有描述和分數標記",
            "type": "ESSAY"
        }},
        {{
            "number": "三",
            "stem": "題目完整內容，包含所有描述和分數標記",
            "type": "ESSAY"
        }},
        {{
            "number": "四",
            "stem": "題目完整內容，包含所有描述和分數標記",
            "type": "ESSAY"
        }}
    ]
}}

注意：
- 使用 "stem" 而不是 "question" 作為題目內容的欄位名
- 確保每題的完整性，從編號開始到下個編號前的所有內容
- 如果分數在括號中（如25分），也要包含
- 保持原文的完整性和格式
"""
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'questions' in parsed_json:
            questions = parsed_json.get("questions", [])
            # 為每個題目添加答案生成
            for question in questions:
                if 'stem' in question:
                    # 為每個分題生成答案
                    answer_data = await self.generate_answer(question['stem'])
                    question['answer'] = answer_data.get('answer', '')
            return questions
        return []
    
    async def split_exam_paper(self, text: str, subject: str) -> List[Dict[str, Any]]:
        """
        自動分析試卷內容，將多個題目分離並逐一處理
        """
        prompt = f"""
你是一位專業的{subject}科老師，請仔細分析以下試卷內容，將其中的主要題目分離出來。

試卷內容：
{text}

請將每個主要題目提取出來，並以JSON格式返回：

{{
    "questions": [
        {{
            "question_number": "題目編號（如：1、2、3或第一題、第二題等）",
            "stem": "完整的題目內容（包括題幹、所有子題、選項等）",
            "type": "題目類型（選擇題、申論題、填充題、複合題等）",
            "estimated_subject": "推測的更細分科目或領域"
        }},
        ...
    ]
}}

重要注意事項：
1. 只分離主要題目，不要將子題拆開成獨立題目
2. 如果一個題目包含多個子題（如第1題有(1)(2)(3)小題），請將整個題目（包括所有子題）作為一個完整單位
3. **關聯題目合併**：如果題目提到「承上題」、「接上題」、「延續上題」、「根據上題」、「基於前題」等字樣，需要將相關聯的兩大題視為同一題，合併處理
4. **連續性題目**：如果某題的解答明顯需要依賴前一題的結果或內容，也應考慮將它們合併為同一題
5. 每個題目都要完整提取，包括題幹、所有子題、所有選項
6. 保留原始的題目編號和結構
7. 如果是選擇題，要包含所有選項 (A)(B)(C)(D)
8. 複合題（有多個小問的題目）應該保持完整，不要拆分

範例：
**一般題目分割：**
如果原題是：
「第1題：
(1) 請說明TCP的三向交握過程
(2) 比較TCP和UDP的差異」

請保持為一個完整題目，不要分成兩個獨立題目。

**關聯題目合併：**
如果原題是：
「第1題：請設計一個資料庫查詢來獲取所有客戶資料...
 第2題：承上題，請針對您設計的查詢進行效能優化分析...」

應該將第1題和第2題合併為同一個完整題目，因為第2題明確提到「承上題」。
"""
        
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'questions' in parsed_json:
            questions = parsed_json.get("questions", [])
            # 為每個分離的題目生成答案
            for question in questions:
                if 'stem' in question:
                    print(f"正在為題目 {question.get('question_number', '未知')} 生成答案...")
                    answer_data = await self.generate_answer(question['stem'])
                    question['answer'] = answer_data.get('answer', '答案生成失敗')
            return questions
        return []
    
    async def analyze_image(self, image_path: str, subject: str = None) -> str:
        """
        分析圖片內容，提取文字和描述
        """
        try:
            import google.generativeai as genai
            from PIL import Image
            
            # 打開圖片
            image = Image.open(image_path)
            
            # 構建提示詞
            if subject:
                prompt = f"""
請仔細分析這張圖片，並提取其中的所有文字內容和重要資訊。
圖片可能包含{subject}領域的題目、圖表、公式或說明文字。

請按以下格式輸出：
1. 如果是題目或考試內容，請完整提取題目文字
2. 如果是圖表或示意圖，請描述圖表內容和重要數據
3. 如果包含公式，請用文字描述公式內容
4. 提取圖片中的所有可見文字

請用繁體中文回應，並盡可能詳細和準確。
"""
            else:
                prompt = """
請仔細分析這張圖片，並提取其中的所有文字內容和重要資訊。
請按以下格式輸出：
1. 圖片中的所有可見文字
2. 圖片內容的描述
3. 如果是題目、公式或圖表，請特別詳細說明

請用繁體中文回應。
"""
            
            # 使用 Gemini Vision 分析圖片
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content([prompt, image])
            
            return response.text if response.text else "無法解析圖片內容"
            
        except Exception as e:
            print(f"圖片分析錯誤: {e}")
            return f"圖片分析失敗: {str(e)}"

    async def format_question_content(self, raw_question) -> str:
        """格式化題目內容，識別並標記程式碼區塊、表格等特殊格式"""
        # 確保輸入是字串類型
        if not isinstance(raw_question, str):
            if hasattr(raw_question, 'get'):
                # 如果是字典，嘗試取得 question 或其他文字欄位
                raw_question = raw_question.get('question', '') or raw_question.get('stem', '') or str(raw_question)
            else:
                raw_question = str(raw_question)
        
        # 如果輸入為空，直接返回
        if not raw_question.strip():
            return raw_question
            
        prompt = f"""
你是一位專業的內容格式化專家。請分析以下題目內容，並將其格式化為更易讀的 Markdown 格式。

**格式化規則：**
1. **程式碼/虛擬碼識別**：如果內容包含程式碼、演算法、虛擬碼，請用程式碼區塊包圍：
   ```pseudocode
   code here
   ```
   或者
   ```
   code here
   ```

2. **虛擬碼特徵識別**：
   - 包含 "begin"、"end"、"for"、"if" 等關鍵字
   - 包含縮排結構
   - 包含變數賦值（如 n←, theIndex←）
   - 包含陣列操作（如 A[i], A[j]）

3. **表格識別**：如果內容包含表格數據，請轉換為 Markdown 表格格式：
   | 欄位1 | 欄位2 | 欄位3 |
   |-------|-------|-------|
   | 數據1 | 數據2 | 數據3 |

4. **數學公式**：將數學公式用反引號包圍，如 `f(x) = x²`

5. **結構化內容**：
   - 使用適當的標題 (##, ###)
   - 使用項目符號或編號列表
   - 保持段落分明
   - 題目的不同部分用適當的分隔

6. **保持原意**：不要改變題目的原始意思，只是改善格式

**原始題目內容：**
```
{raw_question}
```

**請輸出格式化後的 Markdown 內容（直接輸出格式化結果，不要用程式碼區塊包裝）：**
"""
        
        try:
            # 使用特殊的生成配置，不要求 JSON 格式
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            config = genai.types.GenerationConfig(
                temperature=0.1,
                top_p=0.9,
                max_output_tokens=4096
                # 不設定 response_mime_type，讓它返回純文字
            )
            
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=config
            )
            formatted_content = response.text if response.text else raw_question
            
            # 清理可能的格式化問題
            if formatted_content.startswith('```markdown'):
                lines = formatted_content.split('\n')
                if lines[0].strip() == '```markdown':
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                formatted_content = '\n'.join(lines)
            
            # 如果內容被不當地包裝在程式碼區塊中，移除包裝
            if formatted_content.count('```') >= 2 and formatted_content.startswith('```'):
                lines = formatted_content.split('\n')
                if lines[0].startswith('```') and not 'pseudocode' in lines[0] and not any(keyword in lines[0] for keyword in ['python', 'javascript', 'java', 'c++']):
                    lines = lines[1:]
                    if lines and lines[-1].strip() == '```':
                        lines = lines[:-1]
                    formatted_content = '\n'.join(lines)
            
            return formatted_content.strip() if formatted_content.strip() else raw_question
            
        except Exception as e:
            print(f"內容格式化錯誤: {e}")
            return raw_question  # 如果格式化失敗，返回原始內容

    async def clean_and_organize_content(self, content: str) -> str:
        """清理和整理學習資料主文，移除廣告和不相關資訊"""
        
        prompt = f"""
你是一位專業的內容編輯專家。請對以下學習資料進行清理和整理，產生一個乾淨、易讀的主文內容。

**你的任務：**
1. **移除雜訊**：刪除廣告內容、推廣資訊、無關的連結或宣傳文字
2. **保留核心內容**：保留所有教育性和知識性的重要資訊
3. **完善表格格式**：如果原文包含表格資訊，請重新整理為完整、清晰的 Markdown 表格格式
4. **整理排版**：使用適當的 Markdown 格式，包含適當的標題、段落、列表等
5. **圖片處理**：如果原文提到圖片或圖表，請保留相關描述，格式為 `![圖片描述](圖片說明)`
6. **組織結構**：適當分段，使用標題來組織內容層次，確保內容易於閱讀

**特別注意表格處理：**
- 如果原文提到分級、分類、比較等資訊，請務必整理成表格形式
- 表格要有清楚的表頭和內容
- 確保表格格式正確：| 欄位1 | 欄位2 | 欄位3 |

**處理原則：**
- 保留所有學術性、教育性內容
- 移除「點擊這裡」、「立即購買」、「更多資訊請見」、「聯絡我們」等推廣文字
- 移除與主題無關的廣告內容和頁尾資訊
- 保持專業的學習資料風格
- 確保內容結構清晰，易於學習

**原始資料：**
{content}

**請直接輸出整理後的完整 Markdown 格式內容，包含所有重要的表格和結構化資訊：**
"""
        
        try:
            # 使用純文字生成配置，增加輸出長度以容納完整內容
            text_generation_config = genai.types.GenerationConfig(
                temperature=0.1,
                top_p=0.8,
                max_output_tokens=8192
            )
            
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=text_generation_config
            )

            cleaned_content = response.text if response.text else content
            
            # 清理可能的 markdown 代碼塊標記
            if cleaned_content.startswith('```markdown'):
                lines = cleaned_content.split('\n')
                if lines[0].strip() == '```markdown':
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                cleaned_content = '\n'.join(lines)
            
            return cleaned_content.strip() if cleaned_content.strip() else content

        except Exception as e:
            print(f"內容清理錯誤: {e}")
            return content  # 如果清理失敗，返回原始內容

    async def generate_key_points_summary(self, content: str) -> str:
        """生成文章知識摘要，專門用於知識點整理"""
        
        prompt = f"""
你是一位專業的知識摘要專家。請從以下學習資料中提取並整理出重要的知識點摘要。

**你的任務：**
1. **提取核心知識點**：找出文章中最重要的概念、原理和知識
2. **分類整理**：將相關的知識點分組歸類
3. **簡潔表達**：用清晰、簡潔的語言表達每個知識點
4. **結構化呈現**：使用 Markdown 格式，讓摘要易於瀏覽和記憶

**學習資料：**
{content}

**輸出格式要求：**
直接輸出簡潔的 Markdown 格式知識摘要，**不要包含完整的文章內容**，只需要摘要部分：

## 📋 知識重點摘要

### 🔑 核心概念
- 概念1：簡潔的說明
- 概念2：簡潔的說明

### 📊 重要原理
- 原理1：關鍵要點
- 原理2：關鍵要點

### 💡 實務應用
- 應用1：實際運用場景
- 應用2：實際運用場景

### 🎯 記憶要點
- 需要特別記住的關鍵資訊
- 容易混淆的概念澄清

**重要：請只輸出摘要部分，不要重複原始文章內容**
"""
        
        try:
            # 使用純文字生成配置
            text_generation_config = genai.types.GenerationConfig(
                temperature=0.1,
                top_p=0.8,
                max_output_tokens=4096
            )
            
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=text_generation_config
            )

            summary_content = response.text if response.text else ""
            
            # 清理可能的 markdown 代碼塊標記
            if summary_content.startswith('```markdown'):
                lines = summary_content.split('\n')
                if lines[0].strip() == '```markdown':
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                summary_content = '\n'.join(lines)
            
            return summary_content.strip() if summary_content.strip() else "無法生成知識摘要"

        except Exception as e:
            print(f"生成知識摘要錯誤: {e}")
            return f"知識摘要生成失敗：{str(e)}"

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
