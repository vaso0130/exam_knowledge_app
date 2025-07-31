from typing import Dict, Any, List
import asyncio
import concurrent.futures
from src.core.gemini_client import GeminiClient
from src.core.database import DatabaseManager

class ContentFlow:
    """內容處理流程管理器 - 統一管理所有內容分析、問題生成和知識點關聯"""
    
    def __init__(self, gemini_client: GeminiClient, db_manager: Datab            # 步驟5: 生成互動選擇題
            print("  🎯 生成互動選擇題...")
            try:
                quick_quiz = await self.gemini.generate_quick_quiz(content, subject)
                print(f"    ✅ 生成了 {len(quick_quiz)} 道選擇題")
            except Exception as e:
                print(f"    ❌ 互動選擇題生成失敗: {e}")
                quick_quiz = []
            
            # 步驟6: 組合完整的學習頁面內容
            print("  🔗 組合完整的學習頁面內容...")
            try:
                # 組合三個部分：資料主文 + 知識摘要 + 互動選擇題
                complete_learning_content = f"""# 📚 學習資料

## 📄 資料主文
{cleaned_main_content}

---

{knowledge_summary}

---

## 🎯 互動選擇題
""" + (f"共 {len(quick_quiz)} 道題目，請在頁面下方作答。" if quick_quiz else "暫無互動選擇題。")
                
                print(f"    ✅ 完整學習內容組合完成（{len(complete_learning_content)} 字元）")
                
            except Exception as e:
                print(f"    ❌ 學習內容組合失敗: {e}")
                complete_learning_content = f"{cleaned_main_content}\n\n{knowledge_summary}"
            
            # 步驟7: 更新文檔記錄，加入完整的學習內容和選擇題):
        self.gemini = gemini_client
        self.db = db_manager
        # 初始化檔案處理器
        from ..utils.file_processor import FileProcessor
        self.file_processor = FileProcessor()
    
    def process_file(self, file_path: str, filename: str, suggested_subject: str = None) -> Dict[str, Any]:
        """
        處理檔案的統一入口點 - 支援 PDF、圖片、文字檔案
        """
        try:
            # 使用檔案處理器讀取檔案內容
            content, file_type = self.file_processor.process_input(file_path)
            
            # 呼叫完整 AI 處理流程
            return self.complete_ai_processing(content, filename, suggested_subject)
            
        except Exception as e:
            print(f"處理檔案時發生錯誤: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'檔案處理失敗: {str(e)}'
            }
    
    def complete_ai_processing(self, content: str, filename: str, suggested_subject: str = None, source_url: str = None) -> Dict[str, Any]:
        """
        完整 AI 處理流程：一勞永逸的自動化處理
        - 自動分類內容類型（考題 vs 學習資料）
        - 根據類型執行不同的處理流程
        - 考題：題目分離 → 生成答案 → 知識點標註 → 心智圖
        - 學習資料：資訊提取 → 知識點分析 → 模擬題生成 → 心智圖
        """
        try:
            # 使用 ThreadPoolExecutor 來處理異步代碼
            def run_async_processing():
                return asyncio.run(self._run_async_processing(content, filename, suggested_subject, source_url))
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_async_processing)
                return future.result()
                
        except Exception as e:
            print(f"完整 AI 處理時發生錯誤: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '處理失敗，請稍後再試'
            }
    
    async def _run_async_processing(self, content: str, filename: str, suggested_subject: str = None, source_url: str = None) -> Dict[str, Any]:
        """執行異步處理流程"""
        try:
            # 步驟1: 使用 AI 自動分類內容
            print("🤖 AI 正在分析內容類型...")
            classification_result = await self.gemini.auto_classify_and_process(content)
            
            content_type = classification_result.get('content_type', 'study_material')
            detected_subject = classification_result.get('subject', suggested_subject or '其他')
            confidence = classification_result.get('confidence', 0.5)
            
            print(f"📋 內容分類結果：{content_type} ({detected_subject}, 信心度: {confidence:.2f})")
            
            # 儲存文檔到資料庫，包含原始內容和來源 URL
            doc_id = self.db.add_document(
                title=filename, 
                content=content, 
                subject=detected_subject, 
                original_content=content,
                source=source_url  # 保存原始 URL
            )
            
            # 步驟2: 根據內容類型選擇處理流程
            if content_type in ['exam_paper', 'exam']:
                print("📝 檢測到考題內容，執行考題處理流程...")
                result = await self._process_exam_content(content, detected_subject, doc_id, classification_result)
            else:
                print("📚 檢測到學習資料，執行學習資料處理流程...")
                result = await self._process_study_material(content, detected_subject, doc_id, classification_result)
            
            # 步驟3: 生成並儲存心智圖
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
    
    async def _process_exam_content(self, content: str, subject: str, doc_id: int, classification_result: Dict) -> Dict[str, Any]:
        """
        考題處理流程：考題 → 生成答案 → 知識點標註 → 心智圖
        """
        try:
            questions = classification_result.get('questions', [])
            saved_questions = []
            all_knowledge_points = set()
            
            print(f"📝 開始處理 {len(questions)} 道考題...")
            
            for i, question in enumerate(questions, 1):
                try:
                    print(f"  處理第 {i}/{len(questions)} 題...")
                    
                    question_text = question.get('stem', '')
                    answer_text = question.get('answer', '')
                    answer_sources = None
                    
                    # 格式化題目內容，識別程式碼區塊和表格
                    if question_text:
                        print(f"    格式化題目內容...")
                        try:
                            formatted_question = await self.gemini.format_question_content(question_text)
                            question_text = formatted_question
                        except Exception as e:
                            print(f"    格式化失敗，使用原始內容: {e}")
                    
                    # 如果沒有答案，使用 AI 生成
                    if not answer_text and question_text:
                        print(f"    生成答案...")
                        answer_data = await self.gemini.generate_answer(question_text)
                        if answer_data:
                            answer_text = answer_data.get('answer', '')
                            sources = answer_data.get('sources', [])
                            if sources:
                                import json
                                answer_sources = json.dumps(sources, ensure_ascii=False)
                    
                    # 儲存問題到資料庫
                    question_id = self.db.insert_question(
                        document_id=doc_id,
                        title=question.get('title', '無標題'),
                        question_text=question_text,
                        answer_text=answer_text,
                        subject=subject,
                        answer_sources=answer_sources
                    )
                    
                    # 處理知識點
                    knowledge_points = question.get('knowledge_points', [])
                    question_kps = []
                    for kp_name in knowledge_points:
                        if kp_name.strip():
                            kp_id = self.db.add_knowledge_point(kp_name.strip(), subject)
                            self.db.link_question_to_knowledge_point(question_id, kp_id)
                            all_knowledge_points.add(kp_name.strip())
                            question_kps.append(kp_name.strip())
                    
                    # 為每個題目生成專屬心智圖
                    try:
                        print(f"    為題目 {i} 生成心智圖...")
                        if question_kps:
                            question_mindmap = await self.gemini.generate_mindmap(
                                f"{question.get('title', f'題目{i}')} - {subject}", 
                                question_kps
                            )
                            if question_mindmap:
                                self.db.update_question_mindmap(question_id, question_mindmap)
                                print(f"    ✅ 題目 {i} 心智圖生成完成")
                        else:
                            print(f"    ⚠️  題目 {i} 沒有知識點，跳過心智圖生成")
                    except Exception as e:
                        print(f"    ❌ 題目 {i} 心智圖生成失敗: {e}")
                    
                    saved_questions.append({
                        'id': question_id,
                        'stem': question.get('stem', ''),
                        'answer': answer_text,
                        'knowledge_points': knowledge_points,
                        'mindmap': question_mindmap if 'question_mindmap' in locals() else None
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
                'message': f'成功處理考題，解析了 {len(saved_questions)} 道題目，提取了 {len(all_knowledge_points)} 個知識點'
            }
            
        except Exception as e:
            print(f"考題處理流程發生錯誤: {e}")
            raise e
    
    async def _process_study_material(self, content: str, subject: str, doc_id: int, classification_result: Dict) -> Dict[str, Any]:
        """
        學習資料處理流程：
        1. 提取知識點
        2. 生成申論模擬題（存入題庫）
        3. AI整理學習筆記格式
        4. 生成互動選擇題
        5. 更新文檔記錄
        6. 生成心智圖
        """
        try:
            print("📚 執行學習資料處理流程...")
            
            # 步驟1: 提取知識點
            print("  🔍 提取知識點...")
            knowledge_points_raw = await self.gemini.extract_knowledge_points(content, subject)
            knowledge_points = []
            all_knowledge_point_names = []
            
            # 儲存知識點到資料庫
            for kp_name in knowledge_points_raw:
                if kp_name.strip():
                    kp_id = self.db.add_knowledge_point(kp_name.strip(), subject)
                    knowledge_points.append({
                        'id': kp_id,
                        'name': kp_name.strip(),
                        'subject': subject
                    })
                    all_knowledge_point_names.append(kp_name.strip())
            
            print(f"    ✅ 提取了 {len(knowledge_points)} 個知識點")
            
            # 步驟2: 生成申論模擬題（存入題庫）
            print("  📝 生成申論模擬題...")
            generated_questions = await self.gemini.generate_questions_from_text(content, subject)
            saved_questions = []
            
            for i, question in enumerate(generated_questions, 1):
                try:
                    print(f"    處理第 {i}/{len(generated_questions)} 道模擬題...")
                    
                    # 格式化題目內容
                    question_text = question.get('question', '')
                    if question_text:
                        try:
                            formatted_question = await self.gemini.format_question_content(question_text)
                            question_text = formatted_question
                        except Exception as e:
                            print(f"      格式化失敗，使用原始內容: {e}")
                    
                    question_id = self.db.insert_question(
                        document_id=doc_id,
                        title=question.get('title', f'模擬題{i}'),
                        subject=subject,
                        question_text=question_text,
                        answer_text=question.get('answer', '')
                    )
                    
                    # 關聯問題與知識點
                    question_kps = question.get('knowledge_points', [])
                    actual_kps = []
                    for kp_name in question_kps:
                        if kp_name.strip():
                            # 找到對應的知識點 ID
                            kp_id = None
                            for kp in knowledge_points:
                                if kp['name'] == kp_name.strip():
                                    kp_id = kp['id']
                                    break
                            
                            if not kp_id:
                                # 如果知識點不存在，創建新的
                                kp_id = self.db.add_knowledge_point(kp_name.strip(), subject)
                            
                            self.db.link_question_to_knowledge_point(question_id, kp_id)
                            actual_kps.append(kp_name.strip())
                    
                    saved_questions.append({
                        'id': question_id,
                        'title': question.get('title', f'模擬題{i}'),
                        'question': question_text,
                        'answer': question.get('answer', ''),
                        'knowledge_points': actual_kps
                    })
                    
                except Exception as e:
                    print(f"      處理第 {i} 題時發生錯誤: {e}")
                    continue
            
            print(f"    ✅ 生成了 {len(saved_questions)} 道申論模擬題")
            
            # 步驟3: AI清理和整理資料主文
            print("  � AI清理和整理資料主文...")
            try:
                cleaned_main_content = await self.gemini.clean_and_organize_content(content)
                print(f"    ✅ 資料主文整理完成（{len(cleaned_main_content)} 字元）")
            except Exception as e:
                print(f"    ❌ 資料主文整理失敗: {e}")
                cleaned_main_content = content  # 使用原始內容作為後備
            
            # 步驟4: AI生成知識摘要
            print("  📋 AI生成知識摘要...")
            try:
                knowledge_summary = await self.gemini.generate_key_points_summary(content)
                print(f"    ✅ 知識摘要生成完成（{len(knowledge_summary)} 字元）")
            except Exception as e:
                print(f"    ❌ 知識摘要生成失敗: {e}")
                knowledge_summary = f"知識摘要生成失敗，錯誤：{str(e)}"
            
            # 步驟5: 生成互動選擇題
            print("  🎯 生成互動選擇題...")
            try:
                quick_quiz = await self.gemini.generate_quick_quiz(content, subject)
                print(f"    ✅ 生成了 {len(quick_quiz)} 道選擇題")
            except Exception as e:
                print(f"    ❌ 互動選擇題生成失敗: {e}")
                quick_quiz = []
            
            # 步驟5: 更新文檔記錄，加入學習筆記和選擇題
            print("  💾 更新文檔記錄...")
            try:
                import json
                
                # 確保數據格式正確
                if isinstance(key_points_summary, dict):
                    key_points_summary = json.dumps(key_points_summary, ensure_ascii=False, indent=2)
                elif key_points_summary is None:
                    key_points_summary = ""
                else:
                    key_points_summary = str(key_points_summary)
                
                # 處理 quick_quiz 的 JSON 序列化
                if isinstance(quick_quiz, list) and quick_quiz:
                    quick_quiz_json = json.dumps(quick_quiz, ensure_ascii=False)
                else:
                    quick_quiz_json = None
                
                # 更新文檔記錄
                self.db.cursor.execute('''
                    UPDATE documents 
                    SET key_points_summary = ?, quick_quiz = ?
                    WHERE id = ?
                ''', (key_points_summary, quick_quiz_json, doc_id))
                self.db.conn.commit()
                
                print(f"    ✅ 文檔 {doc_id} 記錄更新完成")
                
            except Exception as e:
                print(f"    ❌ 文檔記錄更新失敗: {e}")
            
            # 步驟6: 生成總結心智圖
            print("  🗺️ 生成學習資料心智圖...")
            overall_mindmap = None
            try:
                if all_knowledge_point_names:
                    overall_mindmap = await self.gemini.generate_mindmap(
                        f"學習資料總覽 - {subject}", 
                        all_knowledge_point_names
                    )
                    if overall_mindmap:
                        self.db.update_document_mindmap(doc_id, overall_mindmap)
                        print(f"    ✅ 學習資料心智圖生成完成")
                else:
                    print(f"    ⚠️  沒有知識點，跳過心智圖生成")
            except Exception as e:
                print(f"    ❌ 學習資料心智圖生成失敗: {e}")
            
            # 返回處理結果
            return {
                'success': True,
                'content_type': 'study_material',
                'subject': subject,
                'document_id': doc_id,
                'questions': saved_questions,  # 申論模擬題
                'knowledge_points': all_knowledge_point_names,
                'key_points_summary': key_points_summary,  # AI整理的學習筆記
                'quick_quiz': quick_quiz,  # 互動選擇題
                'mindmap': overall_mindmap,
                'message': f'學習資料處理完成！生成了 {len(saved_questions)} 道申論題、{len(quick_quiz)} 道選擇題，提取了 {len(knowledge_points)} 個知識點'
            }
            
        except Exception as e:
            print(f"學習資料處理流程發生錯誤: {e}")
            raise e
            
            return {
                'success': True,
                'content_type': 'study_material',
                'subject': subject,
                'document_id': doc_id,
                'questions': saved_questions,
                'knowledge_points': knowledge_points,
                'message': f'成功處理學習資料，提取了 {len(knowledge_points)} 個知識點，生成了 {len(saved_questions)} 道模擬題'
            }
            
        except Exception as e:
            print(f"學習資料處理流程發生錯誤: {e}")
            raise e

    async def process_content(self, text: str, subject: str, doc_title: str, doc_id: int) -> Dict[str, Any]:
        """
        處理單一文本內容，提取知識點、生成問題並儲存。
        第二步實施：AI 能力升級 - 自動識別與關聯
        """
        try:
            # 1. 整體提取知識點（用於文檔級別的分類）
            print(f"正在從文本中提取 '{subject}' 科的整體知識點...")
            document_knowledge_points = await self.gemini.extract_knowledge_points(text, subject)
            if not document_knowledge_points:
                print("未能提取到文檔知識點，但仍繼續處理...")

            # 2. 生成模擬題（帶有個別的知識點標籤）
            print("正在根據文本生成模擬題，並為每題自動標註知識點...")
            generated_questions = await self.gemini.generate_questions_from_text(text, subject)
            if not generated_questions:
                print("AI未生成模擬題，但流程繼續...")
                generated_questions = []  # 設為空列表而不是中止流程

            # 3. 儲存資料並建立知識點關聯
            print("正在儲存問題與知識點關聯...")
            saved_data = await self._store_question_and_knowledge_data(
                document_id=doc_id,
                subject=subject,
                questions=generated_questions,
                document_knowledge_points=document_knowledge_points or []
            )

            return {
                'success': True,
                'type': 'question_batch',
                'document_id': doc_id,
                'question_ids': saved_data['question_ids'],
                'knowledge_points': saved_data['all_knowledge_points'],
                'data': {
                    'questions': generated_questions
                }
            }

        except Exception as e:
            print(f"處理內容時發生錯誤: {e}")
            return {'success': False, 'error': str(e)}

    async def _store_question_and_knowledge_data(self, document_id: int, subject: str,
                                                 questions: List[Dict[str, Any]],
                                                 document_knowledge_points: List[str]) -> Dict[str, Any]:
        """
        儲存問題、知識點，並建立兩者之間的關聯。
        第二步升級：每個問題都有自己的知識點標籤
        """
        all_knowledge_points = set(document_knowledge_points)  # 收集所有知識點
        question_ids = []
        
        # 處理每個問題
        for q in questions:
            # 儲存問題
            question_id = self.db.insert_question(
                document_id=document_id,
                title=q.get('title', '無標題'),
                question_text=q.get('question', ''),
                answer_text=q.get('answer', ''),
                subject=subject
            )
            question_ids.append(question_id)
            
            # 處理這個問題的個別知識點標籤
            question_knowledge_points = q.get('knowledge_points', [])
            question_tags = q.get('tags', [])
            
            # 合併知識點和標籤（標籤也視為知識點的一種）
            combined_points = question_knowledge_points + question_tags
            all_knowledge_points.update(combined_points)
            
            # 為每個問題建立知識點關聯
            for kp_name in combined_points:
                if kp_name.strip():  # 確保不是空字串
                    # 新增或取得知識點 ID
                    kp_id = self.db.add_knowledge_point(name=kp_name.strip(), subject=subject)
                    # 建立問題與知識點的關聯
                    self.db.link_question_to_knowledge_point(question_id, kp_id)
            
            print(f"問題 {question_id} 已關聯到 {len(combined_points)} 個知識點")
        
        # 也為文檔級別的知識點建立關聯（如果有的話）
        for doc_kp in document_knowledge_points:
            if doc_kp.strip():
                kp_id = self.db.add_knowledge_point(name=doc_kp.strip(), subject=subject)
                # 將文檔知識點與所有問題關聯
                for q_id in question_ids:
                    self.db.link_question_to_knowledge_point(q_id, kp_id)
        
        return {
            "question_ids": question_ids,
            "all_knowledge_points": list(all_knowledge_points)
        }
