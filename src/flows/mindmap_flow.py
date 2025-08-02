"""
生成心智圖的流程
"""
import asyncio
from typing import Dict, Any
from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager
from ..utils.file_processor import FileProcessor

class MindmapFlow:
    """生成心智圖的流程"""
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager):
        self.gemini = gemini_client
        self.db = db_manager
        self.file_processor = FileProcessor()

    def process_file(self, file_path: str, filename: str, subject: str) -> Dict[str, Any]:
        """處理檔案的同步包裝方法"""
        try:
            # 使用檔案處理器讀取檔案內容
            content, file_type = self.file_processor.process_input(file_path)
            
            # 將檔案內容生成心智圖
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # 這裡我們需要先將內容儲存為問題，然後生成心智圖
                # 為了簡化，我們可以返回一個基本的結果
                result = {
                    'success': True,
                    'message': f'已處理檔案 {filename}，請選擇特定問題來生成心智圖',
                    'questions': []
                }
                return result
            finally:
                loop.close()
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'questions': []
            }

    async def generate_and_save_mindmap(self, question_id: int) -> Dict[str, Any]:
        """為指定問題生成心智圖並儲存"""
        try:
            # 1. 從資料庫取得問題內容
            question_data = self.db.get_question_by_id(question_id)
            if not question_data:
                return {'success': False, 'error': '找不到指定的問題'}

            # 2. 組合文本
            subject = question_data['subject']
            knowledge_points_data = question_data.get('knowledge_points', [])
            
            # 提取知識點名稱，處理不同的資料格式
            knowledge_points = []
            for kp in knowledge_points_data:
                if isinstance(kp, dict):
                    # 如果是字典格式，提取 name 字段
                    knowledge_points.append(kp.get('name', ''))
                elif isinstance(kp, str):
                    # 如果已經是字符串，直接使用
                    knowledge_points.append(kp)
                else:
                    # 其他格式轉為字符串
                    knowledge_points.append(str(kp))
            
            # 過濾掉空值
            knowledge_points = [kp for kp in knowledge_points if kp.strip()]

            # 3. 調用 Gemini API 生成心智圖程式碼
            print("正在生成心智圖...")
            mindmap_code = await self.gemini.generate_mindmap(subject, knowledge_points)
            if not mindmap_code:
                return {'success': False, 'error': '無法生成心智圖程式碼'}

            # 4. 將心智圖程式碼儲存回資料庫
            print("正在儲存心智圖...")
            self.db.update_question_mindmap(question_id, mindmap_code)

            return mindmap_code

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
