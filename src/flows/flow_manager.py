from typing import Any, List, Dict

from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager
from .answer_flow import AnswerFlow
from .mindmap_flow import MindmapFlow
from .content_flow import ContentFlow

class FlowManager:
    """
    統一管理所有核心業務流程。
    這個類別被 GUI 用來觸發各種後端操作。
    """
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager):
        """
        初始化所有流程控制器。
        """
        self.gemini_client = gemini_client
        self.db_manager = db_manager
        
        # 1. 先初始化沒有外部流程依賴的類別
        self.content_processor = ContentFlow(gemini_client, db_manager)
        self.answer_flow = AnswerFlow(gemini_client, db_manager)
        self.mindmap_flow = MindmapFlow(gemini_client, db_manager)
        
        # 2. 為了向後相容，建立別名
        self.content_flow = self.content_processor

    async def process_learning_material(self, raw_text: str, subject: str, source: str) -> Dict[str, Any]:
        """
        處理學習材料（通常是較長的文本或文件內容）。
        """
        return await self.info_flow.process_learning_material(raw_text, subject, source)

    async def process_single_question(self, question_text: str, subject: str, additional_info: dict = None) -> Dict[str, Any]:
        """
        處理使用者輸入的單一問題。
        """
        return await self.answer_flow.process_question(question_text, subject, additional_info or {})

    async def generate_mindmap_for_question(self, question_id: int) -> Dict[str, Any]:
        """
        為指定的問題 ID 生成心智圖。
        """
        return await self.mindmap_flow.generate_and_save_mindmap(question_id)

    async def process_text_content(self, text: str, subject: str, doc_title: str, doc_id: int) -> Dict[str, Any]:
        """
        處理一段給定的文本，提取知識點並生成問題。
        """
        return await self.content_processor.process_content(text, subject, doc_title, doc_id)

    async def detect_if_question(self, text: str) -> bool:
        """
        判斷輸入的文字是否為一個問題。
        """
        return await self.gemini_client.detect_type(text)

    async def generate_quiz_from_knowledge(self, knowledge_content: list, quiz_type: str = 'multiple_choice', num_questions: int = 5) -> Dict[str, Any]:
        """
        根據知識點內容生成測驗題目
        
        Args:
            knowledge_content: 知識點內容列表
            quiz_type: 測驗類型 ('multiple_choice', 'true_false', 'fill_blank')
            num_questions: 題目數量
            
        Returns:
            包含測驗題目的字典
        """
        try:
            # 整理知識點內容為提示文字
            content_summary = []
            for kp in knowledge_content:
                content_summary.append(f"知識點：{kp['name']}")
                if kp.get('description'):
                    content_summary.append(f"說明：{kp['description']}")
                
                # 加入相關題目作為參考
                if kp.get('related_questions'):
                    content_summary.append("相關題目範例：")
                    for i, q in enumerate(kp['related_questions'][:2]):  # 只取前兩個作為範例
                        if len(q) > 3:
                            content_summary.append(f"- {q[3][:100]}...")  # 假設題目內容在索引3
                content_summary.append("---")
            
            content_text = "\n".join(content_summary)
            
            # 根據測驗類型設定提示
            if quiz_type == 'multiple_choice':
                quiz_prompt = f"""
基於以下知識點內容，生成 {num_questions} 道選擇題。每道題目應該：
1. 測試對核心概念的理解，而非記憶細節
2. 避免涉及具體的公司名稱、產品名稱或時事
3. 專注於知識點本身的原理和應用
4. 提供4個選項，其中只有1個正確答案
5. 包含詳細的解析說明

知識點內容：
{content_text}

請以JSON格式回應，結構如下：
{{
    "quiz_type": "multiple_choice",
    "questions": [
        {{
            "id": 1,
            "question": "題目內容",
            "options": ["A. 選項1", "B. 選項2", "C. 選項3", "D. 選項4"],
            "correct_answer": "A",
            "explanation": "詳細解析"
        }}
    ]
}}
"""
            elif quiz_type == 'true_false':
                quiz_prompt = f"""
基於以下知識點內容，生成 {num_questions} 道是非題。每道題目應該：
1. 測試對核心概念的理解
2. 陳述應該清晰明確
3. 避免模糊或有爭議的表述
4. 包含詳細的解析說明

知識點內容：
{content_text}

請以JSON格式回應，結構如下：
{{
    "quiz_type": "true_false",
    "questions": [
        {{
            "id": 1,
            "question": "陳述內容",
            "correct_answer": true,
            "explanation": "詳細解析"
        }}
    ]
}}
"""
            else:  # fill_blank
                quiz_prompt = f"""
基於以下知識點內容，生成 {num_questions} 道填空題。每道題目應該：
1. 測試關鍵概念和術語
2. 空格應該是重要的知識點
3. 提供適當的上下文
4. 包含詳細的解析說明

知識點內容：
{content_text}

請以JSON格式回應，結構如下：
{{
    "quiz_type": "fill_blank",
    "questions": [
        {{
            "id": 1,
            "question": "題目內容，其中 _____ 代表需要填入的答案",
            "correct_answer": "正確答案",
            "explanation": "詳細解析"
        }}
    ]
}}
"""
            
            # 使用 Gemini 生成測驗
            response = await self.gemini_client._generate_with_json_parsing(quiz_prompt)
            
            # 解析回應
            import json
            try:
                quiz_data = json.loads(response)
                return quiz_data
            except json.JSONDecodeError:
                # 如果JSON解析失敗，嘗試提取JSON部分
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    quiz_data = json.loads(json_match.group())
                    return quiz_data
                else:
                    raise ValueError("無法解析AI回應為JSON格式")
                    
        except Exception as e:
            return {
                "error": f"生成測驗時發生錯誤: {str(e)}",
                "quiz_type": quiz_type,
                "questions": []
            }
