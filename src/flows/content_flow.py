from typing import Dict, Any
import asyncio
import concurrent.futures
from src.core.gemini_client import GeminiClient
from src.core.database import DatabaseManager
import json
from ..utils.markdown_utils import (
    format_code_blocks,
    format_summary_to_markdown,
    format_answer_text,
    detect_and_fence_indented_code,
)
from ..flows.mindmap_flow import MindmapFlow

class ContentFlow:
    """內容處理流程管理器 - 統一管理所有內容分析、問題生成和知識點關聯"""
    
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager):
        self.gemini = gemini_client
        self.db = db_manager
        from ..utils.file_processor import FileProcessor
        self.file_processor = FileProcessor()
        self.mindmap_flow = MindmapFlow(gemini_client, db_manager)

    @staticmethod
    def _sanitize_question_text(text: str) -> str:
        """移除可能包含解答或說明標題的行，但保留程式碼區塊內的內容"""
        if not text:
            return text
        import re
        pattern = re.compile(r"^\s*(答案|解答|參考答案|建議|說明|解析)[\s:：]", re.I)
        lines = text.splitlines()
        sanitized_lines = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                sanitized_lines.append(line)
            elif in_code_block:
                sanitized_lines.append(line)
            elif not pattern.match(line):
                sanitized_lines.append(line)

        cleaned = "\n".join(sanitized_lines).strip()
        return detect_and_fence_indented_code(cleaned)

    
    
    def process_file(self, file_path: str, filename: str, suggested_subject: str = None) -> Dict[str, Any]:
        """處理檔案的統一入口點"""
        try:
            # content is the extracted text from the file
            content, _ = self.file_processor.process_input(file_path)

            # ======================================================================
            # ▼▼▼ DEBUG CHECKPOINT 1: 檢查 FileProcessor 的輸出 ▼▼▼
            print("\n" + "="*20 + " DEBUG CHECKPOINT 1: AFTER FileProcessor " + "="*20)
            print("--- Raw content extracted from file ---")
            print(content)
            print("="*67 + "\n")
            # ▲▲▲ DEBUG CHECKPOINT 1 ▲▲▲
            # ======================================================================

            # Pass the file_path along with the extracted content
            return self.complete_ai_processing(content, filename, suggested_subject, file_path=file_path)
        except Exception as e:
            print(f"處理檔案時發生錯誤: {e}")
            return {'success': False, 'error': str(e), 'message': f'檔案處理失敗: {str(e)}'}
    
    def complete_ai_processing(self, content: str, filename: str, suggested_subject: str = None, source_url: str = None, file_path: str = None) -> Dict[str, Any]:
        """完整 AI 處理流程"""
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._run_async_processing(content, filename, suggested_subject, source_url, file_path))
                return future.result()
        except Exception as e:
            print(f"完整 AI 處理時發生錯誤: {e}")
            return {'success': False, 'error': str(e), 'message': '處理失敗，請稍後再試'}
    
    def _extract_answer_string(self, answer_data: Any) -> str:
        """Recursively extracts the answer string from potentially nested answer_data."""
        if isinstance(answer_data, dict):
            if 'answer' in answer_data:
                extracted_answer = self._extract_answer_string(answer_data['answer'])
                if not extracted_answer or "not included in the prompt" in extracted_answer.lower() or "answer is not provided" in extracted_answer.lower():
                    return "（參考答案生成失敗或未提供，請檢查原始資料或稍後重試。）"
                return extracted_answer
            else:
                return json.dumps(answer_data, ensure_ascii=False)
        elif isinstance(answer_data, list):
            return json.dumps(answer_data, ensure_ascii=False)
        else:
            extracted_answer = str(answer_data)
            if not extracted_answer or "not included in the prompt" in extracted_answer.lower() or "answer is not provided" in extracted_answer.lower():
                return "（參考答案生成失敗或未提供，請檢查原始資料或稍後重試。）"
            return extracted_answer

    async def _run_async_processing(self, content: str, filename: str, suggested_subject: str = None, source_url: str = None, file_path: str = None) -> Dict[str, Any]:
        """執行異步處理流程"""
        try:
            print("🤖 AI 正在分析內容類型...")
            parsed_data = await self.gemini.parse_exam_paper(content)

            # # ======================================================================
            # # ▼▼▼ DEBUG CHECKPOINT 2 (已修正) ▼▼▼
            # print("\n" + "="*20 + " DEBUG CHECKPOINT 2: AFTER parse_exam_paper " + "="*20)
            # print("--- Full parsed_data from AI ---")
            # print(json.dumps(parsed_data, indent=2, ensure_ascii=False))
            # # 修正：迭代 questions 列表來印出每個 stem
            # if parsed_data.get('questions'):
            #     for i, q_data in enumerate(parsed_data['questions']):
            #         stem_text = q_data.get('stem', 'STEM NOT FOUND')
            #         print(f"\n--- Extracted 'stem' from Question {i+1} ---")
            #         print(stem_text)
            # print("="*70 + "\n")
            # # ▲▲▲ DEBUG CHECKPOINT 2 (已修正) ▲▲▲
            # # ======================================================================
            
            content_type = parsed_data.get('content_type', 'study_material')
            detected_subject = parsed_data.get('subject', suggested_subject or '其他')
            
            print(f"📋 內容分類結果：{content_type} ({detected_subject})")
            
            doc_id = self.db.add_document(
                title=filename, 
                content=content, # Extracted text
                subject=detected_subject, 
                source=source_url,
                file_path=file_path # The actual file path
            )
            
            if content_type == 'exam_paper':
                print("📝 檢測到考題內容，執行考題處理流程...")
                result = await self._process_exam_content(content, detected_subject, doc_id, parsed_data)
            else:
                print("📚 檢測到學習資料，執行學習資料處理流程...")
                result = await self._process_study_material(content, detected_subject, doc_id, parsed_data)
            
            if result.get('success'):
                return result
            else:
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
                    # 步驟 1: 直接使用 AI 產生的、已完美格式化的題目 (stem)
                    question_text = question_data.get('stem', '')
                    
                    if not question_text:
                        continue

                    # 步驟 2: 讓 AI 針對這個完美的題目生成格式完美的答案
                    answer_data = await self.gemini.generate_answer(question_text)
                    answer_text = format_answer_text(self._extract_answer_string(answer_data)) # format_answer_text 是安全的
                    sources_json = json.dumps(answer_data.get('sources', []), ensure_ascii=False)
                    
                    # 步驟 3: 將完美格式的題目和答案直接存入資料庫，移除所有 format_code_blocks()
                    question_id = self.db.insert_question(
                        document_id=doc_id,
                        title=question_data.get('title', f'題目 {i}'),
                        question_text=question_text,        # <--- 已修正
                        answer_text=answer_text,            # <--- 已修正
                        answer_sources=sources_json,
                        subject=subject,
                        difficulty=question_data.get('difficulty'),
                        guidance_level=question_data.get('guidance_level')
                    )
                    
                    await self.mindmap_flow.generate_and_save_mindmap(question_id)
                    
                    knowledge_points = question_data.get('knowledge_points', [])
                    for kp_name in knowledge_points:
                        kp_id = self.db.add_or_get_knowledge_point(kp_name.strip(), subject)
                        self.db.link_question_to_knowledge_point(question_id, kp_id)
                        all_knowledge_points.add(kp_name.strip())
                    
                    saved_questions.append({
                        'id': question_id,
                        'stem': question_text,
                        'answer': answer_text,
                        'sources': answer_data.get('sources', []),
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
        
        # 步驟 1: AI 生成一組包含題目和答案的模擬題
        generated_questions = await self.gemini.generate_questions_from_text(content, subject)
        saved_questions = []
        all_knowledge_points = set()

        for q_data in generated_questions:
            # 步驟 2: 使用 sanitize 清理題目文字
            q_text = self._sanitize_question_text(q_data.get('question', ''))

            # 對於模擬題，我們使用 generate_answer 重新生成答案，確保答案品質
            answer_data = await self.gemini.generate_answer(q_text)
            answer_text = format_answer_text(self._extract_answer_string(answer_data))
            sources_json = json.dumps(answer_data.get('sources', []), ensure_ascii=False)

            # 步驟 3: 將完美格式的內容直接存入資料庫
            question_id = self.db.insert_question(
                document_id=doc_id,
                title=q_data.get('title', '模擬題'),
                question_text=q_text,               # <--- 已修正
                answer_text=answer_text,            # <--- 已修正
                answer_sources=sources_json,
                subject=subject,
                difficulty=q_data.get('difficulty'),
            )
            
            # 步驟 4: 處理知識點關聯 (新增)
            knowledge_points = q_data.get('knowledge_points', [])
            if knowledge_points:
                print(f"🔗 為題目 {question_id} 關聯知識點: {knowledge_points}")
                for kp_name in knowledge_points:
                    # 新增或取得知識點
                    kp_id = self.db.add_or_get_knowledge_point(
                        name=kp_name.strip(),
                        subject=subject,
                        description=f"來自學習資料：{parsed_data.get('title', '未知文件')}"
                    )
                    # 關聯題目與知識點
                    self.db.link_question_to_knowledge_point(question_id, kp_id)
                    all_knowledge_points.add(kp_name.strip())
            else:
                print(f"⚠️ 題目 {question_id} 沒有生成知識點")
            
            # 生成心智圖
            mindmap_result = await self.mindmap_flow.generate_and_save_mindmap(question_id)
            
            # 將心智圖程式碼儲存到 mindmap_code 欄位
            if mindmap_result and mindmap_result.get('success'):
                self.db.update_question_mindmap(question_id, mindmap_result.get('mindmap_code', ''))
            
            # 生成解題技巧 (新增)
            try:
                print(f"🧠 為題目 {question_id} 生成解題技巧...")
                summary_result = await self.gemini.generate_question_summary(q_text, q_data.get('title', ''))
                if summary_result and 'summary' in summary_result and 'solving_tips' in summary_result:
                    self.db.update_question_solving_tips(
                        question_id,
                        summary_result['summary'],
                        summary_result['solving_tips']
                    )
                    print(f"✅ 解題技巧已生成並儲存")
                else:
                    print(f"⚠️ 解題技巧生成失敗")
            except Exception as e:
                print(f"❌ 生成解題技巧時發生錯誤: {e}")

            q_data['id'] = question_id
            q_data['question'] = q_text
            q_data['answer'] = answer_text
            saved_questions.append(q_data)

        # 生成摘要和測驗
        summary_raw_data = await self.gemini.generate_summary(content)
        # 確保 summary_data 是字典，如果不是則嘗試解析
        if isinstance(summary_raw_data, str):
            try:
                summary_data = json.loads(summary_raw_data)
            except json.JSONDecodeError:
                summary_data = {} # 解析失敗則設為空字典
        else:
            summary_data = summary_raw_data

        quiz_data = await self.gemini.generate_quick_quiz(content, subject)

        # 儲存摘要和測驗
        summary_text = format_summary_to_markdown(summary_data) if summary_data else None
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