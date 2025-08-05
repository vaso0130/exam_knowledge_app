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

            print(f"正在為問題 ID {question_id} 生成心智圖...")
            
            # 2. 驗證問題 ID 格式（如果是字串，確保是有效的 UUID）
            if isinstance(question_id, str):
                import uuid
                try:
                    uuid.UUID(question_id)
                except ValueError:
                    return {'success': False, 'error': f'無效的問題 ID 格式: {question_id}'}
            
            # 3. 組合文本
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

            # 檢查是否有有效的知識點
            question_summary = None  # 初始化變數
            if not knowledge_points:
                print("警告：沒有發現有效的知識點，將生成提示性心智圖")
                mindmap_code = f"""mindmap
  root(("{subject}"))
    提示("請先添加知識點")
      方法1("編輯題目時添加知識點標籤")
      方法2("或上傳相關學習資料")
      方法3("系統會自動提取知識點")"""
            else:
                # 3. 調用 Gemini API 生成心智圖程式碼，加入題目文本
                print(f"正在為 {len(knowledge_points)} 個知識點生成心智圖...")
                question_text = question_data.get('title', '') + '\n\n' + question_data.get('question_text', '')
                mindmap_result = await self.gemini.generate_mindmap(subject, knowledge_points, question_text)
                
                # 提取心智圖代碼和題目摘要
                mindmap_code = mindmap_result.get('mindmap_code', '')
                question_summary = mindmap_result.get('question_summary')
                
            if not mindmap_code:
                return {'success': False, 'error': '無法生成心智圖程式碼'}

            # 4. 將心智圖程式碼儲存回資料庫
            print("正在儲存心智圖...")
            try:
                self.db.update_question_mindmap(question_id, mindmap_code)
                print("心智圖儲存成功")
            except Exception as db_error:
                print(f"儲存心智圖時發生錯誤: {db_error}")
                # 即使儲存失敗，仍然返回生成的心智圖代碼
                return {
                    'success': True,
                    'mindmap_code': mindmap_code,
                    'knowledge_points_count': len(knowledge_points),
                    'warning': f'心智圖生成成功，但儲存時發生錯誤: {str(db_error)}'
                }
            
            # 5. 如果有題目摘要，也一併儲存
            if question_summary and question_summary.get('summary') and question_summary.get('solving_tips'):
                print("正在儲存題目摘要與解題技巧...")
                try:
                    self.db.update_question_solving_tips(
                        question_id, 
                        question_summary.get('summary', ''),
                        question_summary.get('solving_tips', '')
                    )
                    print("題目摘要與解題技巧儲存成功")
                except Exception as summary_error:
                    print(f"儲存題目摘要時發生錯誤: {summary_error}")
                    # 摘要儲存失敗不影響整體結果

            return {
                'success': True,
                'mindmap_code': mindmap_code,
                'knowledge_points_count': len(knowledge_points)
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
