import asyncio
import hashlib
from datetime import datetime
from typing import Dict, Any, List
import os

from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager
from ..utils.file_processor import FileProcessor, ContentValidator
from .content_flow import ContentProcessor

class InfoFlow:
    """學習資料處理流程"""
    
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager, content_processor: ContentProcessor):
        self.gemini = gemini_client
        self.db = db_manager
        self.data_dir = "./data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.content_processor = content_processor
    
    async def process_learning_material(self, raw_text: str, subject: str, source: str) -> Dict[str, Any]:
        """處理學習資料的完整流程"""
        try:
            # 清理文字
            cleaned_text = ContentValidator.clean_text(raw_text)
            
            # 1. Summarizer - 摘要全文
            print("正在生成摘要...")
            summary_data = await self.gemini.generate_summary(cleaned_text)
            
            # 2. Tagger - 生成標籤
            print("正在生成標籤...")
            tags = await self.gemini.generate_tags(cleaned_text, subject)
            
            # 3. QAGenerator - 生成模擬題
            print("正在生成模擬題...")
            questions = await self.gemini.generate_questions(
                summary_data.get('bullets', [])
            )
            
            # 4. StorageAgent - 儲存資料
            print("正在儲存資料...")
            result = await self._store_info_data(
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                summary_data=summary_data,
                subject=subject,
                tags=tags,
                questions=questions,
                source=source
            )
            
            # 5. Process content for knowledge points
            print("正在處理內容以提取知識點...")
            doc_id = result['document_id']
            doc_title = os.path.basename(result['file_path'])
            
            # 使用 ContentProcessor 處理文本
            processing_result = await self.content_processor.process_content(
                text=cleaned_text,
                subject=subject,
                doc_title=doc_title,
                doc_id=doc_id
            )

            if not processing_result.get('success'):
                 print(f"警告：無法處理內容以提取知識點：{processing_result.get('error')}")


            return {
                'success': True,
                'type': 'info',
                'subject': subject,
                'document_id': result['document_id'],
                'question_ids': result['question_ids'],
                'file_path': result['file_path'],
                'data': {
                    'summary': summary_data.get('summary', ''),
                    'bullets': summary_data.get('bullets', []),
                    'tags': tags,
                    'questions': questions,
                    'knowledge_points': processing_result.get('knowledge_points', [])
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'type': 'info'
            }
    
    async def _store_info_data(self, raw_text: str, cleaned_text: str,
                              summary_data: Dict[str, Any], subject: str,
                              tags: List[str], questions: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
        """儲存學習資料"""
        
        # 生成唯一檔案名稱
        content_hash = hashlib.md5(cleaned_text.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{content_hash}.md"
        
        # 建立科目目錄
        subject_dir = os.path.join(self.data_dir, subject)
        os.makedirs(subject_dir, exist_ok=True)
        
        file_path = os.path.join(subject_dir, filename)
        
        # 生成 Markdown 內容
        markdown_content = self._generate_info_markdown(
            original_text=cleaned_text,
            summary=summary_data.get('summary', ''),
            bullets=summary_data.get('bullets', []),
            tags=tags,
            questions=questions,
            subject=subject,
            source=source
        )
        
        # 寫入檔案
        FileProcessor.save_markdown(markdown_content, file_path)
        
        # 儲存到資料庫
        doc_id = self.db.add_document(
            title=filename,
            content=cleaned_text,
            subject=subject,
            tags=",".join(tags),
            file_path=file_path,
            source=source
        )
        
        question_ids = []
        for q in questions:
            q_id = self.db.add_question(
                document_id=doc_id,
                question_text=q['stem'],
                answer_text=q['answer'],
                subject=subject
            )
            question_ids.append(q_id)
            
        return {
            'document_id': doc_id,
            'question_ids': question_ids,
            'file_path': file_path
        }
        
    def _generate_info_markdown(self, original_text: str, summary: str, bullets: List[str],
                                tags: List[str], questions: List[Dict[str, Any]], subject: str, source: str) -> str:
        """生成學習資料的 Markdown 格式內容"""
        
        md_content = f"# {subject} 學習筆記\n\n"
        md_content += f"**來源:** {source}\n"
        md_content += f"**標籤:** {', '.join(tags)}\n\n"
        
        md_content += "## 摘要\n"
        md_content += f"{summary}\n\n"
        
        md_content += "## 重點整理\n"
        for bullet in bullets:
            md_content += f"- {bullet}\n"
        md_content += "\n"
        
        md_content += "## 模擬試題\n"
        for i, q in enumerate(questions, 1):
            md_content += f"**題目 {i}:** {q['stem']}\n\n"
            md_content += f"**答案:**\n{q['answer']}\n\n"
            
        md_content += "---\n\n"
        md_content += "## 原始文本\n"
        md_content += original_text
        
        return md_content
