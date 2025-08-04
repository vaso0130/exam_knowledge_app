
import os
import json
import asyncio
from typing import Dict, List, Any

# Assuming the main Gemini client is in the core directory
from ..core.gemini_client import GeminiClient
from ..utils.json_parser import extract_json_from_text

class NoteAIClient:
    """
    A dedicated AI client for handling all AI-related tasks for the notes system.
    It leverages the core GeminiClient for actual API communication.
    """
    def __init__(self):
        # Initialize the core Gemini client
        # This assumes API keys and other configurations are handled within GeminiClient
        self.gemini_client = GeminiClient()

    def _run_async(self, coro):
        """Helper method to run async functions synchronously - fixed"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in a running loop, we can't use run_until_complete
                # Instead, we'll use a thread pool to avoid blocking
                import concurrent.futures
                import threading
                
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    return future.result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop, create a new one
            return asyncio.run(coro)

    async def _safe_generate_json(self, prompt: str, use_simple_model: bool = False) -> Dict[str, Any]:
        """Safely generate JSON response with error handling"""
        try:
            # 根據任務複雜度選擇模型
            if use_simple_model:
                raw_response = await self.gemini_client.generate_async_simple(prompt, is_json=True)
            else:
                raw_response = await self.gemini_client.generate_async(prompt, is_json=True)
            
            # Try to parse as JSON
            if raw_response.strip().startswith('{') or raw_response.strip().startswith('['):
                try:
                    return json.loads(raw_response)
                except json.JSONDecodeError:
                    pass
            
            # Use the main app's JSON extraction utility
            extracted_json = extract_json_from_text(raw_response)
            if extracted_json:
                return extracted_json
                
            # If all fails, return error structure
            return {'error': 'Failed to parse JSON response', 'raw_response': raw_response}
            
        except Exception as e:
            return {'error': str(e)}

    def analyze_note_content(self, content: str) -> Dict[str, Any]:
        """
        Analyzes the note content to extract key information using a structured prompt.

        Args:
            content: The text content of the note.

        Returns:
            A dictionary containing the analysis results.
        """
        prompt = f"""
        請對以下筆記內容進行深入分析，並以 JSON 格式回傳結果。
        分析應包含以下幾個部分：
        1.  `summary`: 為筆記產生一段約 100-150 字的精簡摘要。
        2.  `keywords`: 提取 5-8 個最重要的關鍵字。
        3.  `main_topics`: 識別筆記涵蓋的 2-3 個主要主題。
        4.  `difficulty_level`: 評估內容的難易度（例如：初級、中級、高級）。
        5.  `suggested_tags`: 根據內容建議 3-5 個相關的標籤。
        6.  `knowledge_points`: 列出筆記中提到的具體知識點（如果有的話）。

        筆記內容：
        ---
        {content}
        ---

        請嚴格按照上述要求以 JSON 格式輸出。
        """
        
        try:
            # 使用主模型進行內容分析（複雜推理任務）
            response_data = self._run_async(self._safe_generate_json(prompt, use_simple_model=False))
            
            # Basic validation to ensure the response has the expected keys
            required_keys = ['summary', 'keywords', 'main_topics', 'difficulty_level', 'suggested_tags', 'knowledge_points']
            if 'error' in response_data:
                return self._get_default_analysis_structure(f"AI Error: {response_data['error']}")
            
            if not all(key in response_data for key in required_keys):
                # Handle cases where the AI response is not as expected
                return self._get_default_analysis_structure("AI response missing required keys.")

            return response_data

        except Exception as e:
            # Handle exceptions from the AI client (e.g., API errors, parsing issues)
            print(f"Error during note analysis: {e}")
            return self._get_default_analysis_structure(str(e))

    def suggest_related_content(self, note_content: str, existing_notes: List[str], all_knowledge_points: List[str]) -> Dict[str, List]:
        """
        Suggests related content based on the note's text.

        Args:
            note_content: The content of the current note.
            existing_notes: A list of titles of other notes.
            all_knowledge_points: A list of all available knowledge points.

        Returns:
            A dictionary with suggestions.
        """
        prompt = f"""
        根據以下筆記內容，從提供的「現有筆記標題列表」和「知識點列表」中，找出最相關的 3-5 項內容。
        同時，請產生 2-3 個相關的練習題目和學習建議。

        筆記內容：
        ---
        {note_content}
        ---

        現有筆記標題列表：
        {existing_notes}

        知識點列表：
        {all_knowledge_points}

        請以 JSON 格式回傳，包含以下鍵：
        - `related_notes`: (list of strings)
        - `knowledge_points`: (list of strings)
        - `questions`: (list of strings)
        - `study_suggestions`: (list of strings)
        """
        try:
            # 使用主模型進行相關內容建議（複雜推理任務）
            response_data = self._run_async(self._safe_generate_json(prompt, use_simple_model=False))
            if 'error' in response_data:
                return {
                    'related_notes': [],
                    'knowledge_points': [],
                    'questions': [],
                    'study_suggestions': [f"Error: {response_data['error']}"]
                }
            return response_data
        except Exception as e:
            print(f"Error suggesting related content: {e}")
            return {
                'related_notes': [],
                'knowledge_points': [],
                'questions': [],
                'study_suggestions': [f"Error: {e}"]
            }

    # === AI 筆記整理功能 ===

    def organize_with_mindmap(self, content: str) -> Dict[str, Any]:
        """將筆記轉換成心智圖結構化格式"""
        prompt = f"""
        請將以下筆記內容轉換成心智圖的結構化格式。

        筆記內容：
        ---
        {content}
        ---

        請以 JSON 格式回傳，包含：
        1. `mindmap_structure`: 心智圖的階層結構，用嵌套字典表示
        2. `central_topic`: 中心主題
        3. `main_branches`: 主要分支列表
        4. `mermaid_code`: 可用於渲染的 Mermaid 心智圖代碼
        5. `organized_content`: 按心智圖結構重新整理的內容

        JSON 格式：
        {{
            "central_topic": "主要概念",
            "main_branches": ["分支1", "分支2", "分支3"],
            "mindmap_structure": {{
                "主要概念": {{
                    "分支1": ["細節1", "細節2"],
                    "分支2": ["細節3", "細節4"]
                }}
            }},
            "mermaid_code": "mindmap\\n  root((主要概念))\\n    分支1\\n      細節1\\n      細節2",
            "organized_content": "重新整理後的內容"
        }}
        """
        # AI 整理功能：使用輔助模型（簡單整理任務）
        return self._safe_ai_call(prompt, "mindmap", use_simple_model=True)

    def organize_hierarchically(self, content: str) -> Dict[str, Any]:
        """層次化重點整理"""
        prompt = f"""
        請將以下筆記內容按重要性和邏輯關係分層整理。

        筆記內容：
        ---
        {content}
        ---

        請以 JSON 格式回傳，包含：
        1. `title`: 整理後的標題
        2. `main_points`: 主要重點列表（重要性排序）
        3. `supporting_details`: 每個重點的支撐細節
        4. `key_concepts`: 關鍵概念列表
        5. `hierarchical_structure`: 完整的階層結構
        6. `organized_content`: 按層次重新整理的內容

        重點要按重要性排序，並清楚標示各層級關係。
        """
        # 層次化整理：使用輔助模型
        return self._safe_ai_call(prompt, "hierarchical", use_simple_model=True)

    def organize_with_feynman_technique(self, content: str) -> Dict[str, Any]:
        """費曼技巧解析 - 用簡單易懂的方式重新解釋概念"""
        prompt = f"""
        請使用費曼技巧將以下筆記內容重新解釋，用最簡單易懂的方式表達。

        筆記內容：
        ---
        {content}
        ---

        請以 JSON 格式回傳，包含：
        1. `simple_explanation`: 用最簡單的語言解釋主要概念
        2. `analogies`: 生動的類比和比喻
        3. `step_by_step`: 分步驟詳細說明
        4. `examples`: 具體的例子
        5. `potential_gaps`: 可能的理解盲點
        6. `teaching_points`: 如果要教別人，重點是什麼
        7. `organized_content`: 費曼技巧整理後的內容

        目標是讓一個完全不懂這個領域的人也能理解。
        """
        # 費曼技巧：使用主模型（需要深度理解和解釋）
        return self._safe_ai_call(prompt, "feynman", use_simple_model=False)

    def organize_with_qa_learning(self, content: str) -> Dict[str, Any]:
        """問答式學習 - 生成一系列漸進式問題來加深理解"""
        prompt = f"""
        請將以下筆記內容轉換成問答式學習格式，生成漸進式問題來加深理解。

        筆記內容：
        ---
        {content}
        ---

        請以 JSON 格式回傳，包含：
        1. `basic_questions`: 基礎理解問題（5-7個）
        2. `intermediate_questions`: 中級應用問題（3-5個）
        3. `advanced_questions`: 高級分析問題（2-3個）
        4. `critical_thinking`: 批判性思考問題（2個）
        5. `answers`: 所有問題的詳細答案
        6. `learning_progression`: 學習進度建議
        7. `organized_content`: 問答式整理的內容

        問題要有層次性，從簡單到複雜，幫助深度理解。
        """
        # 問答式學習：使用主模型（需要複雜的問題設計）
        return self._safe_ai_call(prompt, "qa_learning", use_simple_model=False)

    def organize_with_comparison(self, content: str) -> Dict[str, Any]:
        """對比分析整理 - 找出關鍵概念間的異同和關聯"""
        prompt = f"""
        請對以下筆記內容進行對比分析，找出關鍵概念間的異同點和關聯性。

        筆記內容：
        ---
        {content}
        ---

        請以 JSON 格式回傳，包含：
        1. `key_concepts`: 識別出的關鍵概念列表
        2. `similarities`: 概念間的相似點
        3. `differences`: 概念間的差異點
        4. `relationships`: 概念間的關聯性
        5. `comparison_table`: 對比表格格式
        6. `pros_and_cons`: 優缺點分析
        7. `organized_content`: 對比分析後的整理內容

        重點是清楚呈現概念間的關係和區別。
        """
        # 對比分析：使用主模型（需要複雜的概念分析）
        return self._safe_ai_call(prompt, "comparison", use_simple_model=False)

    def organize_with_memory_palace(self, content: str) -> Dict[str, Any]:
        """記憶宮殿法 - 將內容轉換成故事或空間記憶結構"""
        prompt = f"""
        請將以下筆記內容轉換成記憶宮殿的格式，用故事或空間記憶法來幫助記憶。

        筆記內容：
        ---
        {content}
        ---

        請以 JSON 格式回傳，包含：
        1. `memory_story`: 記憶故事（將概念編成一個有趣的故事）
        2. `spatial_layout`: 空間佈局描述（想像的空間和路線）
        3. `key_anchors`: 關鍵記憶錨點
        4. `visual_imagery`: 視覺想像描述
        5. `memory_cues`: 記憶提示和技巧
        6. `practice_routine`: 記憶練習建議
        7. `organized_content`: 記憶宮殿法整理的內容

        要讓內容容易記憶和回憶。
        """
        # 記憶宮殿：使用輔助模型（創意性較強但不需要太複雜推理）
        return self._safe_ai_call(prompt, "memory_palace", use_simple_model=True)

    def format_and_enhance_content(self, content: str) -> Dict[str, Any]:
        """格式化與補強 - 整理格式、補充資料、修正錯字"""
        prompt = f"""
        請對以下筆記內容進行格式化整理、補充相關資料，並修正任何錯字或語法問題。

        筆記內容：
        ---
        {content}
        ---

        請以 JSON 格式回傳，包含：
        1. `formatted_content`: 格式化後的內容（Markdown格式，結構清晰）
        2. `corrections_made`: 修正的錯字和語法問題列表
        3. `enhancements_added`: 新增的補充資料和說明
        4. `structure_improvements`: 結構改善說明
        5. `formatting_notes`: 格式化處理說明
        6. `additional_resources`: 建議的延伸閱讀或參考資料
        7. `organized_content`: 最終整理完成的內容

        重點：
        - 保持原意不變，只改善表達和結構
        - 修正錯字、標點符號、語法問題
        - 統一格式（標題、列表、段落）
        - 適當補充背景知識或定義
        - 增加邏輯結構和可讀性
        """
        # 格式化與補強：使用輔助模型（簡單的格式處理）
        return self._safe_ai_call(prompt, "format_enhance", use_simple_model=True)

    # === 互動式選擇題生成 ===

    def generate_interactive_quiz(self, content: str) -> Dict[str, Any]:
        """根據筆記內容生成互動式選擇題"""
        prompt = f"""
        請根據以下筆記內容生成一套互動式選擇題，用於測試理解程度。

        筆記內容：
        ---
        {content}
        ---

        請以 JSON 格式回傳，包含：
        1. `questions`: 問題列表，每個問題包含：
           - `question`: 問題內容
           - `options`: 4個選項（A、B、C、D）
           - `correct_answer`: 正確答案（A/B/C/D）
           - `explanation`: 詳細解釋
           - `difficulty`: 難易度（easy/medium/hard）
           - `question_type`: 問題類型（概念理解/應用分析/綜合評價）
        2. `quiz_summary`: 測驗摘要（總題數、各難度分布）
        3. `learning_objectives`: 學習目標

        請生成 8-12 道題目，涵蓋不同難度和題型。
        """
        # 互動式測驗：使用輔助模型（選擇題生成相對簡單）
        return self._safe_ai_call(prompt, "interactive_quiz", use_simple_model=True)

    # === 從題庫或教材生成筆記 ===

    def generate_note_from_questions(self, questions_data: List[Dict]) -> Dict[str, Any]:
        """從題庫資料生成筆記"""
        questions_text = "\n\n".join([
            f"題目：{q.get('question_text', '')}\n答案：{q.get('answer_text', '')}"
            for q in questions_data
        ])
        
        prompt = f"""
        請根據以下題目和答案，生成一份完整的學習筆記。

        題目資料：
        ---
        {questions_text}
        ---

        請以 JSON 格式回傳，包含：
        1. `title`: 筆記標題
        2. `content`: 完整的筆記內容（Markdown 格式）
        3. `key_concepts`: 涵蓋的關鍵概念
        4. `study_tips`: 學習重點提示
        5. `related_topics`: 相關主題
        6. `difficulty_assessment`: 難度評估
        7. `suggested_tags`: 建議標籤

        筆記要系統性地整理知識點，方便學習。
        """
        # 從題庫生成筆記：使用主模型（需要系統性整理）
        return self._safe_ai_call(prompt, "note_from_questions", use_simple_model=False)

    def generate_note_from_materials(self, materials_content: str, material_type: str = "教材") -> Dict[str, Any]:
        """從教材內容生成筆記"""
        prompt = f"""
        請將以下{material_type}內容整理成一份學習筆記。

        {material_type}內容：
        ---
        {materials_content}
        ---

        請以 JSON 格式回傳，包含：
        1. `title`: 筆記標題
        2. `content`: 完整的筆記內容（Markdown 格式）
        3. `summary`: 內容摘要
        4. `key_points`: 重點列表
        5. `concepts`: 重要概念定義
        6. `examples`: 具體例子
        7. `study_suggestions`: 學習建議
        8. `suggested_tags`: 建議標籤

        筆記要清楚易懂，適合複習使用。
        """
        # 從教材生成筆記：使用主模型（需要教學性整理）
        return self._safe_ai_call(prompt, "note_from_materials", use_simple_model=False)

    # === 輔助方法 ===

    def _safe_ai_call(self, prompt: str, operation_type: str, use_simple_model: bool = False) -> Dict[str, Any]:
        """安全的 AI 調用，包含錯誤處理"""
        try:
            response_data = self._run_async(self._safe_generate_json(prompt, use_simple_model))
            if 'error' in response_data:
                return {
                    'error': response_data['error'],
                    'operation_type': operation_type,
                    'success': False,
                    'organized_content': f'AI 整理失敗：{response_data["error"]}',
                    'model_used': 'simple' if use_simple_model else 'primary'
                }
            response_data['success'] = True
            response_data['model_used'] = 'simple' if use_simple_model else 'primary'
            return response_data
        except Exception as e:
            print(f"Error during {operation_type} operation: {e}")
            return {
                'error': str(e),
                'operation_type': operation_type,
                'success': False,
                'organized_content': f'AI 整理失敗：{str(e)}',
                'model_used': 'simple' if use_simple_model else 'primary'
            }

    def _get_default_analysis_structure(self, error_message: str = "") -> Dict[str, Any]:
        """Returns a default structure for analysis results in case of an error."""
        return {
            'summary': f'Failed to generate summary. {error_message}',
            'keywords': [],
            'main_topics': [],
            'difficulty_level': 'Unknown',
            'suggested_tags': [],
            'knowledge_points': []
        }

