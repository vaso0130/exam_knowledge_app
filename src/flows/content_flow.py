from typing import Dict, Any, List
from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager

class ContentProcessor:
    """處理單一文本內容，提取資訊並儲存"""
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager):
        self.gemini = gemini_client
        self.db = db_manager

    async def process_content(self, text: str, subject: str, doc_title: str, doc_id: int) -> Dict[str, Any]:
        """
        處理單一文本內容，提取知識點、生成問題並儲存。
        """
        try:
            # 1. 提取知識點
            print(f"正在從文本中提取 '{subject}' 科的知識點...")
            knowledge_points = await self.gemini.extract_knowledge_points(text, subject)
            if not knowledge_points:
                print("未能提取到知識點，流程中止。")
                return {'success': False, 'error': '未能提取到知識點'}

            # 2. 生成模擬題
            print("正在根據文本生成模擬題...")
            # Assuming generate_questions_from_text exists in GeminiClient
            generated_questions = await self.gemini.generate_questions_from_text(text, subject)
            if not generated_questions:
                print("未能生成模擬題，流程中止。")
                return {'success': False, 'error': '未能生成模擬_T'}

            # 3. 儲存資料
            print("正在儲存問題與知識點關聯...")
            saved_data = await self._store_question_and_knowledge_data(
                document_id=doc_id,
                subject=subject,
                questions=generated_questions,
                knowledge_points=knowledge_points
            )

            return {
                'success': True,
                'type': 'question_batch',
                'document_id': doc_id,
                'question_ids': saved_data['question_ids'],
                'knowledge_points': knowledge_points,
                'data': {
                    'questions': generated_questions
                }
            }

        except Exception as e:
            print(f"處理內容時發生錯誤: {e}")
            return {'success': False, 'error': str(e)}

    async def _store_question_and_knowledge_data(self, document_id: int, subject: str,
                                                 questions: List[Dict[str, Any]],
                                                 knowledge_points: List[str]) -> Dict[str, Any]:
        """
        儲存問題、知識點，並建立兩者之間的關聯。
        """
        # 1. 新增或取得所有知識點的 ID
        knowledge_point_ids = []
        for kp_name in knowledge_points:
            kp_id = self.db.add_or_get_knowledge_point(name=kp_name, subject=subject)
            knowledge_point_ids.append(kp_id)

        # 2. 儲存所有問題
        question_ids = []
        for q in questions:
            question_id = self.db.add_question(
                document_id=document_id,
                question_text=q['question'],
                answer_text=q['answer'],
                subject=subject,
                mindmap_code="" # 初始為空
            )
            question_ids.append(question_id)

            # 3. 建立每個問題與所有知識點的關聯
            for kp_id in knowledge_point_ids:
                self.db.link_question_to_knowledge_point(question_id, kp_id)
        
        return {
            "question_ids": question_ids,
            "knowledge_point_ids": knowledge_point_ids
        }
