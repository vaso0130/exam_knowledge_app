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
        第二步實施：AI 能力升級 - 自動識別與關聯
        """
        try:
            # 1. 整體提取知識點（用於文檔級別的分類）
            print(f"正在從文本中提取 '{subject}' 科的整體知識點...")
            document_knowledge_points = await self.gemini.extract_knowledge_points(text, subject)
            if not document_knowledge_points:
                print("未能提取到文檔知識點，但仍繼續處理...")

            # 2. 生成模擬題（帶有個別的知識點標籤）
            print("正在根據文本生成模擬題，並為每題自動標註知識點...")
            generated_questions = await self.gemini.generate_questions_from_text(text, subject)
            if not generated_questions:
                print("AI未生成模擬題，但流程繼續...")
                generated_questions = []  # 設為空列表而不是中止流程

            # 3. 儲存資料並建立知識點關聯
            print("正在儲存問題與知識點關聯...")
            saved_data = await self._store_question_and_knowledge_data(
                document_id=doc_id,
                subject=subject,
                questions=generated_questions,
                document_knowledge_points=document_knowledge_points or []
            )

            return {
                'success': True,
                'type': 'question_batch',
                'document_id': doc_id,
                'question_ids': saved_data['question_ids'],
                'knowledge_points': saved_data['all_knowledge_points'],
                'data': {
                    'questions': generated_questions
                }
            }

        except Exception as e:
            print(f"處理內容時發生錯誤: {e}")
            return {'success': False, 'error': str(e)}

    async def _store_question_and_knowledge_data(self, document_id: int, subject: str,
                                                 questions: List[Dict[str, Any]],
                                                 document_knowledge_points: List[str]) -> Dict[str, Any]:
        """
        儲存問題、知識點，並建立兩者之間的關聯。
        第二步升級：每個問題都有自己的知識點標籤
        """
        all_knowledge_points = set(document_knowledge_points)  # 收集所有知識點
        question_ids = []
        
        # 處理每個問題
        for q in questions:
            # 儲存問題
            question_id = self.db.add_question(
                document_id=document_id,
                question_text=q['stem'],
                answer_text=q['answer'],
                subject=subject
            )
            question_ids.append(question_id)
            
            # 處理這個問題的個別知識點標籤
            question_knowledge_points = q.get('knowledge_points', [])
            question_tags = q.get('tags', [])
            
            # 合併知識點和標籤（標籤也視為知識點的一種）
            combined_points = question_knowledge_points + question_tags
            all_knowledge_points.update(combined_points)
            
            # 為每個問題建立知識點關聯
            for kp_name in combined_points:
                if kp_name.strip():  # 確保不是空字串
                    # 新增或取得知識點 ID
                    kp_id = self.db.add_or_get_knowledge_point(name=kp_name.strip(), subject=subject)
                    # 建立問題與知識點的關聯
                    self.db.link_question_to_knowledge_point(question_id, kp_id)
            
            print(f"問題 {question_id} 已關聯到 {len(combined_points)} 個知識點")
        
        # 也為文檔級別的知識點建立關聯（如果有的話）
        for doc_kp in document_knowledge_points:
            if doc_kp.strip():
                kp_id = self.db.add_or_get_knowledge_point(name=doc_kp.strip(), subject=subject)
                # 將文檔知識點與所有問題關聯
                for q_id in question_ids:
                    self.db.link_question_to_knowledge_point(q_id, kp_id)
        
        return {
            "question_ids": question_ids,
            "all_knowledge_points": list(all_knowledge_points)
        }
