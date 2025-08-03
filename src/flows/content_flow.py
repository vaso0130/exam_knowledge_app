from typing import Dict, Any
import asyncio
import concurrent.futures
from src.core.gemini_client import GeminiClient
from src.core.database import DatabaseManager
import json
from ..utils.markdown_utils import (
    format_summary_to_markdown,
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

    async def _process_single_question_concurrently(self, question_data: Dict, doc_id: int, subject: str, question_index: int, is_generated_question: bool = False) -> Dict:
        """
        [新函式] 並行處理單一問題的核心邏輯。
        這個函式會被 asyncio.gather 呼叫。
        
        Args:
            question_data: 問題資料
            doc_id: 文件ID
            subject: 科目
            question_index: 問題索引
            is_generated_question: 是否為生成的模擬題
        """
        try:
            # 從傳入的資料獲取題幹
            if is_generated_question:
                # 對於模擬題，使用 question 欄位
                question_text = self._sanitize_question_text(question_data.get('question', ''))
            else:
                # 對於考題，使用 stem 欄位
                question_text = question_data.get('stem') or question_data.get('question')
            
            if not question_text:
                return {'success': False, 'error': '題幹為空'}

            print(f"    🔄 開始並行處理第 {question_index} 題...")

            # 1. 生成答案 (I/O 密集型)
            answer_data = await self.gemini.generate_answer(question_text)
            answer_text = self._extract_answer_string(answer_data)  # 直接使用 AI 回傳的答案，不做二次加工
            sources_json = json.dumps(answer_data.get('sources', []), ensure_ascii=False)

            # 2. 存入資料庫 (I/O 密集型)
            question_id = self.db.insert_question(
                document_id=doc_id,
                title=question_data.get('title', f'題目 {question_index}'),
                question_text=question_text,
                answer_text=answer_text,
                answer_sources=sources_json,
                subject=subject,
                difficulty=question_data.get('difficulty'),
                guidance_level=question_data.get('guidance_level')
            )

            # 3. 處理知識點 (CPU/I/O 混合)
            knowledge_points = question_data.get('knowledge_points', [])
            if knowledge_points:
                print(f"    🔗 為題目 {question_id} 關聯 {len(knowledge_points)} 個知識點")
                for kp_name in knowledge_points:
                    kp_id = self.db.add_or_get_knowledge_point(
                        name=kp_name.strip(),
                        subject=subject,
                        description=f"來自{'模擬題' if is_generated_question else '考題'}生成"
                    )
                    self.db.link_question_to_knowledge_point(question_id, kp_id)

            # 4. 生成心智圖 (I/O 密集型)
            mindmap_result = await self.mindmap_flow.generate_and_save_mindmap(question_id)
            if mindmap_result and mindmap_result.get('success'):
                self.db.update_question_mindmap(question_id, mindmap_result.get('mindmap_code', ''))

            # 5. 生成解題技巧 (僅限模擬題，I/O 密集型)
            if is_generated_question:
                try:
                    summary_result = await self.gemini.generate_question_summary(question_text, question_data.get('title', ''))
                    if summary_result and 'summary' in summary_result and 'solving_tips' in summary_result:
                        self.db.update_question_solving_tips(
                            question_id,
                            summary_result['summary'],
                            summary_result['solving_tips']
                        )
                        print(f"    ✅ 題目 {question_id} 解題技巧已生成")
                except Exception as e:
                    print(f"    ⚠️ 題目 {question_id} 解題技巧生成失敗: {e}")

            print(f"    ✅ 第 {question_index} 題處理完成 (ID: {question_id})")

            # 6. 回傳結構化處理結果
            return {
                'success': True,
                'id': question_id,
                'stem': question_text,
                'answer': answer_text,
                'sources': answer_data.get('sources', []),
                'knowledge_points': knowledge_points
            }
        except Exception as e:
            print(f"    ❌ 處理第 {question_index} 題時並行發生錯誤: {e}")
            return {'success': False, 'error': str(e), 'stem': question_data.get('stem', 'N/A')}

    
    
    def process_file(self, file_path: str, filename: str, suggested_subject: str = None, 
                    uploader_id: int = None, uploader_name: str = None) -> Dict[str, Any]:
        """處理檔案的統一入口點"""
        try:
            # content is the extracted text from the file
            content, _ = self.file_processor.process_input(file_path)

            # Pass the file_path along with the extracted content
            return self.complete_ai_processing(
                content, filename, suggested_subject, 
                file_path=file_path,
                uploader_id=uploader_id,
                uploader_name=uploader_name
            )
        except Exception as e:
            print(f"處理檔案時發生錯誤: {e}")
            return {'success': False, 'error': str(e), 'message': f'檔案處理失敗: {str(e)}'}
    
    def complete_ai_processing(self, content: str, filename: str, suggested_subject: str = None, 
                              source_url: str = None, file_path: str = None,
                              uploader_id: int = None, uploader_name: str = None) -> Dict[str, Any]:
        """完整 AI 處理流程"""
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._run_async_processing(
                    content, filename, suggested_subject, source_url, file_path,
                    uploader_id, uploader_name
                ))
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

    async def _run_async_processing(self, content: str, filename: str, suggested_subject: str = None, 
                                   source_url: str = None, file_path: str = None,
                                   uploader_id: int = None, uploader_name: str = None) -> Dict[str, Any]:
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
                file_path=file_path, # The actual file path
                uploader_id=uploader_id,
                uploader_name=uploader_name
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
        """考題處理流程 (已升級為並行處理)"""
        questions_from_ai = parsed_data.get('questions', [])
        print(f"📝 檢測到 {len(questions_from_ai)} 道考題，開始並行處理...")

        # 1. 建立所有問題的處理任務列表
        tasks = []
        for i, question_data in enumerate(questions_from_ai, 1):
            task = self._process_single_question_concurrently(
                question_data=question_data,
                doc_id=doc_id,
                subject=subject,
                question_index=i,
                is_generated_question=False  # 這是考題，不是模擬題
            )
            tasks.append(task)

        # 2. 使用 asyncio.gather 一次性執行所有任務
        print(f"🚀 開始並行處理 {len(tasks)} 個考題任務...")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 3. 收集處理結果
        saved_questions = []
        all_knowledge_points = set()
        failed_count = 0
        
        for result in results:
            if isinstance(result, Exception):
                print(f"一個任務執行時發生嚴重錯誤: {result}")
                failed_count += 1
            elif result.get('success'):
                saved_questions.append(result)
                for kp in result.get('knowledge_points', []):
                    all_knowledge_points.add(kp.strip())
            else:
                print(f"一個任務處理失敗: {result.get('error')}")
                failed_count += 1

        message = f'成功處理考題，共 {len(saved_questions)} 道成功，{failed_count} 道失敗。'
        print(f"📊 {message}")
        
        return {
            'success': True,
            'content_type': 'exam_paper',
            'subject': subject,
            'document_id': doc_id,
            'questions': saved_questions,
            'knowledge_points': list(all_knowledge_points),
            'message': message
        }

    async def _process_study_material(self, content: str, subject: str, doc_id: int, parsed_data: Dict) -> Dict[str, Any]:
        """學習資料處理流程 (模擬題部分已升級為並行處理)"""
        print("📚 執行學習資料處理流程...")
        
        # 步驟 1: AI 生成一組包含題目和答案的模擬題
        generated_questions = await self.gemini.generate_questions_from_text(content, subject)
        print(f"🤖 AI 已生成 {len(generated_questions)} 道模擬題，開始並行處理...")

        # 2. 建立所有模擬題的處理任務列表
        tasks = []
        for i, q_data in enumerate(generated_questions, 1):
            task = self._process_single_question_concurrently(
                question_data=q_data,
                doc_id=doc_id,
                subject=subject,
                question_index=i,
                is_generated_question=True  # 這是模擬題
            )
            tasks.append(task)

        # 3. 使用 asyncio.gather 一次性執行所有任務
        print(f"� 開始並行處理 {len(tasks)} 個模擬題任務...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 4. 收集處理結果
        saved_questions = []
        all_knowledge_points = set()
        failed_count = 0

        for result in results:
            if isinstance(result, Exception):
                print(f"一個模擬題任務執行時發生嚴重錯誤: {result}")
                failed_count += 1
            elif result.get('success'):
                # 轉換格式以符合原來的期望
                saved_questions.append({
                    'id': result['id'],
                    'question': result['stem'],
                    'answer': result['answer'],
                    'knowledge_points': result['knowledge_points']
                })
                for kp in result.get('knowledge_points', []):
                    all_knowledge_points.add(kp.strip())
            else:
                print(f"一個模擬題任務處理失敗: {result.get('error')}")
                failed_count += 1
        
        print(f"📊 模擬題並行處理完成：{len(saved_questions)} 道成功，{failed_count} 道失敗")

        # 5. 後續的摘要和測驗處理保持不變，因為這些不是重複性任務
        print("📄 開始生成摘要...")
        summary_raw_data = await self.gemini.generate_summary(content)
        # 確保 summary_data 是字典，如果不是則嘗試解析
        if isinstance(summary_raw_data, str):
            try:
                summary_data = json.loads(summary_raw_data)
            except json.JSONDecodeError:
                summary_data = {} # 解析失敗則設為空字典
        else:
            summary_data = summary_raw_data

        print("🧩 開始生成快速測驗...")
        quiz_data = await self.gemini.generate_quick_quiz(content, subject)

        # 儲存摘要和測驗
        # 新版本：AI 已經直接返回 Markdown 格式，不需要再次格式化
        if summary_data and isinstance(summary_data, dict):
            if 'summary' in summary_data and isinstance(summary_data['summary'], str):
                # 檢查是否為新格式（已經是 Markdown）
                summary_content = summary_data['summary']
                if summary_content.strip().startswith("#") or "##" in summary_content:
                    # 新格式：直接使用 AI 生成的 Markdown
                    summary_text = summary_content
                    
                    # 檢查是否需要添加 bullets（如果 AI 沒有包含的話）
                    if ('bullets' in summary_data and 
                        isinstance(summary_data['bullets'], list) and 
                        summary_data['bullets']):
                        
                        # 檢查是否已經包含 bullets 內容
                        bullets_exist = any(bullet in summary_text for bullet in summary_data['bullets'][:2])
                        if not bullets_exist:
                            summary_text += "\n\n## 條列式重點\n\n"
                            for bullet in summary_data['bullets']:
                                summary_text += f"- {bullet}\n"
                else:
                    # 舊格式：使用格式化函數
                    summary_text = format_summary_to_markdown(summary_data)
            else:
                # 舊格式：使用格式化函數
                summary_text = format_summary_to_markdown(summary_data)
        else:
            summary_text = None
        quiz_text = json.dumps(quiz_data, ensure_ascii=False) if quiz_data else None
        self.db.update_document_summary_and_quiz(doc_id, summary_text, quiz_text)

        message = f'學習資料處理完成！生成了 {len(saved_questions)} 道模擬題 ({failed_count} 道失敗)。'
        print(f"🎉 {message}")

        return {
            'success': True,
            'content_type': 'study_material',
            'subject': subject,
            'document_id': doc_id,
            'questions': saved_questions,
            'knowledge_points': list(all_knowledge_points),
            'summary': summary_data,
            'quiz': quiz_data,
            'message': message
        }