import google.generativeai as genai
import asyncio
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import os
from asyncio_throttle import Throttler
from ..utils.json_parser import extract_json_from_text

class GeminiClient:
    def __init__(self, api_key: str = None):
        load_dotenv()
        self.api_key = api_key or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("請設定 GEMINI_API_KEY 或 GOOGLE_API_KEY 環境變數")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.throttler = Throttler(rate_limit=10, period=60)  # 每分鐘最多10次請求
        
        # 生成配置
        self.generation_config = genai.types.GenerationConfig(
            temperature=0.2,
            top_p=0.9,
            max_output_tokens=8192,
            response_mime_type="application/json"  # 要求 JSON 格式輸出
        )
    
    async def _generate_with_json_parsing(self, prompt: str) -> Optional[Dict[str, Any]]:
        """異步生成並解析 JSON 回應"""
        raw_response = await self.generate_async(prompt)
        if not raw_response:
            return None
        
        parsed_json = extract_json_from_text(raw_response)
        return parsed_json

    async def generate_async(self, prompt: str) -> str:
        """異步生成回應"""
        async with self.throttler:
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
請為以下內容提供一個簡潔的摘要句子，以及3-7個重點項目。

內容：
{text[:4000]}

請以JSON格式回應：
{{
    "summary": "一句話摘要",
    "bullets": ["重點1", "重點2", "重點3", ...]
}}
"""
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'summary' in parsed_json and 'bullets' in parsed_json:
            return parsed_json
        return {"summary": "無法生成摘要", "bullets": []}
    
    async def generate_questions(self, bullets: List[str]) -> List[Dict[str, Any]]:
        """依據重點生成模擬申論題"""
        prompt = f"""
基於以下重點內容，請生成3-5題模擬申論題。所有題目都應該是需要深入分析、論述的申論題型。

重點內容：
{chr(10).join(f'- {bullet}' for bullet in bullets)}

申論題要求：
1. 題目需要學生進行深入分析、比較、評述或論證
2. 答案應該包含多個要點，需要條理清晰的論述
3. 如果適合，可以要求學生用表格方式整理比較
4. 題目應具有開放性，允許多角度思考

請以JSON格式回應：
{{
    "questions": [
        {{
            "stem": "申論題目內容（要求深入分析或論述）",
            "answer": "詳細的參考答案（如果適合用表格，請使用 Markdown 表格格式）",
            "type": "Essay",
            "points": "評分要點或考查重點"
        }},
        ...
    ]
}}

範例申論題類型：
- 請分析並比較...的優缺點，並論述其適用場景
- 請論述...的重要性，並舉例說明其在實際應用中的體現
- 請評述...的發展趨勢，並分析其對...的影響
"""
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'questions' in parsed_json:
            return parsed_json.get("questions", [])
        return []
    
    async def parse_exam_paper(self, text: str) -> Dict[str, Any]:
        """
        解析考卷內容，自動分割題目並識別考科
        """
        prompt = f"""
請分析以下文本內容，這可能是一份考卷或包含多個題目的學習資料。

任務：
1. 自動識別考科類別（從：資料結構、資訊管理、資通網路與資訊安全、資料庫應用、或其他）
2. 判斷內容類型（考卷題目 or 學習資料）
3. 如果是考卷，請將每個題目分割開來（注意：一個題目可能包含多個小問題，這些應該視為同一題）
4. 如果是學習資料，請提取核心知識點

**重要：題目分割原則**
- 一個題目可能包含多個部分（如：問題描述 + 程式碼 + 多個小問題）
- 只有明確的題號分隔（如「第一題」、「1.」、「題目二」）才分割
- 同一題目內的不同部分（如「(10分)」、「請分析」、「請說明」）應合併為一題
- 程式碼和相關問題應該保持在同一題中

文本內容：
{text}

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
            "knowledge_points": ["相關知識點1", "相關知識點2"]
        }}
    ]
}}

分析指引：
- 如果看到明確的題號（「第一題」、「1.」、「(1)」、「題目一」），才進行題目分割
- 同一題目內的程式碼、圖表、多個小問題都應該包含在同一個 "stem" 中
- 考科判斷依據：關鍵字、專業術語、內容領域
- 每個題目都要完整提取，不要遺漏任何部分

