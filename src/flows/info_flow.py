import asyncio
import hashlib
from datetime import datetime
from typing import Dict, Any, List
import os

from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager
from ..utils.file_processor import FileProcessor, ContentValidator
from .content_flow import ContentFlow

class InfoFlow:
    """學習資料處理流程"""
    
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager, content_processor: ContentFlow):
        self.gemini = gemini_client
        self.db = db_manager
        self.data_dir = "./data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.content_processor = content_processor
        self.file_processor = FileProcessor()
    
    def process_file(self, file_path: str, filename: str, subject: str) -> Dict[str, Any]:
        """處理檔案的同步包裝方法"""
        try:
            # 使用檔案處理器讀取檔案內容
            content, file_type = self.file_processor.process_input(file_path)
            
            # 呼叫非同步處理方法
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self.process_learning_material(content, subject, filename)
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
            
            # 🆕 4. 新增：生成重點摘要與快速測驗選擇題
            print("正在生成重點摘要與快速測驗...")
            key_points_summary = await self.gemini.generate_key_points_summary(cleaned_text)
            quick_quiz = await self.gemini.generate_quick_quiz(cleaned_text, subject)
            
            # 5. StorageAgent - 儲存資料
            print("正在儲存資料...")
            result = await self._store_info_data(
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                summary_data=summary_data,
                subject=subject,
                tags=tags,
                questions=questions,
                source=source,
                key_points_summary=key_points_summary,  # 🆕 新增參數
                quick_quiz=quick_quiz  # 🆕 新增參數
            )
            
            # 6. Process content for knowledge points
            print("正在處理內容以提取知識點...")
            doc_id = result['document_id']
            doc_title = os.path.basename(result['file_path'])
            
            # 移除對 content_processor 的調用，因為學習資料不應該被當作考題來解析
            # processing_result = await self.content_processor.process_content(
            #     text=cleaned_text,
            #     subject=subject,
            #     doc_title=doc_title,
            #     doc_id=doc_id
            # )
            # if not processing_result.get('success'):
            #      print(f"警告：無法處理內容以提取知識點：{processing_result.get('error')}")

            # 直接使用 Tagger 生成的標籤作為知識點
            knowledge_points = tags

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
                    'knowledge_points': knowledge_points,
                    'key_points_summary': key_points_summary,
                    'quick_quiz': quick_quiz
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
                              tags: List[str], questions: List[Dict[str, Any]], source: str,
                              key_points_summary: str = "", quick_quiz: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """儲存學習資料"""
        
        if quick_quiz is None:
            quick_quiz = []
        
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
            source=source,
            key_points_summary=key_points_summary,  # 🆕 新增參數
            quick_quiz=quick_quiz  # 🆕 新增參數
        )
        
        # 寫入檔案
        FileProcessor.save_markdown(markdown_content, file_path)
        
        # 儲存到資料庫 - 增加資料型態檢查與轉換
        import json
        
        # 確保 key_points_summary 是字串格式，防止 'dict' object has no attribute 'replace' 錯誤
        if isinstance(key_points_summary, dict):
            print("警告：key_points_summary 是字典格式，正在轉換為文字...")
            key_points_summary = json.dumps(key_points_summary, ensure_ascii=False, indent=2)
        elif key_points_summary is None:
            key_points_summary = ""
        else:
            key_points_summary = str(key_points_summary)  # 確保是字串
        
        # 處理 quick_quiz 的 JSON 序列化
        if isinstance(quick_quiz, list) and quick_quiz:
            quick_quiz_json = json.dumps(quick_quiz, ensure_ascii=False)
        else:
            quick_quiz_json = None
        
        doc_id = self.db.add_document(
            title=filename,
            content=cleaned_text,
            subject=subject,
            tags=",".join(tags),
            file_path=file_path,
            source=source,
            key_points_summary=key_points_summary,
            quick_quiz=quick_quiz_json
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
                                tags: List[str], questions: List[Dict[str, Any]], subject: str, source: str,
                                key_points_summary: str = "", quick_quiz: List[Dict[str, Any]] = None) -> str:
        """生成學習資料的 Markdown 格式內容"""
        
        if quick_quiz is None:
            quick_quiz = []
        
        md_content = f"# {subject} 學習筆記\n\n"
        md_content += f"**來源:** {source}\n"
        md_content += f"**標籤:** {', '.join(tags)}\n\n"
        
        # 🆕 新增：原始全文區域
        md_content += "## 📄 原始文本\n"
        md_content += f"{original_text}\n\n"
        md_content += "---\n\n"
        
        # 🆕 新增：重點摘要區域
        if key_points_summary:
            md_content += "## ⭐ 重點摘要\n"
            md_content += f"{key_points_summary}\n\n"
            md_content += "---\n\n"
        
        # 🆕 新增：快速測驗區域
        if quick_quiz:
            md_content += "## 🎯 快速測驗\n"
            md_content += "*快速檢驗您對重點知識的掌握程度*\n\n"
            for i, q in enumerate(quick_quiz, 1):
                md_content += f"**{i}. {q.get('question', '')}**\n\n"
                
                # 處理選擇題選項
                if q.get('type') == 'multiple_choice' and q.get('options'):
                    for opt in q['options']:
                        md_content += f"   {opt}\n"
                    md_content += f"\n   **正解：{q.get('correct_answer', '')}**\n"
                    if q.get('explanation'):
                        md_content += f"   **解析：{q.get('explanation', '')}**\n"
                elif q.get('type') == 'true_false':
                    md_content += f"   **正解：{'是' if q.get('correct_answer') else '否'}**\n"
                    if q.get('explanation'):
                        md_content += f"   **解析：{q.get('explanation', '')}**\n"
                else:
                    md_content += f"   **答案：{q.get('correct_answer', '')}**\n"
                    if q.get('explanation'):
                        md_content += f"   **解析：{q.get('explanation', '')}**\n"
                md_content += "\n"
            md_content += "---\n\n"
        
        # 原有的摘要區域（保持向後相容）
        md_content += "## 📋 學習摘要\n"
        md_content += f"{summary}\n\n"
        
        md_content += "## 📝 重點整理\n"
        for bullet in bullets:
            md_content += f"- {bullet}\n"
        md_content += "\n"
        
        # 原有的模擬試題區域（保持向後相容）
        md_content += "## 📚 模擬試題\n"
        md_content += "*深度理解與應用練習*\n\n"
        for i, q in enumerate(questions, 1):
            md_content += f"**題目 {i}:** {q['stem']}\n\n"
            md_content += f"**答案:**\n{q['answer']}\n\n"
        
        return md_content
