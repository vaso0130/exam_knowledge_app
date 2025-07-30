"""
流程管理器
"""
from typing import Dict, Any

from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager
from .info_flow import InfoFlow
from .answer_flow import AnswerFlow
from .mindmap_flow import MindmapFlow
from .content_flow import ContentProcessor

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
        self.content_processor = ContentProcessor(gemini_client, db_manager)
        self.answer_flow = AnswerFlow(gemini_client, db_manager)
        self.mindmap_flow = MindmapFlow(gemini_client, db_manager)
        
        # 2. 初始化依賴其他流程的類別 (InfoFlow 依賴 ContentProcessor)
        self.info_flow = InfoFlow(gemini_client, db_manager, self.content_processor)

    async def process_learning_material(self, raw_text: str, subject: str, source: str) -> Dict[str, Any]:
        """
        處理學習材料（通常是較長的文本或文件內容）。
        """
        return await self.info_flow.process_learning_material(raw_text, subject, source)

    async def process_single_question(self, question_text: str, subject: str, additional_info: Dict = None) -> Dict[str, Any]:
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
