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
        """生成標準答案，支援表格格式"""
        prompt = f"""
請為以下考試題目提供標準答案。如果答案適合用表格呈現（如比較、分類、統計等），請使用 Markdown 表格格式。

題目：
{question_text}

請分析題目內容，如果適合用表格呈現，請在答案中包含適當的表格，並在表格後提供詳細論述說明。

表格格式要求：
- 使用標準 Markdown 表格語法
- 表格要有清楚的標題行
- 內容要對齊整齊
- 表格後要有詳細的文字說明

請以JSON格式回應，包含以下欄位：
{{
    "answer": "詳細的標準答案（如果適合，請包含 Markdown 表格）",
    "sources": ["來源1", "來源2", "來源3"],
    "has_table": true/false,
    "table_description": "表格的用途說明（如果有表格的話）"
}}

範例表格格式：
| 項目 | 特點 | 適用場景 |
|------|------|----------|
| 選項A | 特點1 | 場景1 |
| 選項B | 特點2 | 場景2 |

請確保答案內容完整、準確，並適當運用表格來提升資訊的清晰度。
"""
        parsed_json = await self._generate_with_json_parsing(prompt)
        if parsed_json and 'answer' in parsed_json and 'sources' in parsed_json:
            return parsed_json
        return {"answer": "無法解析答案", "sources": [], "has_table": False, "table_description": ""}
    
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
    
    async def generate_tags(self, text: str, subject: str) -> List[str]:
        """生成標籤"""
        prompt = f"""
基於以下{subject}領域的內容，請生成3-6個相關的標籤關鍵字。

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