範例：
如果文本包含：「請分析以下演算法...（程式碼）...請說明演算法名稱（10分）...請列出處理過程（10分）」
這應該視為**一個完整題目**，包含程式碼和兩個小問題。
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
            # 考卷題目：直接轉換為問題格式
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
        根據完整文本內容生成模擬題，並為每個問題自動標註知識點標籤
        這個方法專門用於處理整篇文章，並為每個生成的問題提供詳細的知識點標籤
        """
        prompt = f"""
        你是一位專業的出題老師，你的任務是從提供的文本中，生成結構化的申論題或問答題。

        **任務說明：**
        1.  **分析文本**：仔細閱讀以下內容，理解其核心概念。
        2.  **設計題目**：根據文本，設計 1 到 5 道申論題或問答題。
        3.  **產生簡短標題**：為每一道題目，產生一個簡潔有力的標題（5-10個字），總結題目的核心。
        4.  **提供詳解**：為每道題目提供詳細的參考答案。
        5.  **標註知識點**：為每道題目標註相關的知識點（2-4個）。
        6.  **格式化輸出**：將所有內容以單一的JSON格式輸出。

        **文本內容：**
        ```
        {text}
        ```

        **輸出要求：**
        -   必須是嚴格的JSON格式。
        -   JSON物件應包含一個鍵 `questions`。
        -   `questions` 的值應該是一個物件列表，每個物件代表一題。
        -   每個題目物件應包含四個鍵：`title` (字串), `question` (字串), `answer` (字串), `knowledge_points` (字串陣列)。

        **範例：**
        ```json
        {{
            "questions": [
                {{
                    "title": "TCP/IP 四層模型",
                    "question": "請說明 TCP/IP 模型的四層結構，並簡述每一層的主要功能。",
                    "answer": "TCP/IP 模型分為四層：1. 應用層 (Application Layer)：處理特定應用程式的協定，如 HTTP、FTP。2. 傳輸層 (Transport Layer)：提供端對端的數據傳輸服務，如 TCP、UDP。3. 網路層 (Internet Layer)：負責數據包的路由與轉發，主要協定是 IP。4. 網路介面層 (Network Interface Layer)：處理與物理網路的介面，如乙太網路。",
                    "knowledge_points": ["TCP/IP 模型", "網路協定", "網路層次架構"]
                }},
                {{
                    "title": "OSI 七層模型比較",
                    "question": "OSI 七層模型與 TCP/IP 四層模型有何對應關係？請簡要比較其異同。",
                    "answer": "OSI 的應用層、表現層、會議層對應到 TCP/IP 的應用層。OSI 的傳輸層對應到 TCP/IP 的傳輸層。OSI 的網路層對應到 TCP/IP 的網路層。OSI 的資料連結層與實體層對應到 TCP/IP 的網路介面層。主要差異在於 OSI 是一個理論模型，而 TCP/IP 是實際應用的標準。",
                    "knowledge_points": ["OSI 模型", "TCP/IP 模型", "網路協定標準", "模型比較"]
                }}
            ]
        }}
        ```

        請現在分析給定的文本並返回JSON結果。
        """
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'questions' in parsed_json:
            return parsed_json.get("questions", [])
        return []
    
    async def generate_mindmap(self, subject: str, knowledge_points: List[str]) -> str:
        """
        根據輸入的文本，生成 Mermaid.js 格式的心智圖 Markdown。
        """
        # 將知識點列表轉換為 Mermaid 節點
        nodes_text = ""
        for kp in knowledge_points:
            # 確保知識點不含破壞格式的字元，並加上引號
            safe_kp = kp.replace('"', "'")
            nodes_text += f'      "{safe_kp}"\n'

        prompt = f"""
        請根據以下核心主題和關鍵知識點，生成一個 Mermaid.js 格式的心智圖。
        心智圖應該以核心主題為根節點，並將每個知識點作為其主要分支。
        請確保輸出的格式是純粹的 Mermaid Markdown，以 `mindmap` 開頭。
        重要：節點的文字已用雙引號包起來，請直接使用。

        核心主題：{subject}
        
        知識點：
{', '.join(knowledge_points)}

        Mermaid 心智圖範例格式：
        mindmap
          root(("{subject}"))
{nodes_text}
        
        請直接輸出 Mermaid 代碼，不要包含任何額外的解釋或 ```mermaid ... ``` 標記。
        """
        # 對於心智圖，我們期望純文字輸出，而不是 JSON
        async with self.throttler:
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
3. 每個題目都要完整提取，包括題幹、所有子題、所有選項
4. 保留原始的題目編號和結構
5. 如果是選擇題，要包含所有選項 (A)(B)(C)(D)
6. 複合題（有多個小問的題目）應該保持完整，不要拆分

範例：
如果原題是：
「第1題：
(1) 請說明TCP的三向交握過程
(2) 比較TCP和UDP的差異」

請保持為一個完整題目，不要分成兩個獨立題目。
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
            
            async with self.throttler:
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

    async def generate_key_points_summary(self, content: str) -> str:
        """生成重點摘要"""
        
        prompt = f"""
你是一位專業的學習內容分析師。請針對以下學習資料，產生一份簡潔而全面的重點摘要。

**任務要求：**
1. 提取文章的核心概念和重要知識點
2. 用條列式或段落形式整理重點
3. 重點應該涵蓋主要概念、重要細節、關鍵結論
4. 語言簡潔明瞭，適合快速複習
5. 保持學術性和準確性

**學習資料：**
{content}

**請以清晰的格式輸出重點摘要：**
"""
        
        try:
            response = await self.generate_async(prompt)
            return response.strip() if response else ""
        except Exception as e:
            print(f"生成重點摘要錯誤: {e}")
            return ""

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
