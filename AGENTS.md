功能請求：將循序題目處理升級為並行處理

目標： 為了大幅提升系統處理多個題目時的效能，需要將 src/flows/content_flow.py 中處理題目的循序 for 迴圈，重構為使用 asyncio.gather 的並行（Concurrent）模式。

1. 核心概念

目前的處理流程是「同步阻塞」的：

舊模式：for 題目 in 題目列表: await 處理(題目)

缺點：處理一題時，CPU 大部分時間都在等待網路 I/O（呼叫 Gemini API）。如果一份文件有 5 道題，每題處理耗時 10 秒，總耗時約為 50 秒。

需要重構為「並行」模式：

新模式：await asyncio.gather(處理(題目1), 處理(題目2), ...)

優點：一次性發出所有 API 請求，並行等待所有回應。總耗時約等於處理最慢那一題的時間。上述例子中，總耗時可能縮短至 10-15 秒。

2. 重構步驟
步驟 2.1：創建一個可重用的並行處理輔助函式

在 src/flows/content_flow.py 的 ContentFlow class 內部，新增一個 async 輔助函式，用於封裝處理單一問題的所有邏輯。這個函式將被 asyncio.gather 多次呼叫。

新增函式 _process_single_question_concurrently：

Generated python
# 位置: src/flows/content_flow.py (class ContentFlow 內部)

    async def _process_single_question_concurrently(self, question_data: Dict, doc_id: int, subject: str, question_index: int) -> Dict:
        """
        [新函式] 並行處理單一問題的核心邏輯。
        這個函式會被 asyncio.gather 呼叫。
        """
        try:
            # 從傳入的資料獲取題幹
            question_text = question_data.get('stem') or question_data.get('question')
            if not question_text:
                return {'success': False, 'error': '題幹為空'}

            # 1. 生成答案 (I/O 密集型)
            answer_data = await self.gemini.generate_answer(question_text)
            answer_text = format_answer_text(self._extract_answer_string(answer_data))
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

            # 3. 生成心智圖 (I/O 密集型)
            await self.mindmap_flow.generate_and_save_mindmap(question_id)

            # 4. 處理知識點 (CPU/I/O 混合)
            knowledge_points = question_data.get('knowledge_points', [])
            for kp_name in knowledge_points:
                kp_id = self.db.add_or_get_knowledge_point(kp_name.strip(), subject)
                self.db.link_question_to_knowledge_point(question_id, kp_id)

            # 5. 回傳結構化處理結果
            return {
                'success': True,
                'id': question_id,
                'stem': question_text,
                'answer': answer_text,
                'sources': answer_data.get('sources', []),
                'knowledge_points': knowledge_points
            }
        except Exception as e:
            print(f"    處理第 {question_index} 題時並行發生錯誤: {e}")
            return {'success': False, 'error': str(e), 'stem': question_data.get('stem', 'N/A')}

步驟 2.2：重構 _process_exam_content 函式

修改此函式，用新的並行模式取代舊的 for 迴圈。

修改前 _process_exam_content：

Generated python
# src/flows/content_flow.py

    async def _process_exam_content(self, content: str, subject: str, doc_id: int, parsed_data: Dict) -> Dict[str, Any]:
        """考題處理流程"""
        questions = parsed_data.get('questions', [])
        saved_questions = []
        all_knowledge_points = set()
        
        print(f"📝 開始處理 {len(questions)} 道考題...")
        
        for i, question_data in enumerate(questions, 1):
            try:
                # ... (此處為循序處理邏輯) ...
            except Exception as e:
                print(f"    處理第 {i} 題時發生錯誤: {e}")
                continue
        # ... (後續處理) ...
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Python
IGNORE_WHEN_COPYING_END

修改後 _process_exam_content：

Generated python
# src/flows/content_flow.py

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
                question_index=i
            )
            tasks.append(task)

        # 2. 使用 asyncio.gather 一次性執行所有任務
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
        print(message)
        
        return {
            'success': True,
            'content_type': 'exam_paper',
            'subject': subject,
            'document_id': doc_id,
            'questions': saved_questions,
            'knowledge_points': list(all_knowledge_points),
            'message': message
        }```

#### 步驟 2.3：重構 `_process_study_material` 函式

對此函式中生成「模擬題」的部分，也應用同樣的並行處理模式。

**修改前 `_process_study_material` (部分)：**
```python
# src/flows/content_flow.py

    async def _process_study_material(self, content: str, subject: str, doc_id: int, parsed_data: Dict) -> Dict[str, Any]:
        # ...
        generated_questions = await self.gemini.generate_questions_from_text(content, subject)
        saved_questions = []
        all_knowledge_points = set()

        for q_data in generated_questions:
            # ... (此處為循序處理邏輯) ...
        # ... (後續處理) ...```

