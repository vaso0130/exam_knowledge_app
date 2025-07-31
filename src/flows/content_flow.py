from typing import Dict, Any, List
import asyncio
import concurrent.futures
from src.core.gemini_client import GeminiClient
from src.core.database import DatabaseManager
import json

class ContentFlow:
    """內容處理流程管理器 - 統一管理所有內容分析、問題生成和知識點關聯"""
    
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager):
        self.gemini = gemini_client
        self.db = db_manager
        from ..utils.file_processor import FileProcessor
        self.file_processor = FileProcessor()

    @staticmethod
    def _sanitize_question_text(text: str) -> str:
        """移除可能包含解答或說明標題的行"""
        if not text:
            return text
        import re
        pattern = re.compile(r"^\s*(答案|解答|參考答案|建議|說明|解析)[\s:：]", re.I)
        lines = [line for line in text.splitlines() if not pattern.match(line)]
        return "\n".join(lines).strip()

    @staticmethod
    def _convert_markdown_to_html_with_code_blocks(md_text: str) -> str:
        """
        Converts Markdown text to HTML, specifically handling fenced code blocks
        to include Prism.js compatible classes.
        """
        return markdown.markdown(md_text, extensions=['fenced_code', 'nl2br', 'tables'])
    
    def process_file(self, file_path: str, filename: str, suggested_subject: str = None) -> Dict[str, Any]:
        """處理檔案的統一入口點"""
        try:
            content, _ = self.file_processor.process_input(file_path)
            return self.complete_ai_processing(content, filename, suggested_subject)
        except Exception as e:
            print(f"處理檔案時發生錯誤: {e}")
            return {'success': False, 'error': str(e), 'message': f'檔案處理失敗: {str(e)}'}
    
    def complete_ai_processing(self, content: str, filename: str, suggested_subject: str = None, source_url: str = None) -> Dict[str, Any]:
        """完整 AI 處理流程"""
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._run_async_processing(content, filename, suggested_subject, source_url))
                return future.result()
        except Exception as e:
            print(f"完整 AI 處理時發生錯誤: {e}")
            return {'success': False, 'error': str(e), 'message': '處理失敗，請稍後再試'}
    
    def _extract_answer_string(self, answer_data: Any) -> str:
        """Recursively extracts the answer string from potentially nested answer_data."""
        if isinstance(answer_data, dict):
            if 'answer' in answer_data:
                return self._extract_answer_string(answer_data['answer'])
            else:
                return json.dumps(answer_data, ensure_ascii=False)
        elif isinstance(answer_data, list):
            return json.dumps(answer_data, ensure_ascii=False)
        else:
            return str(answer_data)

    async def _run_async_processing(self, content: str, filename: str, suggested_subject: str = None, source_url: str = None) -> Dict[str, Any]:
        """執行異步處理流程"""
        try:
            print("🤖 AI 正在分析內容類型...")
            parsed_data = await self.gemini.parse_exam_paper(content)
            
            content_type = parsed_data.get('content_type', 'study_material')
            detected_subject = parsed_data.get('subject', suggested_subject or '其他')
            
            print(f"📋 內容分類結果：{content_type} ({detected_subject})")
            
            doc_id = self.db.add_document(
                title=filename, 
                content=content, 
                subject=detected_subject, 
                original_content=content,
                source=source_url
            )
            
            if content_type == 'exam_paper':
                print("📝 檢測到考題內容，執行考題處理流程...")
                result = await self._process_exam_content(content, detected_subject, doc_id, parsed_data)
            else:
                print("📚 檢測到學習資料，執行學習資料處理流程...")
                result = await self._process_study_material(content, detected_subject, doc_id, parsed_data)
            
            if result.get('success'):
                print("🗺️ 正在生成心智圖...")
                all_kps = result.get('knowledge_points', [])
                if all_kps:
                    mindmap_data = await self.gemini.generate_mindmap(detected_subject, all_kps)
                    if mindmap_data:
                        self.db.update_document_mindmap(doc_id, mindmap_data)
                        print(f"✅ 心智圖已成功生成並儲存至文檔 {doc_id}")
                        result['mindmap'] = mindmap_data
            
            return result
                
        except Exception as e:
            print(f"異步處理時發生錯誤: {e}")
            raise e
    
    async def _process_exam_content(self, content: str, subject: str, doc_id: int, parsed_data: Dict) -> Dict[str, Any]:
        """考題處理流程"""
        questions = parsed_data.get('questions', [])
        saved_questions = []
        all_knowledge_points = set()
        
        print(f"📝 開始處理 {len(questions)} 道考題...")
        
        for i, question_data in enumerate(questions, 1):
            try:
                question_text = self._sanitize_question_text(question_data.get('stem', ''))
                if not question_text:
                    continue

                # 直接使用純淨的題幹生成答案
                answer_data = await self.gemini.generate_answer(question_text)
                print(f"DEBUG: answer_data type: {type(answer_data)}, value: {answer_data}")
                answer_text = self._extract_answer_string(answer_data)
                print(f"DEBUG: answer_text type: {type(answer_text)}, value: {answer_text}")
                
                question_id = self.db.insert_question(
                    document_id=doc_id,
                    title=question_data.get('title', f'題目 {i}'),
                    question_text=question_text,
                    answer_text=answer_text,
                    subject=subject,
                    difficulty=question_data.get('difficulty'),
                    guidance_level=question_data.get('guidance_level')
                )
                print(f"DEBUG: Difficulty: {question_data.get('difficulty')}, Guidance Level: {question_data.get('guidance_level')}")
                
                knowledge_points = question_data.get('knowledge_points', [])
                for kp_name in knowledge_points:
                    kp_id = self.db.add_knowledge_point(kp_name.strip(), subject)
                    self.db.link_question_to_knowledge_point(question_id, kp_id)
                    all_knowledge_points.add(kp_name.strip())
                
                saved_questions.append({
                    'id': question_id,
                    'stem': question_text,
                    'answer': answer_text,
                    'knowledge_points': knowledge_points
                })
            except Exception as e:
                print(f"    處理第 {i} 題時發生錯誤: {e}")
                continue
        
        return {
            'success': True,
            'content_type': 'exam_paper',
            'subject': subject,
            'document_id': doc_id,
            'questions': saved_questions,
            'knowledge_points': list(all_knowledge_points),
            'message': f'成功處理考題，解析了 {len(saved_questions)} 道題目。'
        }

    async def _process_study_material(self, content: str, subject: str, doc_id: int, parsed_data: Dict) -> Dict[str, Any]:
        """學習資料處理流程"""
        print("📚 執行學習資料處理流程...")
        
        # 生成模擬題
        generated_questions = await self.gemini.generate_questions_from_text(content, subject)
        saved_questions = []
        all_knowledge_points = set()

        for q_data in generated_questions:
            question_id = self.db.insert_question(
                document_id=doc_id,
                title=q_data.get('title', '模擬題'),
                question_text=q_data.get('question', ''),
                answer_text=self._extract_answer_string(q_data.get('answer', '')),
                subject=subject,
                difficulty=q_data.get('difficulty'),
            )
            saved_questions.append({'id': question_id, **q_data})
            
            for kp_name in q_data.get('knowledge_points', []):
                kp_id = self.db.add_knowledge_point(kp_name.strip(), subject)
                self.db.link_question_to_knowledge_point(question_id, kp_id)
                all_knowledge_points.add(kp_name.strip())

        # 生成摘要和測驗
        summary_data = await self.gemini.generate_summary(content)
        quiz_data = await self.gemini.generate_quick_quiz(content, subject)

        # 儲存摘要和測驗
        summary_text = json.dumps(summary_data, ensure_ascii=False) if summary_data else None
        quiz_text = json.dumps(quiz_data, ensure_ascii=False) if quiz_data else None
        self.db.update_document_summary_and_quiz(doc_id, summary_text, quiz_text)

        return {
            'success': True,
            'content_type': 'study_material',
            'subject': subject,
            'document_id': doc_id,
            'questions': saved_questions,
            'knowledge_points': list(all_knowledge_points),
            'summary': summary_data,
            'quiz': quiz_data,
            'message': f'學習資料處理完成！生成了 {len(saved_questions)} 道模擬題。'
        }