"""
生成心智圖的流程
"""
from typing import Dict, Any
from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager

class MindmapFlow:
    """生成心智圖的流程"""
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager):
        self.gemini = gemini_client
        self.db = db_manager

    async def generate_and_save_mindmap(self, question_id: int) -> Dict[str, Any]:
        """為指定問題生成心智圖並儲存"""
        try:
            # 1. 從資料庫取得問題內容
            question_data = self.db.get_question_by_id(question_id)
            if not question_data:
                return {'success': False, 'error': '找不到指定的問題'}

            # 2. 組合文本
            text_for_mindmap = f"主題: {question_data['subject']}\n"
            text_for_mindmap += f"問題: {question_data['question_text']}\n"
            text_for_mindmap += f"答案: {question_data['answer_text']}\n"
            
            # 加入知識點
            if question_data.get('knowledge_points'):
                kps = ", ".join([kp['name'] for kp in question_data['knowledge_points']])
                text_for_mindmap += f"核心知識點: {kps}\n"

            # 3. 調用 Gemini API 生成心智圖程式碼
            print("正在生成心智圖...")
            mindmap_code = await self.gemini.generate_mindmap(text_for_mindmap)
            if not mindmap_code:
                return {'success': False, 'error': '無法生成心智圖程式碼'}

            # 4. 將心智圖程式碼儲存回資料庫
            print("正在儲存心智圖...")
            self.db.update_question_mindmap(question_id, mindmap_code)

            return {
                'success': True,
                'question_id': question_id,
                'mindmap_code': mindmap_code
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
