
import os
import json
import asyncio
import re
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
            
            # 清理回應（移除多餘的空白和標記）
            cleaned_response = raw_response.strip()
            
            # 移除常見的非JSON前綴和後綴
            prefixes_to_remove = ['```json', '```JSON', '```', 'json', 'JSON']
            suffixes_to_remove = ['```', '```json', '```JSON']
            
            for prefix in prefixes_to_remove:
                if cleaned_response.startswith(prefix):
                    cleaned_response = cleaned_response[len(prefix):].strip()
                    break
                    
            for suffix in suffixes_to_remove:
                if cleaned_response.endswith(suffix):
                    cleaned_response = cleaned_response[:-len(suffix)].strip()
                    break
            
            # 嘗試直接解析JSON
            if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
                try:
                    parsed_json = json.loads(cleaned_response)
                    if isinstance(parsed_json, dict):
                        # 驗證和修復內容欄位
                        parsed_json = self._ensure_organized_content(parsed_json)
                        return parsed_json
                except json.JSONDecodeError as e:
                    print(f"直接JSON解析失敗: {e}")
                    print(f"RAW AI RESPONSE THAT FAILED PARSING:\n---\n{cleaned_response[:1000]}\n---")
                    # 嘗試修復常見的JSON問題
                    fixed_json = self._fix_common_json_issues(cleaned_response)
                    if fixed_json:
                        try:
                            parsed_json = json.loads(fixed_json)
                            if isinstance(parsed_json, dict):
                                parsed_json = self._ensure_organized_content(parsed_json)
                                return parsed_json
                        except json.JSONDecodeError as inner_e:
                            print(f"修復後JSON解析仍失敗: {inner_e}")
                            pass
            
            # 如果直接解析失敗，使用提取工具
            from ..utils.json_parser import extract_json_from_text
            extracted_json = extract_json_from_text(cleaned_response)
            if extracted_json and isinstance(extracted_json, dict):
                extracted_json = self._ensure_organized_content(extracted_json)
                return extracted_json
            elif extracted_json and isinstance(extracted_json, list):
                return {
                    'data': extracted_json, 
                    'organized_content': '列表格式的整理結果：\n' + '\n'.join([str(item) for item in extracted_json])
                }
            
            # 嘗試從原始回應中提取有用信息
            if cleaned_response and len(cleaned_response.strip()) > 10:
                # 如果AI回應看起來像是結構化內容但不是JSON
                structured_content = self._extract_structured_content(cleaned_response)
                if structured_content:
                    return structured_content
                    
                # 最後的備用：將整個回應作為organized_content
                return {
                    'organized_content': cleaned_response,
                    'raw_response': raw_response,
                    'parsing_note': '無法解析為JSON格式，使用原始AI回應作為內容'
                }
            
            # 完全失敗的情況  
            return {
                'error': 'Failed to parse JSON response', 
                'raw_response': raw_response,
                'organized_content': f'AI回應解析失敗。原始回應: {raw_response[:200]}...'
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'organized_content': f'AI處理過程中發生錯誤: {str(e)}'
            }

    def _ensure_organized_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """確保數據有organized_content欄位"""
        if not data.get('organized_content'):
            # 嘗試從其他欄位生成organized_content
            content_sources = [
                'formatted_content', 'simple_explanation', 'memory_story',
                'content', 'result', 'text', 'summary', 'description'
            ]
            
            for field in content_sources:
                if data.get(field):
                    if isinstance(data[field], str):
                        data['organized_content'] = data[field]
                        break
                    elif isinstance(data[field], list):
                        data['organized_content'] = '\n'.join([str(item) for item in data[field]])
                        break
            
            # 如果仍然沒有，嘗試合成一個
            if not data.get('organized_content'):
                data['organized_content'] = self._synthesize_content_from_data(data)
        
        return data

    def _fix_common_json_issues(self, json_str: str) -> str:
        """修復常見的JSON格式問題"""
        try:
            # 移除多餘的逗號
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            # 修復單引號為雙引號
            json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
            json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
            
            # 修復未加引號的鍵
            json_str = re.sub(r'(\w+):', r'"\1":', json_str)
            
            return json_str
        except:
            return None

    def _extract_structured_content(self, text: str) -> Dict[str, Any]:
        """從非JSON格式的結構化文本中提取內容"""
        try:
            # 如果文本包含明顯的結構標記
            if '**' in text or '##' in text or '*' in text or '1.' in text:
                return {
                    'organized_content': text,
                    'content_type': 'markdown',
                    'parsing_note': '檢測到結構化文本，作為Markdown內容處理'
                }
            return None
        except:
            return None

    def _synthesize_content_from_data(self, data: Dict[str, Any]) -> str:
        """從數據字典合成organized_content"""
        try:
            content_parts = []
            
            # 根據不同的欄位類型組合內容
            field_priorities = [
                'title', 'main_points', 'basic_questions', 'memory_story',
                'simple_explanation', 'key_concepts', 'summary'
            ]
            
            for field in field_priorities:
                if data.get(field):
                    if isinstance(data[field], str):
                        content_parts.append(f"**{field.replace('_', ' ').title()}:**\n{data[field]}")
                    elif isinstance(data[field], list):
                        items = '\n'.join([f"- {item}" for item in data[field]])
                        content_parts.append(f"**{field.replace('_', ' ').title()}:**\n{items}")
            
            if content_parts:
                return '\n\n'.join(content_parts)
            else:
                return f"整理結果包含 {len(data)} 個欄位，請查看詳細資料。"
                
        except Exception as e:
            return f"內容合成失敗: {str(e)}"

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
        """將筆記轉換成心智圖結構化格式，專為 ECharts 優化"""
        prompt = f"""
        請將以下筆記內容轉換成心智圖的結構化 JSON 格式。
        輸出的 JSON 中 `mindmap_data` 欄位必須符合 ECharts Tree Chart 的格式，也就是一個包含 `name` 和 `children` 的巢狀物件。

        筆記內容：
        ---
        {content}
        ---

        **--- JSON 格式範例 START ---**
        {{
            "central_topic": "雲端計算核心概念",
            "main_branches": ["傳統模式", "雲端模式", "二進位啟示"],
            "mindmap_data": {{
                "name": "雲端計算核心概念",
                "children": [
                    {{
                        "name": "傳統本地計算",
                        "children": [
                            {{ "name": "數據處理：集中式儲存" }},
                            {{ "name": "邏輯運算：垂直擴展" }}
                        ]
                    }},
                    {{
                        "name": "雲端計算模式",
                        "children": [
                            {{ "name": "數據處理：分散式儲存" }},
                            {{ "name": "邏輯運算：彈性擴展" }}
                        ]
                    }},
                    {{ "name": "萊布尼茲的二進位啟示" }}
                ]
            }},
            "organized_content": "### 心智圖整理\\n- **中心主題**: 雲端計算核心概念\\n  - **主要分支**: 傳統本地計算..."
        }}
        **--- JSON 格式範例 END ---**

        請嚴格按照上述範例的 `mindmap_data` 結構生成 JSON。
        """
        # 不再需要 mermaid_code，而是 mindmap_data
        return self._safe_ai_call(prompt, "mindmap", use_simple_model=True)

    def organize_hierarchically(self, content: str) -> Dict[str, Any]:
        """層次化重點整理"""
        prompt = f"""
        請將以下筆記內容按重要性和邏輯關係分層整理。

        筆記內容：
        ---
        {content}
        ---

        請以 JSON 格式回傳，**必須**是有效的JSON結構，包含：
        {{
            "title": "整理後的標題",
            "main_points": ["重要重點1", "重要重點2", "重要重點3"],
            "supporting_details": {{
                "重要重點1": ["支撐細節1", "支撐細節2"],
                "重要重點2": ["支撐細節3", "支撐細節4"]
            }},
            "key_concepts": ["關鍵概念1", "關鍵概念2", "關鍵概念3"],
            "hierarchical_structure": {{
                "第一層": ["項目1", "項目2"],
                "第二層": ["子項目1", "子項目2"]
            }},
            "organized_content": "按層次重新整理的完整內容，包含所有重點和細節"
        }}

        重點要按重要性排序，並清楚標示各層級關係。回傳的必須是有效的JSON格式。
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

        請以 JSON 格式回傳，**必須**是有效的JSON結構，包含：
        {{
            "simple_explanation": "用最簡單的語言解釋主要概念的內容",
            "analogies": ["類比1", "類比2", "類比3"],
            "step_by_step": ["步驟1說明", "步驟2說明", "步驟3說明"],
            "examples": ["具體例子1", "具體例子2"],
            "potential_gaps": ["可能的理解盲點1", "盲點2"],
            "teaching_points": ["教學重點1", "重點2", "重點3"],
            "organized_content": "費曼技巧整理後的完整內容，包含簡單解釋、類比、步驟說明和例子"
        }}

        目標是讓一個完全不懂這個領域的人也能理解。回傳的必須是有效的JSON格式。
        """
        # 費曼技巧：使用主模型（需要深度理解和解釋）
        return self._safe_ai_call(prompt, "feynman", use_simple_model=False)

    def organize_with_qa_learning(self, content: str) -> Dict[str, Any]:
        """問答式學習 - 生成一系列漸進式問題來加深理解"""
        prompt = f"""
        請將以下筆記內容轉換成問答式學習格式。嚴格遵循JSON格式，不要在JSON物件前後添加任何額外文字。

        **--- JSON 格式範例 START ---**
        {{
            "basic_questions": [
                "什麼是萊布尼茲的二進位系統？",
                "二進位系統使用哪兩個數字？"
            ],
            "intermediate_questions": [
                "二進位系統如何影響現代計算機架構？",
                "請舉例說明數字10如何用二進位表示。"
            ],
            "advanced_questions": [
                "除了二進位，還有哪些進位制在特定計算領域被使用？並說明其應用場景。"
            ],
            "critical_thinking": [
                "如果人類文明是基於三進位系統發展，科技和社會會是什麼樣子？"
            ],
            "answers": {{
                "什麼是萊布尼茲的二進位系統？": "這是一個由德國哲學家和數學家萊布尼茲推廣的進位制，它只使用0和1兩個數字來表示所有數值。這是現代計算機運作的基礎。",
                "二進位系統使用哪兩個數字？": "0 和 1。"
            }},
            "learning_progression": "建議先從基礎問題開始，確保理解核心定義，然後進入中級問題進行應用練習，最後挑戰高級和批判性思考問題以深化理解。",
            "organized_content": "### 問答式學習\\n\\n**基礎問題**\\n- 什麼是萊布尼茲的二進位系統？\\n  - **答案**: 這是一個由德國哲學家和數學家萊布尼茲推廣的進位制...\\n\\n..."
        }}
        **--- JSON 格式範例 END ---**

        請根據以下筆記內容生成類似上述範例的JSON輸出。回傳的必須是有效的JSON格式。

        筆記內容：
        ---
        {content}
        ---
        
        請以 JSON 格式回傳，**必須**是有效的JSON結構，包含：
        {{
            "basic_questions": ["基礎問題1", "基礎問題2", "基礎問題3", "基礎問題4", "基礎問題5"],
            "intermediate_questions": ["中級問題1", "中級問題2", "中級問題3"],
            "advanced_questions": ["高級問題1", "高級問題2"],
            "critical_thinking": ["批判性思考問題1", "批判性思考問題2"],
            "answers": {{
                "基礎問題1": "詳細答案",
                "基礎問題2": "詳細答案"
            }},
            "learning_progression": "學習進度建議的內容",
            "organized_content": "問答式整理的完整內容，包含所有問題和答案"
        }}

        問題要有層次性，從簡單到複雜，幫助深度理解。回傳的必須是有效的JSON格式。
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

        **--- JSON 格式範例 START ---**
        {{
            "memory_story": "想像一個古老的圖書館，每個書架代表一個重要概念。圖書管理員帶你參觀，首先來到了「二進位系統」的書架，上面擺放著只有0和1兩種顏色的書籍。接著，你們走向「資料表示」區域，那裡有一面牆展示著如何用0和1的組合形成各種數字、字母與符號。最後，你們來到了「計算機架構」展示廳，裡面有一個巨大的模型，展示電流如何通過電晶體表示0和1的狀態。",
            "spatial_layout": "整個記憶宮殿是一座三層樓的圖書館。一樓是基礎概念區，二樓是應用區，三樓是前沿研究區。各樓層之間由螺旋樓梯連接，每個概念都有專屬的展示空間。",
            "key_anchors": [
                {{
                    "anchor": "黑白書架",
                    "content": "代表二進位的0和1",
                    "visual": "書架上只有純黑和純白兩種顏色的書"
                }},
                {{
                    "anchor": "彩色編碼牆",
                    "content": "代表如何用二進位編碼表示各種資料",
                    "visual": "牆上有色彩鮮豔的編碼表，0和1的組合對應著不同的文字和圖像"
                }}
            ],
            "visual_imagery": "整個圖書館充滿古典氣息，但裝有現代科技裝置。陽光從彩色玻璃窗射入，在地板上形成二進位碼的圖案。",
            "memory_cues": ["每當看到黑白對比時，聯想到二進位的0和1", "看到電腦時，想像內部的電流如何表示數據"],
            "practice_routine": "每天睡前，在腦海中走過圖書館的每個區域，回顧每個關鍵錨點。每週實際寫出至少三個二進位轉換範例鞏固記憶。",
            "organized_content": "# 記憶宮殿：二進位系統與計算機基礎\\n\\n## 故事背景\\n想像一個古老的圖書館，每個書架代表一個重要概念...\\n\\n## 空間佈局\\n整個記憶宮殿是一座三層樓的圖書館..."
        }}
        **--- JSON 格式範例 END ---**

        請以 JSON 格式回傳，**必須**是有效的JSON結構，包含：
        {{
            "memory_story": "將所有概念編成一個有趣且連貫的故事",
            "spatial_layout": "描述想像的空間和遊覽路線",
            "key_anchors": [
                {{
                    "anchor": "錨點名稱1",
                    "content": "關聯的內容或概念",
                    "visual": "視覺想像描述"
                }},
                {{
                    "anchor": "錨點名稱2",
                    "content": "關聯的內容或概念",
                    "visual": "視覺想像描述"
                }}
            ],
            "visual_imagery": "生動的視覺想像描述",
            "memory_cues": ["記憶提示1", "提示2", "提示3"],
            "practice_routine": "記憶練習和復習建議",
            "organized_content": "記憶宮殿法整理的完整內容，包含故事、空間佈局和記憶技巧"
        }}

        請特別注意，`key_anchors` 必須是一個包含物件的陣列，每個物件都有 anchor、content 和 visual 三個屬性，如範例所示。
        
        要讓內容容易記憶和回憶，創造生動有趣的故事和視覺畫面。回傳的必須是有效的JSON格式。
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

    def generate_smart_note_content(self, context: Dict[str, Any]) -> str:
        """
        智能生成筆記內容，結合題目、答案、使用者內容和提示
        
        Args:
            context: 包含question_text, answer_text, user_content, user_prompt, title的字典
        
        Returns:
            生成的筆記內容（Markdown格式）
        """
        question_text = context.get('question_text', '')
        answer_text = context.get('answer_text', '')
        user_content = context.get('user_content', '').strip()
        user_prompt = context.get('user_prompt', '').strip()
        title = context.get('title', '')
        
        # 構建智能提示
        prompt = f"""
        我需要你為一道考試題目生成學習筆記。以下是相關資訊：

        題目：
        ---
        {question_text}
        ---

        標準答案：
        ---
        {answer_text}
        ---

        使用者現有筆記內容：
        ---
        {user_content if user_content else "（目前為空，請從零開始生成）"}
        ---

        {"使用者特別要求：" + user_prompt if user_prompt else ""}

        請生成一份完整且有價值的筆記內容，要求：

        1. **如果使用者已有內容**：
           - 保留並整合使用者的內容
           - 補充和完善現有內容
           - 修正可能的錯誤
           - 增加深度分析

        2. **如果使用者內容為空**：
           - 從零開始生成完整筆記
           - 包含題目分析、解題思路、知識點整理
           - 提供學習重點和記憶技巧

        3. **內容結構要求**：
           - 使用 Markdown 格式
           - 包含適當的標題層級
           - 使用列表、表格等增強可讀性
           - 加入 emoji 使內容更生動

        4. **知識深度**：
           - 不僅僅重述答案，要分析原理
           - 提供相關概念的解釋
           - 包含實際應用案例
           - 給出記憶口訣或技巧

        {"5. **特別注意**：" + user_prompt if user_prompt else ""}

        請直接回傳筆記內容，不要包含其他說明。
        """
        
        try:
            # 使用非同步呼叫獲取生成結果
            response = self._run_async(self.gemini_client.generate_content_async(prompt))
            return response
        except Exception as e:
            print(f"Error in smart content generation: {e}")
            # 返回基本結構作為備用
            return f"""# {title}

## 📚 題目分析
{question_text}

## ✅ 解答要點
{answer_text}

## 📝 學習筆記
{user_content if user_content else "請在此處添加您的學習心得和重點整理。"}

## 💡 重點提醒
- 仔細分析題目要求
- 理解解答的核心概念
- 關聯相關知識點

{f"## 🎯 特別注意\\n{user_prompt}" if user_prompt else ""}
"""

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
            
            # 確保格式化功能有有效的 organized_content
            if operation_type == "format_enhance" and not response_data.get('organized_content'):
                if response_data.get('formatted_content'):
                    response_data['organized_content'] = response_data['formatted_content']
                elif response_data.get('data'):
                    # 如果AI返回的是包裝在data中的內容
                    response_data['organized_content'] = str(response_data['data'])
                else:
                    response_data['organized_content'] = '格式化處理完成，但缺少整理後的內容。'
            
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

