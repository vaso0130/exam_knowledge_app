"""
處理單一問題的流程
"""
import os
import hashlib
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager
from ..utils.file_processor import FileProcessor

class AnswerFlow:
    """
    處理單一問題的流程
    """
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager):
        self.gemini = gemini_client
        self.db = db_manager
        self.file_processor = FileProcessor()

    @staticmethod
    def _sanitize_question_text(text: str) -> str:
        """移除包含解答或說明標題的行"""
        if not text:
            return text

        import re

        pattern = re.compile(r"^\s*(答案|解答|參考答案|建議|說明|解析)[\s:：]", re.I)
        lines = []
        for line in text.splitlines():
            if pattern.match(line):
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    def process_file(self, file_path: str, filename: str, subject: str) -> Dict[str, Any]:
        """處理檔案的同步包裝方法"""
        try:
            # 使用檔案處理器讀取檔案內容
            content, file_type = self.file_processor.process_input(file_path)
            
            # 將檔案內容當作問題處理
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self.process_question(content, subject, {'source': filename})
                )
                return result
            finally:
                loop.close()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'questions': []
            }

    async def process_question(self, question_text: str, subject: str, additional_info: Dict = None) -> Dict[str, Any]:
        """
        處理單一問題的完整流程
        """
        if additional_info is None:
            additional_info = {}
            
        try:
            # 先清理題目內容可能包含的答案
            question_text = self._sanitize_question_text(question_text)

            # 1. 生成答案
            print("正在生成答案...")
            answer_data = await self.gemini.generate_answer(question_text)
            if not answer_data or 'answer' not in answer_data:
                raise ValueError("無法生成有效的答案")

            # 2. 提取知識點
            print(f"正在從問題中提取 '{subject}' 科的知識點...")
            combined_text = f"題目：{question_text}\n答案：{answer_data['answer']}"
            knowledge_points = await self.gemini.extract_knowledge_points(combined_text, subject)
            if not knowledge_points:
                print("警告：未能從問題中提取到知識點。")
                # 即使沒有知識點，也繼續儲存問題
                knowledge_points = []

            # 3. 儲存資料
            print("正在儲存問題和答案...")
            result = self._store_question_data(
                question_text=question_text,
                answer_text=answer_data['answer'],
                subject=subject,
                knowledge_points=knowledge_points
            )

            # 為問題生成心智圖
            mindmap_code = None
            if knowledge_points:
                try:
                    mindmap_code = await self.gemini.generate_mindmap(subject, knowledge_points)
                    if mindmap_code:
                        self.db.update_question_mindmap(result['question_id'], mindmap_code)
                except Exception as e:
                    print(f"生成心智圖失敗: {e}")

            return {
                'success': True,
                'type': 'question',
                'question_id': result['question_id'],
                'data': {
                    'answer': answer_data['answer'],
                    'sources': answer_data.get('sources', []),
                    'knowledge_points': knowledge_points,
                    'mindmap': mindmap_code
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'type': 'question'
            }

    def _store_question_data(self, question_text: str, answer_text: str, subject: str, knowledge_points: List[str]) -> Dict[str, Any]:
        """
        儲存單一問題及其關聯的知識點
        """
        
        # 建立一個虛擬文件來關聯這個獨立的問題
        doc_title = f"獨立問題-{question_text[:20]}..."
        doc_id = self.db.add_document(
            title=doc_title,
            content=question_text,
            subject=subject,
            tags="獨立問題",
            file_path=""
        )

        # 儲存問題
        question_id = self.db.add_question(
            document_id=doc_id,
            question_text=question_text,
            answer_text=answer_text,
            subject=subject
        )

        # 新增或取得知識點並建立關聯
        for kp_name in knowledge_points:
            kp_id = self.db.add_or_get_knowledge_point(name=kp_name, subject=subject)
            self.db.link_question_to_knowledge_point(question_id, kp_id)

        return {'question_id': question_id}
