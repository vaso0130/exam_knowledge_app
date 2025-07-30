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
    
    async def generate_mindmap(self, text: str) -> str:
        """
        根據輸入的文本，生成 Mermaid.js 格式的心智圖 Markdown。
        """
        prompt = f"""
        請根據以下文本內容，生成一個 Mermaid.js 格式的心智圖。
        心智圖應該圍繞核心主題展開，並包含3到5個主要分支，每個分支下有2到4個子節點。
        請確保輸出的格式是純粹的 Mermaid Markdown，以 `mindmap` 開頭。
        重要：如果節點的文字包含特殊字元（如括號、斜線等），請務必用雙引號將文字包起來，例如 `"節點(文字)"`。

        文本內容：
        {text[:3000]}

        Mermaid 心智圖範例格式：
        mindmap
          root(("核心主題"))
            "主要分支 1"
              "子節點 1.1"
              "子節點 1.2"
            "主要分支 2 (含特殊字元)"
              "子節點 2.1"
              "子節點 2.2"
        
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