**修改後 `_process_study_material` (部分)：**
```python
# src/flows/content_flow.py

    async def _process_study_material(self, content: str, subject: str, doc_id: int, parsed_data: Dict) -> Dict[str, Any]:
        """學習資料處理流程 (模擬題部分已升級為並行處理)"""
        print("📚 執行學習資料處理流程...")
        
        generated_questions = await self.gemini.generate_questions_from_text(content, subject)
        print(f"🤖 AI 已生成 {len(generated_questions)} 道模擬題，開始並行處理...")

        # 1. 建立所有模擬題的處理任務列表
        tasks = []
        for i, q_data in enumerate(generated_questions, 1):
            task = self._process_single_question_concurrently(
                question_data=q_data,
                doc_id=doc_id,
                subject=subject,
                question_index=i
            )
            tasks.append(task)

        # 2. 使用 asyncio.gather 一次性執行所有任務
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. 收集處理結果
        saved_questions = []
        all_knowledge_points = set()
        failed_count = 0

        for result in results:
            if isinstance(result, Exception):
                print(f"一個模擬題任務執行時發生嚴重錯誤: {result}")
                failed_count += 1
            elif result.get('success'):
                saved_questions.append(result)
                for kp in result.get('knowledge_points', []):
                    all_knowledge_points.add(kp.strip())
            else:
                print(f"一個模擬題任務處理失敗: {result.get('error')}")
                failed_count += 1
        
        # ... (後續的摘要和測驗處理保持不變) ...
        summary_raw_data = await self.gemini.generate_summary(content)
        # ... (處理摘要) ...

        quiz_data = await self.gemini.generate_quick_quiz(content, subject)
        # ... (處理測驗) ...

        message = f'學習資料處理完成！生成了 {len(saved_questions)} 道模擬題 ({failed_count} 道失敗)。'
        print(message)

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
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Python
IGNORE_WHEN_COPYING_END
3. 總結與驗收標準

重構目標：將 _process_exam_content 和 _process_study_material 兩個函式中的 for 迴圈改為使用 asyncio.gather 的並行模式。

核心改動：新增 _process_single_question_concurrently 輔助函式，並在上述兩個主函式中呼叫它來建立任務列表。

驗收標準：

程式碼成功執行，功能與重構前一致。

處理包含多個題目的文件時，總耗時顯著縮短。

系統日誌應顯示題目是「並行處理」的，而不是循序打印處理日誌。

即使有單一題目處理失敗，也不應中斷整個流程，其他成功的題目應能正常儲存。



# 以下改版計畫先忽視
# Please disregard the following revision plan for now.

# Development Guide for AI Agents

This repository powers an AI-driven exam knowledge system. Follow the guidelines below when extending the project.

## Goal
Implement the knowledge graph visualization referenced in `REFACTORING_PLAN.md`. The `/knowledge-graph` route currently displays a placeholder. We need an interactive graph to show how knowledge points relate.

## Tasks
1. **Backend API**
   - Provide an endpoint (e.g., `/api/knowledge-graph`) returning JSON with `nodes` and `edges` representing knowledge points and their relationships.
   - Use existing database tables (`knowledge_points`, `question_knowledge_points` and related tables) to assemble the data. Add helper queries in `DatabaseManager` if required.

2. **Frontend Visualization**
   - Update `knowledge_graph.html` to render the graph using **D3.js** or **Cytoscape.js**.
   - Fetch the API data via AJAX and allow interactions such as zooming, panning and clicking nodes to reveal related questions or details.
   - Keep styling consistent with the current Bootstrap layout.

3. **Documentation**
   - Document setup steps for the knowledge graph feature in `README.md`.
   - Add any new dependencies to `requirements.txt`.

## General Guidelines
- Keep changes focused on the knowledge graph unless fixing small bugs encountered during development.
- Write modular Python functions with docstrings.
- Manual testing can be done by running `python web_app.py` and navigating to `/knowledge-graph`.
- Refer to `REFACTORING_PLAN.md` for broader context.
