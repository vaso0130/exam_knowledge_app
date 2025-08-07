
import os
import json
import asyncio
import re
from typing import Dict, List, Any, Optional

# Assuming the main Gemini client is in the core directory
from ..core.gemini_client import GeminiClient
from ..utils.json_parser import extract_json_from_text
from .lsp_bridge import LSPBridge

class NoteAIClient:
    """
    A dedicated AI client for handling all AI-related tasks for the notes system.
    It leverages the core GeminiClient for actual API communication.
    """
    def __init__(self):
        # Initialize the core Gemini client
        # This assumes API keys and other configurations are handled within GeminiClient
        self.gemini_client = GeminiClient()
        
        # 初始化LSP橋接模組（按需創建）
        self._lsp_bridge = None
        self._use_lsp = True  # 是否使用LSP處理
        
        # LSP支援的語言映射
        self._lsp_language_map = {
            'markdown': 'markdown',
            'python': 'python',
            'javascript': 'javascript',
            'java': 'java',
            'html': 'html',
            'css': 'css',
            'json': 'json',
            'sql': 'sql'
        }

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
                                return parsed_json
                        except json.JSONDecodeError as inner_e:
                            print(f"修復後JSON解析仍失敗: {inner_e}")
                            pass
            
            # 如果直接解析失敗，使用提取工具
            from ..utils.json_parser import extract_json_from_text
            extracted_json = extract_json_from_text(cleaned_response)
            if extracted_json and isinstance(extracted_json, dict):
                return extracted_json
            elif extracted_json and isinstance(extracted_json, list):
                return {
                    'data': extracted_json, 
                    'parsing_note': '解析到列表格式的數據'
                }
            
            # 嘗試從原始回應中提取有用信息
            if cleaned_response and len(cleaned_response.strip()) > 10:
                # 如果AI回應看起來像是結構化內容但不是JSON
                # 在調用 _extract_structured_content 之前，先確保它不是有效的JSON
                if not (cleaned_response.startswith('{') and cleaned_response.endswith('}')):
                    structured_content = self._extract_structured_content(cleaned_response)
                    if structured_content:
                        return structured_content
                    
                # 最後的備用：返回錯誤信息，不再生成organized_content
                return {
                    'error': 'JSON解析失敗，請重新生成',
                    'raw_response': raw_response,
                    'parsing_note': '無法解析為有效的JSON格式'
                }
            
            # 完全失敗的情況  
            return {
                'error': 'Failed to parse JSON response', 
                'raw_response': raw_response,
                'parsing_note': f'AI回應解析失敗。原始回應: {raw_response[:200]}...'
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'parsing_note': f'AI處理過程中發生錯誤: {str(e)}'
            }


    def _fix_common_json_issues(self, json_str: str) -> str:
        """修復常見的JSON格式問題"""
        try:
            # 移除多餘的逗號
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            # 修復缺失的逗號（在引號後面跟著換行和引號的情況）
            json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
            json_str = re.sub(r'"\s*\n\s*[a-zA-Z_][a-zA-Z0-9_]*":', '",\n"', json_str)
            
            # 修復單引號為雙引號
            json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
            json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
            
            # 修復未加引號的鍵
            json_str = re.sub(r'(\w+):', r'"\1":', json_str)
            
            # 修復缺失逗號的對象屬性（特別針對answers欄位）
            json_str = re.sub(r'"\s*(\n\s*"[^"]+":)', r'",\1', json_str)
            
            # 移除可能的重複逗號
            json_str = re.sub(r',,+', ',', json_str)
            
            return json_str
        except:
            return None

    def _extract_structured_content(self, text: str) -> Dict[str, Any]:
        """從非JSON格式的結構化文本中提取內容"""
        try:
            # 首先檢查是否看起來像JSON但解析失敗了
            text_stripped = text.strip()
            if (text_stripped.startswith('{') and text_stripped.endswith('}')) or (text_stripped.startswith('[') and text_stripped.endswith(']')):
                # 這看起來像JSON，不應該被當作Markdown處理
                # 但需要進一步確認是否真的是JSON格式
                try:
                    # 嘗試解析JSON以確認
                    json.loads(text_stripped)
                    # 如果成功解析，絕對不應該作為Markdown處理
                    return None
                except json.JSONDecodeError:
                    # 如果解析失敗，可能是格式不正確的JSON，繼續檢查是否是Markdown
                    pass
                
            # 如果文本包含明顯的結構標記，並且確定不是有效的JSON格式
            if ('**' in text or '##' in text or '1.' in text) and not (text_stripped.startswith('{') and text_stripped.endswith('}')):
                return {
                    'organized_content': text,
                    'content_type': 'markdown',
                    'parsing_note': '檢測到結構化文本，作為Markdown內容處理'
                }
            return None
        except:
            return None



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
        請將以下筆記內容轉換成心智圖的結構化 JSON 格式。這是一個嚴格的格式化任務，必須精確遵循規範。

        筆記內容：
        ---
        {content}
        ---

        **重要格式規範**：
        1. 你需要提供一個符合 ECharts 樹狀圖 (Tree Chart) 格式的 JSON
        2. JSON 中的 `mindmap_data` 必須是一個包含 `name` 和 `children` 的巢狀物件
        3. 每個節點都必須有 `name` 屬性，而 `children` 是可選的
        4. 節點名稱應簡潔明了，控制在20個字以內，避免過長文字
        5. 最終的樹結構應該水平均衡分佈，讓整體結構更加平衡美觀

        **--- JSON 格式範例 START ---**
        {{
            "central_topic": "雲端計算基礎",
            "main_branches": ["服務模式", "部署模型", "關鍵技術"],
            "mindmap_data": {{
                "name": "雲端計算基礎",
                "children": [
                    {{
                        "name": "服務模式",
                        "children": [
                            {{ 
                                "name": "SaaS", 
                                "children": [
                                    {{ "name": "即用即付" }},
                                    {{ "name": "無需本地安裝" }}
                                ]
                            }},
                            {{ 
                                "name": "PaaS",
                                "children": [
                                    {{ "name": "開發環境" }},
                                    {{ "name": "中介層服務" }}
                                ]
                            }},
                            {{ "name": "IaaS" }}
                        ]
                    }},
                    {{
                        "name": "部署模型",
                        "children": [
                            {{ "name": "公有雲" }},
                            {{ "name": "私有雲" }},
                            {{ "name": "混合雲" }}
                        ]
                    }},
                    {{
                        "name": "關鍵技術",
                        "children": [
                            {{ "name": "虛擬化" }},
                            {{ "name": "分佈式系統" }}
                        ]
                    }}
                ]
            }}
        }}
        **--- JSON 格式範例 END ---**

        請嚴格按照上述範例的 `mindmap_data` 結構生成 JSON。確保生成的心智圖結構均衡、清晰且組織合理，每個節點的名稱簡潔明瞭，不要太長或太複雜。
        """
        # 不再需要 mermaid_code，而是 mindmap_data
        return self._safe_ai_call(prompt, "mindmap", use_simple_model=True)

    def organize_hierarchically(self, content: str) -> Dict[str, Any]:
        """層次化重點整理"""
        prompt = f"""
        請將以下筆記內容按重要性和邏輯關係分層整理，製作成更易讀且結構化的格式。這是一個嚴格的資料結構化任務，你必須產生完全符合規格的 JSON 格式。

        筆記內容：
        ---
        {content}
        ---

        請回傳嚴格符合以下格式的 JSON 結構，這非常重要：
        {{
            "title": "整理後的標題",
            "main_points": ["重點1", "重點2", "重點3"],
            "sub_points": [
                {{
                    "title": "小節標題1",
                    "content": "該小節的詳細內容，支援 Markdown 格式"
                }},
                {{
                    "title": "小節標題2", 
                    "content": "該小節的詳細內容，支援 Markdown 格式"
                }}
            ],
            "key_concepts": [
                {{
                    "term": "概念名稱1",
                    "definition": "概念定義1"
                }},
                {{
                    "term": "概念名稱2",
                    "definition": "概念定義2"
                }}
            ],
            "learning_tips": "學習本主題的建議和技巧"
        }}

        嚴格規範：
        1. main_points 必須是一個字符串數組，每個元素為一個重點
        2. sub_points 必須是一個對象數組，每個對象必須包含 title 和 content 屬性
        3. key_concepts 必須是一個對象數組，每個對象必須包含 term 和 definition 屬性
        4. 所有字段都是必須的，不要省略任何字段
        5. 不允許添加額外的字段
        6. 確保 JSON 格式完全正確，不能有缺失的逗號或多餘的逗號
        7. 不要在 JSON 外添加任何額外的文字或標記

        請嚴格按照上述格式回傳 JSON，這對於前端正確顯示層次化筆記至關重要。
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

        請直接以以下 JSON 格式回傳，**必須**是完全符合以下的JSON結構：
        {{
            "simple_explanation": "用最簡單的語言解釋主要概念的內容",
            "analogies": ["類比1", "類比2", "類比3"],
            "step_by_step": ["步驟1說明", "步驟2說明", "步驟3說明"],
            "examples": ["具體例子1", "具體例子2"],
            "potential_gaps": ["可能的理解盲點1", "盲點2"],
            "teaching_points": ["教學重點1", "重點2", "重點3"]
        }}

        目標是讓程式可以完全處理這個JSON格式，所以請不要回傳多餘的東西。
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
            "learning_progression": "建議先從基礎問題開始，確保理解核心定義，然後進入中級問題進行應用練習，最後挑戰高級和批判性思考問題以深化理解。"
        }}
        **--- JSON 格式範例 END ---**

        請根據以下筆記內容生成類似上述範例的JSON輸出。回傳的必須是有效的JSON格式。

        筆記內容：
        ---
        {content}
        ---

        問題要有層次性，從簡單到複雜，幫助深度理解。
        
        **嚴格 JSON 格式要求**：
        回傳的必須是完全符合以下結構的有效 JSON 格式，不得有任何額外文字、說明或標記：
        
        {{
            "basic_questions": [
                "基礎問題1",
                "基礎問題2", 
                "基礎問題3",
                "基礎問題4",
                "基礎問題5"
            ],
            "intermediate_questions": [
                "中級問題1",
                "中級問題2",
                "中級問題3"
            ],
            "advanced_questions": [
                "高級問題1",
                "高級問題2"
            ],
            "critical_thinking": [
                "批判性思考問題1",
                "批判性思考問題2"
            ],
            "answers": {{
                "基礎問題1": "詳細答案1",
                "基礎問題2": "詳細答案2",
                "基礎問題3": "詳細答案3",
                "基礎問題4": "詳細答案4",
                "基礎問題5": "詳細答案5",
                "中級問題1": "詳細答案1",
                "中級問題2": "詳細答案2",
                "中級問題3": "詳細答案3",
                "高級問題1": "詳細答案1",
                "高級問題2": "詳細答案2",
                "批判性思考問題1": "詳細答案1",
                "批判性思考問題2": "詳細答案2"
            }},
            "learning_progression": "學習進度建議的內容"
        }}
        
        **重要提醒**：
        1. 確保 JSON 格式完全正確，所有引號、逗號、括號都正確配對
        2. answers 欄位必須包含所有問題的對應答案
        3. 每個問題的答案都要詳細且有價值
        4. 不要在 JSON 前後添加任何解釋、標記或多餘文字
        5. 回傳內容只能是純 JSON，不可包含其他任何內容
        6. 範例的題數只是範例，不代表每次都要生成出同樣題數的問答，可以多也可以少。
        """
        # 問答式學習：使用主模型（需要複雜的問題設計）
        result = self._safe_ai_call(prompt, "qa_learning", use_simple_model=False)
        
        # 使用輔助模型進行二次格式化和驗證
        if result.get('success', False) and not result.get('error'):
            result = self._post_process_qa_learning_result(result)
        
        return result

    def _post_process_qa_learning_result(self, qa_result: Dict[str, Any]) -> Dict[str, Any]:
        """對問答式學習結果進行驗證，只在必要時使用輔助模型修復"""
        try:
            # 如果原始結果成功且包含必要的結構化數據，直接返回
            if (qa_result.get('success') and 
                not qa_result.get('error') and
                qa_result.get('basic_questions') and
                qa_result.get('answers')):
                
                # 驗證數據完整性
                if self._validate_qa_structure(qa_result):
                    qa_result['post_processed'] = False  # 標記為未經後處理
                    qa_result['validation_note'] = '原始結果結構完整，直接使用'
                    return qa_result
            
            # 如果原始結果有問題但包含 organized_content，嘗試用輔助模型修復
            if (qa_result.get('success') and 
                qa_result.get('organized_content') and 
                not qa_result.get('basic_questions')):
                
                print("⚠️ 檢測到舊格式 organized_content，嘗試用輔助模型解析...")
                formatted_result = self._format_qa_content_with_ai(qa_result)
                if formatted_result.get('success'):
                    return formatted_result
                
            # 如果以上都失敗，返回原始結果
            return qa_result
            
        except Exception as e:
            print(f"後處理問答式學習結果時發生錯誤: {e}")
            return qa_result

    def _validate_qa_structure(self, qa_data: Dict[str, Any]) -> bool:
        """驗證問答式學習數據結構的完整性"""
        try:
            # 檢查必要欄位
            if not qa_data.get('basic_questions') or not qa_data.get('answers'):
                return False
                
            # 檢查基礎問題是否為列表且非空
            basic_questions = qa_data.get('basic_questions', [])
            if not isinstance(basic_questions, list) or len(basic_questions) == 0:
                return False
                
            # 檢查答案字典是否包含基礎問題的答案
            answers = qa_data.get('answers', {})
            if not isinstance(answers, dict):
                return False
                
            # 至少要有一些基礎問題的答案
            basic_answers_count = sum(1 for q in basic_questions if q in answers)
            if basic_answers_count == 0:
                return False
                
            return True
            
        except Exception:
            return False

    def _format_qa_content_with_ai(self, raw_qa_data: Dict[str, Any]) -> Dict[str, Any]:
        """使用輔助模型格式化問答式學習內容"""
        try:
            # 構建給AI的提示，要求其格式化和驗證問答內容
            format_prompt = f"""
            請將以下問答式學習內容格式化成標準的JSON格式。這是一個格式化任務，確保輸出符合規範。

            原始內容：
            ---
            {json.dumps(raw_qa_data, ensure_ascii=False, indent=2)}
            ---

            請回傳嚴格符合以下結構的 JSON 格式，**不得有任何額外文字或標記**：

            {{
                "basic_questions": [
                    "基礎問題1",
                    "基礎問題2",
                    "基礎問題3"
                ],
                "intermediate_questions": [
                    "中級問題1", 
                    "中級問題2"
                ],
                "advanced_questions": [
                    "高級問題1",
                    "高級問題2"
                ],
                "critical_thinking": [
                    "批判性思考問題1",
                    "批判性思考問題2"
                ],
                "answers": {{
                    "基礎問題1": "詳細答案1",
                    "基礎問題2": "詳細答案2",
                    "基礎問題3": "詳細答案3",
                    "中級問題1": "詳細答案1",
                    "中級問題2": "詳細答案2",
                    "高級問題1": "詳細答案1",
                    "高級問題2": "詳細答案2",
                    "批判性思考問題1": "詳細答案1",
                    "批判性思考問題2": "詳細答案2"
                }},
                "learning_progression": "學習進度建議"
            }}

            **格式化要求**：
            1. 確保所有問題都有對應的答案
            2. 移除任何無效或空白的問題
            3. 確保answers物件包含所有問題的答案
            4. 確保JSON格式完全正確，無語法錯誤
            5. 只回傳JSON，不要包含任何其他文字

            請處理並格式化上述內容。
            """
            
            # 使用輔助模型進行格式化（簡單的格式處理任務）
            formatted_response = self._run_async(
                self.gemini_client.generate_async_simple(format_prompt, is_json=True)
            )
            
            # 清理和解析回應
            cleaned_response = formatted_response.strip()
            
            # 移除可能的標記
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
            
            # 嘗試解析格式化後的JSON
            if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
                try:
                    formatted_data = json.loads(cleaned_response)
                    
                    # 驗證必要欄位
                    required_fields = ['basic_questions', 'answers']
                    if all(field in formatted_data for field in required_fields):
                        return {
                            **formatted_data,
                            'success': True,
                            'model_used': 'simple',
                            'post_processed': True,
                            'formatting_note': '已通過輔助模型二次格式化和驗證'
                        }
                except json.JSONDecodeError as e:
                    print(f"輔助模型格式化後的JSON解析失敗: {e}")
                    print(f"格式化後內容: {cleaned_response[:500]}...")
            
            # 格式化失敗，返回錯誤
            return {
                'error': 'AI格式化失敗',
                'success': False,
                'raw_formatted_response': cleaned_response[:500] + '...' if len(cleaned_response) > 500 else cleaned_response
            }
            
        except Exception as e:
            print(f"使用AI格式化問答內容時發生錯誤: {e}")
            return {
                'error': f'格式化過程發生錯誤: {str(e)}',
                'success': False
            }

    def organize_with_comparison(self, content: str) -> Dict[str, Any]:
        """對比分析整理 - 找出關鍵概念間的異同和關聯"""
        prompt = f"""
            請對以下筆記內容進行對比分析，找出關鍵概念間的異同點和關聯性。

            筆記內容：
            ---
            {content}
            ---

            請嚴格按照下方 JSON 格式範例回傳內容，**不得有任何多餘的文字或標記**，只允許回傳有效的 JSON 物件：

            **--- JSON 格式範例 START ---**
            {{
                "key_concepts": ["概念A", "概念B", "概念C"],
                "similarities": [
                "概念A與概念B都屬於資料結構，皆可用於資料儲存與檢索。",
                "三者皆可用於解決排序問題。"
                ],
                "differences": [
                "概念A是線性結構，概念B是樹狀結構。",
                "概念C支援多重父節點，A與B僅有單一父節點。"
                ],
                "relationships": [
                "概念A可視為概念B的特殊情況。",
                "概念C可與A或B結合應用於複雜場景。"
                ],
                "comparison_table": [
                {{
                    "項目": "結構類型",
                    "概念A": "線性",
                    "概念B": "樹狀",
                    "概念C": "圖狀"
                }},
                {{
                    "項目": "應用場景",
                    "概念A": "簡單資料儲存",
                    "概念B": "階層資料管理",
                    "概念C": "複雜關聯建模"
                }}
                ],
                "pros_and_cons": [
                {{
                    "concept": "概念A",
                    "pros": ["實作簡單", "存取速度快"],
                    "cons": ["彈性較低", "不適合複雜關聯"]
                }},
                {{
                    "concept": "概念B",
                    "pros": ["階層清楚", "易於擴展"],
                    "cons": ["搜尋效率依結構而異"]
                }},
                {{
                    "concept": "概念C",
                    "pros": ["彈性高", "可表現複雜關係"],
                    "cons": ["實作較複雜", "維護成本高"]
                }}
                ]
            }}
            **--- JSON 格式範例 END ---**

            請根據上述範例，**務必以相同結構的 JSON 格式回傳**，所有欄位皆為必填，不可省略或添加額外欄位。
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
            "practice_routine": "每天睡前，在腦海中走過圖書館的每個區域，回顧每個關鍵錨點。每週實際寫出至少三個二進位轉換範例鞏固記憶。"
        }}
        **--- JSON 格式範例 END ---**

        請**務必**以以下 JSON 格式回傳，**必須**是有效的JSON結構，包含：
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
            "practice_routine": "記憶練習和復習建議"
        }}

        請特別注意，`key_anchors` 必須是一個包含物件的陣列，每個物件都有 anchor、content 和 visual 三個屬性，如範例所示。
        
        要讓內容容易記憶和回憶，創造生動有趣的故事和視覺畫面。回傳的必須是有效的JSON格式，並且沒有其他內容，好讓程式處理這個JSON。
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
           - `options`: 必須是陣列格式的4個選項 ["選項1", "選項2", "選項3", "選項4"]
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
        # 檢查是否是從題庫連結過來的筆記生成請求
        if 'question_text' in context:
            return self._generate_smart_note_from_question(context)
        else:
            # 普通筆記生成請求
            return self._generate_smart_note_without_question(context)
            
    def _generate_smart_note_from_question(self, context: Dict[str, Any]) -> str:
        """從題目生成筆記（用於題庫連結過來的筆記）"""
        question_text = context.get('question_text', '')
        answer_text = context.get('answer_text', '')
        user_content = context.get('user_content', '').strip()
        user_prompt = context.get('user_prompt', '').strip()
        title = context.get('title', '')
        
        # 構建智能提示 - 強化版本，確保生成更有價值的內容
        prompt = f"""
        你是一位頂尖的學習輔助 AI，你的任務是為使用者創建一份專業、深入且結構清晰的學習筆記。

        # 原始資訊

        ## 筆記標題:
        {title}

        ## 題目:
        ```
        {question_text}
        ```

        ## 標準答案:
        ```
        {answer_text}
        ```

        ## 使用者已有的筆記內容:
        ```
        {user_content if user_content else "（使用者尚未提供筆記內容）"}
        ```
        
        {"## 使用者特別要求:\n" + user_prompt if user_prompt else ""}


        請生成一份完整且有價值的筆記內容，以下是嚴格要求：

        1. **不要直接複製題目和答案**：
           - 請對原始內容進行深入分析和重新詮釋
           - 用自己的語言解釋概念和原理
           - 添加更多背景知識和相關聯的重要概念
           - 將知識點融入更廣泛的學科框架中

        2. **如果使用者已有內容**：
           - 保留並整合使用者的內容
           - 顯著補充和完善現有內容
           - 修正可能的錯誤或不準確之處
           - 增加深度分析和關聯知識

        3. **如果使用者內容為空**：
           - 從零開始生成完整筆記
           - 提供完整的知識框架和脈絡
           - 添加實用的學習技巧和方法
           - 分析題目背後的核心概念和原理

        4. **高質量內容結構**：
           - 使用清晰的 Markdown 層次結構
           - 創建多層次標題，從主題到細節
           - 使用列表、表格等增強可讀性
           - 適當使用 emoji 增加視覺提示
           - 加入摘要和重點提示框

        5. **提升知識深度**：
           - 分析題目背後的核心概念和原理
           - 解釋相關術語和重要定義
           - 提供多角度理解和不同觀點
           - 包含實際應用案例和範例
           - 加入記憶技巧和關聯方法

        6. **進階學習策略**：
           - 提供解決類似問題的方法論
           - 添加擴展閱讀和進階學習路徑
           - 設計自我測試問題或練習
           - 加入與其他相關知識的連結
        
        {"7. **特別注意使用者要求**：" + user_prompt if user_prompt else "7. **學習效率提升**：\n           - 加入適合的圖示和視覺提示\n           - 設計自我測試的問題\n           - 提供記憶口訣和助記技巧"}

        重要提醒：
        1. 請直接創建完整的筆記內容，不要包含任何前言、說明或解釋
        2. 不要只是簡單地複製題目和答案，要創造有實質增值的學習內容
        3. 使用適合學習的格式，包括標題、列表、表格等
        4. 內容必須既全面又深入，能真正幫助學習者掌握知識

        # 任務指示

        請根據以上「原始資訊」與要求還有提醒，生成一份完整的 Markdown 格式筆記。
        **你的輸出必須嚴格遵循以下「筆記結構」，並用深入、原創的內容填充所有區塊。不要包含任何引言或額外的解釋。**

        ---

        # 筆記結構 (你的最終輸出)

        # 「 」學習筆記 (加入你覺得適合的標題 例如：「氣泡排序法」學習筆記）
        

        ## 📚 知識背景與脈絡
        [在此處分析並列出本題涵蓋的核心知識點，並簡要說明它們在整個學科中的位置和重要性。]

        ## 📝 學習筆記 
        [**這部分最重要**：如果使用者提供了現有筆記，請在此處保留、整合並大幅擴充其內容，修正可能的錯誤。如果沒有，請從零開始生成一份詳盡的筆記內容，包含定義、範例和深入說明。]
        
        {user_content if user_content else "[從零開始生成一份詳盡的筆記內容...]"}

        ## 🧠 記憶技巧與擴展學習
        [提供 2-3 個有創意的記憶技巧（如口訣、類比）或擴展學習的建議（如相關主題、推薦閱讀）。]
        - **記憶技巧**: [例如：將公式與一個有趣的故事連結...]
        - **擴展學習**: [例如：這個概念與『另一主題』有關，可以進一步研究...]

        ## 🔍 概念剖析

        ### 核心概念
        [在此處用你自己的話，深入解釋題目背後的核心概念和原理，不要只是複製題目文字。]

        ### 解答要點
        [在此處詳細闡述答案的邏輯和步驟，並解釋為什麼這是正確的答案，不要只是複製答案文字。]

        ## 💡 思路與方法
        [在此處提供針對此類問題的具體、思考框架。]

        ## 📌 重點整理
        [創建一個 Markdown 表格，整理出最重要的 2-3 個知識點。]
        | 知識點 | 重要性 | 常見考點 |
        |---|---|---|
        | [知識點1] | [用 1-5 顆 ⭐ 評估] | [說明這個知識點的常見考法或易錯點] |
        | [知識點2] | [用 1-5 顆 ⭐ 評估] | [說明這個知識點的常見考法或易錯點] |


        """
        
        try:
            # 使用非同步呼叫獲取生成結果 - 修正為正確的方法名稱
            response = self._run_async(self.gemini_client.generate_async(prompt, is_json=False))
            return response
        except Exception as e:
            print(f"Error generating smart note content: {e}")
            # 如果AI生成失敗，返回一個基本的模板
            return f"生成失敗: {str(e)}"

    def _generate_smart_note_without_question(self, context: Dict[str, Any]) -> str:
        """
        智能生成筆記內容，結合使用者現有內容和提示（適用於新建筆記）
        
        Args:
            context: 包含 user_content, user_prompt, title 的字典
        
        Returns:
            生成的筆記內容（Markdown格式）
        """
        user_content = context.get('user_content', '').strip()
        user_prompt = context.get('user_prompt', '').strip()
        title = context.get('title', '')
        
        # 如果使用者沒有提供任何內容，則無法生成
        if not user_content:
            return "請先提供一些筆記內容，AI才能幫助優化和擴充您的筆記。"
        
        # 構建智能提示 - 專為已有筆記內容設計
        prompt = f"""
        你是一位頂尖的學習輔助 AI，你的任務是幫助使用者優化和擴充現有的筆記內容。

        # 原始資訊

        ## 筆記標題:
        {title}

        ## 使用者現有的筆記內容:
        ```
        {user_content}
        ```
        
        {"## 使用者特別要求:\n" + user_prompt if user_prompt else ""}

        請基於使用者的現有內容，生成一份完整且有價值的筆記，以下是嚴格要求：

        1. **優化現有內容**：
           - 保留使用者的原始觀點和結構
           - 修正可能的錯誤或不準確之處
           - 改善文字表達和邏輯流程
           - 補充缺失的背景知識和細節
           
        2. **擴充筆記深度**：
           - 添加相關的學術背景和理論基礎
           - 提供更多專業術語和解釋
           - 補充實用的例子和應用場景
           - 加入不同觀點或方法的比較
           
        3. **提升筆記結構**：
           - 優化 Markdown 層次結構
           - 使用適當的標題層級組織內容
           - 添加列表、表格等增強可讀性
           - 適當使用 emoji 增加視覺提示
           
        4. **增強學習價值**：
           - 添加記憶技巧和學習方法
           - 設計自我測試問題
           - 提供延伸閱讀建議
           - 關聯其他相關知識領域
           
        {"5. **特別注意使用者要求**：" + user_prompt if user_prompt else "5. **進階學習資源**：\n           - 提供進階學習的建議\n           - 設計思考問題\n           - 建議實踐或應用方向"}

        重要提醒：
        1. 請直接創建完整的筆記內容，不要包含任何前言、說明或解釋
        2. 保留使用者原有筆記的核心內容和觀點，在此基礎上優化和擴充
        3. 使用適合學習的格式，包括標題、列表、表格等
        4. 內容必須既全面又深入，能真正幫助學習者掌握知識

        # 任務指示

        請根據以上「原始資訊」與要求還有提醒，生成一份完整的 Markdown 格式筆記。
        **你的輸出必須嚴格遵循以下「筆記結構」，並用深入、原創的內容填充所有區塊。不要包含任何引言或額外的解釋。**

        ---

        # 筆記結構 (你的最終輸出)

        # 「{title}」學習筆記

        ## 📚 核心知識與背景
        [在此部分，總結和擴展筆記主題的核心知識點和學科背景]

        ## 📝 增強學習筆記 
        [**這部分最重要**：保留並擴充使用者的現有筆記內容。確保原始觀點保留，同時補充相關知識、修正可能的不準確之處。]
        
        {user_content}

        ## 🔍 深入分析
        [在此部分，提供更深入的概念解析、原理說明或方法論]
        
        ## 💡 應用與實踐
        [在此部分，提供實際應用案例、操作步驟或實踐建議]

        ## 🧠 學習技巧與擴展
        [提供 2-3 個記憶技巧、學習方法或相關資源]
        - **記憶技巧**: [提供具體的記憶方法]
        - **擴展學習**: [建議相關主題或資源]
        
        ## 📌 重點整理
        [創建一個表格，總結筆記中的關鍵點]
        | 關鍵概念 | 重要性 | 應用場景 |
        |---|---|---|
        | [概念1] | [用 1-5 顆 ⭐ 評估] | [說明適用場景] |
        | [概念2] | [用 1-5 顆 ⭐ 評估] | [說明適用場景] |
        """
        
        try:
            # 使用非同步呼叫獲取生成結果
            response = self._run_async(self.gemini_client.generate_async(prompt, is_json=False))
            return response
        except Exception as e:
            print(f"Error in smart content generation: {e}")
            # 返回增強版的基本結構作為備用
            return f"""# {title} - 學習筆記

## 📚 知識背景與脈絡

這個題目涉及的核心知識點包括：
- 待補充...
- 待補充...

## 🔍 概念剖析

### 核心概念
- 待補充...

### 相關定義
- 待補充...

## 💡 解題思路與方法

1. 首先理解問題的關鍵點
2. 分析可能的解題策略
3. 應用相關知識點
4. 驗證結果的正確性

## 📌 重點整理

| 知識點 | 重要性 | 常見考點 |
|-------|------|--------|
| 待補充... | ⭐⭐⭐ | 待補充... |
| 待補充... | ⭐⭐ | 待補充... |

## 📝 學習筆記
{user_content if user_content else "在這裡記錄您的學習心得和重點整理。"}

## 🧠 記憶技巧

- 待補充...
- 待補充...

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

    # === AI 文字偵測功能 ===

    def detect_and_suggest_text(self, content: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        AI文字偵測 - 即時分析用戶輸入的文字內容並提供智慧建議
        實現類似 VS Code IntelliSense 的即時建議功能，基於語言伺服器協議(LSP)概念設計
        
        首先嘗試使用外部LSP伺服器處理，如果失敗或不可用則降級為AI處理
        
        Args:
            content: 用戶輸入的文字內容
            context: 額外的上下文信息（如筆記標題、已有內容等）
        
        Returns:
            包含各種建議的字典
        """
        # 如果內容太短，不進行分析
        if not content or len(content.strip()) < 10:
            return {
                'suggestions': [],
                'has_suggestions': False,
                'analysis_note': '內容太短，無需分析'
            }
        
        # 獲取上下文信息
        note_title = context.get('title', '') if context else ''
        existing_content = context.get('existing_content', '') if context else ''
        content_type = context.get('content_type', '') if context else ''
        use_ai_only = context.get('use_ai_only', False) if context else False
        
        # 自動檢測內容類型並選擇對應的處理器
        detected_language = self._detect_code_language(content)
        
        # 是否優先使用LSP處理
        should_use_lsp = self._use_lsp and not use_ai_only
        
        # 如果應該優先使用LSP且內容類型合適
        if should_use_lsp and detected_language in self._lsp_language_map:
            try:
                # 嘗試使用LSP獲取診斷信息（非阻塞）
                lsp_diagnostics = self._run_async(
                    self._try_lsp_diagnostics(content, detected_language)
                )
                
                # 如果成功獲取LSP診斷結果
                if lsp_diagnostics:
                    # 將LSP診斷結果轉換為標準格式
                    result = {
                        'suggestions': [],
                        'quick_fixes': [],
                        'content_enhancements': [],
                        'diagnostics': [],
                        'has_suggestions': bool(lsp_diagnostics),
                        'analysis_timestamp': self._get_current_timestamp(),
                        'content_length': len(content),
                        'content_type': detected_language,
                        'model_used': f'lsp-{detected_language}'
                    }
                    
                    # 處理LSP診斷信息
                    for diag in lsp_diagnostics:
                        # 添加診斷信息
                        result['diagnostics'].append({
                            'severity': diag.get('severity', 'info'),
                            'message': diag.get('message', '未知問題'),
                            'position': f"第{diag.get('range', {}).get('start', {}).get('line', 0)+1}行"
                        })
                        
                        # 將診斷轉換為建議
                        if 'message' in diag:
                            result['suggestions'].append({
                                'type': '格式優化' if diag.get('severity') == 'warning' else '錯字修正',
                                'title': diag.get('message')[:30] + ('...' if len(diag.get('message', '')) > 30 else ''),
                                'description': diag.get('message', ''),
                                'priority': 'high' if diag.get('severity') == 'error' else 'medium',
                                'icon': 'structure' if '結構' in diag.get('message', '') else 'format'
                            })
                    
                    # 只有在LSP診斷結果較少時，才使用AI增強（避免重複信息）
                    if len(lsp_diagnostics) <= 2:
                        # 異步啟動AI分析以增強LSP結果（不等待結果）
                        asyncio.create_task(self._enhance_lsp_with_ai(content, context, result))
                    
                    return result
            except Exception as e:
                print(f"LSP處理失敗，降級為AI處理: {e}")
                # 繼續使用AI處理
        
        # 如果是 Markdown 內容，使用專門的 Markdown LSP
        if detected_language == 'markdown' or content_type == 'markdown':
            markdown_analysis = self.analyze_markdown_syntax(content)
            
            # 將 Markdown 分析結果轉換為統一格式
            result = {
                'suggestions': [],
                'quick_fixes': [],
                'content_enhancements': [],
                'diagnostics': markdown_analysis.get('diagnostics', []),
                'has_suggestions': markdown_analysis.get('has_issues', False),
                'analysis_timestamp': self._get_current_timestamp(),
                'content_length': len(content),
                'content_type': 'markdown',
                'model_used': 'simple-markdown-lsp'
            }
            
            # 處理建議
            for suggestion in markdown_analysis.get('suggestions', []):
                result['suggestions'].append({
                    'type': suggestion.get('type', '格式優化'),
                    'title': suggestion.get('label', '格式建議'),
                    'description': suggestion.get('description', ''),
                    'priority': 'medium',
                    'icon': 'format'
                })
                
                # 如果有具體的修改建議，添加為快速修復
                if 'suggested_change' in suggestion:
                    result['quick_fixes'].append({
                        'issue': suggestion.get('label', '格式問題'),
                        'fix': '應用建議的修改',
                        'original': '(需要選擇具體文本)',
                        'suggested': suggestion.get('suggested_change', '')
                    })
            
            # 添加結構相關的內容增強建議
            if 'structure' in markdown_analysis:
                structure_issues = []
                for struct in markdown_analysis.get('structure', []):
                    if struct.get('type') == 'heading' and struct.get('level') > 1:
                        structure_issues.append({
                            'suggestion': f"檢查標題「{struct.get('text', '')}」的層級結構",
                            'reason': "確保文檔標題層級有清晰的階層關係"
                        })
                
                if structure_issues:
                    result['content_enhancements'].extend(structure_issues)
            
            return result
            
        # 如果是程式碼內容，使用程式碼 LSP
        elif detected_language in ['python', 'javascript', 'java', 'c', 'sql', 'html', 'code']:
            code_analysis = self.analyze_code_syntax(content, detected_language)
            
            # 將程式碼分析結果轉換為統一格式
            result = {
                'suggestions': [],
                'quick_fixes': [],
                'content_enhancements': [],
                'diagnostics': code_analysis.get('diagnostics', []),
                'has_suggestions': code_analysis.get('has_issues', False),
                'analysis_timestamp': self._get_current_timestamp(),
                'content_length': len(content),
                'content_type': detected_language,
                'model_used': f'simple-{detected_language}-lsp'
            }
            
            # 處理建議
            for suggestion in code_analysis.get('suggestions', []):
                result['suggestions'].append({
                    'type': '程式碼優化',
                    'title': suggestion.get('label', '程式碼建議'),
                    'description': suggestion.get('detail', ''),
                    'priority': 'high',
                    'icon': 'structure'
                })
                
                # 如果有具體的修改建議，添加為快速修復
                if 'insertText' in suggestion:
                    result['quick_fixes'].append({
                        'issue': suggestion.get('label', '程式碼問題'),
                        'fix': '應用建議的修改',
                        'original': '(需要選擇具體代碼)',
                        'suggested': suggestion.get('insertText', '')
                    })
            
            return result
        
        # 一般文本內容使用通用 LSP
        else:
            # 使用更精簡的提示詞，專注於LSP功能
            prompt = f"""
            你是一個高效智慧筆記助手，實現類似 VS Code 的 LSP (Language Server Protocol) 功能。
            請分析用戶輸入的文字內容，並依照以下功能提供即時智慧建議：

            1. 即時語法解析與錯誤檢測 - 檢查文本格式、語法問題
            2. 智慧補全 - 提供內容完善的建議
            3. 語意理解 - 基於上下文提供相關內容建議

            當前筆記標題：{note_title}
            
            用戶正在輸入的文字：
            ---
            {content}
            ---
            
            {f"筆記現有內容：\\n---\\n{existing_content}\\n---" if existing_content else ""}

            請以 JSON 格式提供以下類型的建議：

            {{
                "suggestions": [
                    {{
                        "type": "格式優化|錯字修正|內容補強|結構建議|智慧補全",
                        "title": "簡短建議標題",
                        "description": "具體建議內容",
                        "priority": "high|medium|low",
                        "icon": "format|spell|structure|content"
                    }}
                ],
                "quick_fixes": [
                    {{
                        "issue": "發現的問題",
                        "fix": "修正建議",
                        "original": "原始文字",
                        "suggested": "建議文字"
                    }}
                ],
                "content_enhancements": [
                    {{
                        "suggestion": "內容增強建議",
                        "reason": "建議原因"
                    }}
                ],
                "diagnostics": [
                    {{
                        "severity": "error|warning|info",
                        "message": "診斷訊息",
                        "position": "問題位置描述"
                    }}
                ],
                "has_suggestions": true
            }}
            
            請保持回應簡潔、實用，只提供確實有幫助的建議。務必確保所有JSON欄位格式正確。
            """
            
            try:
                # 確保使用輔助模型進行快速分析
                response_data = self._run_async(
                    self.gemini_client.generate_async_simple(prompt, is_json=True)
                )
                
                # 清理和解析回應
                if isinstance(response_data, str):
                    response_data = self._parse_detection_response(response_data)
                
                # 確保回應格式正確
                if not isinstance(response_data, dict):
                    return {
                        'suggestions': [],
                        'has_suggestions': False,
                        'analysis_note': '暫無建議'
                    }
                
                # 簡化檢查邏輯
                has_suggestions = bool(response_data.get('suggestions') or 
                                       response_data.get('quick_fixes') or 
                                       response_data.get('content_enhancements') or 
                                       response_data.get('diagnostics'))
                
                # 更新has_suggestions欄位
                response_data['has_suggestions'] = has_suggestions
                
                # 添加元數據
                response_data['analysis_timestamp'] = self._get_current_timestamp()
                response_data['content_length'] = len(content)
                response_data['content_type'] = 'text'
                response_data['model_used'] = 'simple'
                
                return response_data
                
            except Exception as e:
                print(f"AI文字偵測錯誤: {e}")
                return {
                    'suggestions': [],
                    'has_suggestions': False,
                    'analysis_note': f'分析時發生錯誤: {str(e)}'
                }

    def _parse_detection_response(self, response_text: str) -> Dict[str, Any]:
        """解析AI文字偵測的回應文字，使用更簡潔的邏輯"""
        try:
            # 清理回應文字
            cleaned_response = response_text.strip()
            
            # 移除可能的標記 - 簡化邏輯
            if cleaned_response.startswith('```json') or cleaned_response.startswith('```JSON'):
                cleaned_response = cleaned_response[7:].strip()
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:].strip()
                
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3].strip()
            
            # 嘗試解析JSON
            if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
                import json
                try:
                    return json.loads(cleaned_response)
                except json.JSONDecodeError:
                    pass
            
            # 解析失敗時返回空結構 - 直接返回而非使用另一函數
            return {
                'suggestions': [],
                'has_suggestions': False,
                'analysis_note': '解析回應失敗'
            }
            
        except Exception as e:
            return {
                'suggestions': [],
                'has_suggestions': False,
                'analysis_note': f'解析回應發生錯誤: {str(e)}'
            }

    def _get_current_timestamp(self) -> str:
        """獲取當前時間戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

    def generate_content_enhancement(self, enhancement_request: str, current_content: str, title: str = "", context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        根據增強建議生成實際內容
        
        Args:
            enhancement_request: 增強建議的描述
            current_content: 目前的筆記內容  
            title: 筆記標題
            context: 額外的上下文資訊
            
        Returns:
            包含生成內容的字典
        """
        try:
            context = context or {}
            
            # 特殊關鍵字處理 - 直接返回常見術語的定義
            special_keywords = {
                "CIA": "# CIA 三要素 (機密性、完整性、可用性)\n\n**機密性 (Confidentiality)**: 確保資訊只能被授權的人員訪問和使用，防止未經授權的資訊披露。\n\n**完整性 (Integrity)**: 保護資料不被未經授權的修改，確保資訊的正確性和可靠性。\n\n**可用性 (Availability)**: 確保資訊系統及其資源對授權使用者的即時可用性，防止服務中斷。",
                "CIA三要素": "# CIA 三要素 (機密性、完整性、可用性)\n\n**機密性 (Confidentiality)**: 確保資訊只能被授權的人員訪問和使用，防止未經授權的資訊披露。保護方式包括：加密、訪問控制、身分驗證等。\n\n**完整性 (Integrity)**: 保護資料不被未經授權的修改，確保資訊的正確性和可靠性。保護方式包括：雜湊函數、數位簽章、存取控制等。\n\n**可用性 (Availability)**: 確保資訊系統及其資源對授權使用者的即時可用性，防止服務中斷。保護方式包括：備援系統、容災設計、分散式架構等。",
                "CPR": "# CPR 資訊安全三原則\n\n**機密性 (Confidentiality)**: 確保資訊只能被授權的人員訪問和使用，防止資料洩漏。\n\n**隱私性 (Privacy)**: 保護個人敏感資訊不被不當收集、使用或分享。\n\n**可靠性 (Reliability)**: 確保系統和資料的穩定性、一致性和可靠性。",
                "AAA": "# AAA 安全框架\n\n**認證 (Authentication)**: 驗證使用者身分的過程，確保系統知道「你是誰」。常見方式包括：\n- 密碼認證\n- 生物辨識\n- 多因素認證\n\n**授權 (Authorization)**: 確定使用者能夠訪問哪些資源的過程，即「你能做什麼」。實現方式包括：\n- 訪問控制清單 (ACL)\n- 角色型訪問控制 (RBAC)\n- 屬性型訪問控制 (ABAC)\n\n**稽核 (Accounting)**: 記錄使用者在系統中的活動，即「你做了什麼」。重要內容包括：\n- 系統日誌\n- 行為分析\n- 異常偵測",
                "CERT": "# CERT (Computer Emergency Response Team)\n\n**完整英文全名**: Computer Emergency Response Team\n\n**中文意義**: 電腦緊急應變小組\n\n**定義與重要性**:\nCERT是組織內部或國家級別設立的專門機構，負責處理資安事件和漏洞，協調網路安全事件的應對措施。\n\n**主要職責**:\n1. **事件回應** - 應對網路安全威脅和攻擊\n2. **漏洞管理** - 識別、分析和協調漏洞修復\n3. **安全警報** - 發布威脅情報和安全公告\n4. **教育培訓** - 提高組織的安全意識\n5. **事件協調** - 與其他機構協作應對大規模事件",
                "PDCA": "# PDCA 循環 (Plan-Do-Check-Act)\n\n**完整英文全名**: Plan-Do-Check-Act Cycle (又稱為戴明循環 Deming Cycle)\n\n**中文意義**: 計劃-執行-檢查-行動循環\n\n**定義與重要性**:\nPDCA是一種持續改進的管理方法，廣泛應用於品質管理、資訊安全管理和業務流程改進。\n\n**四個階段**:\n1. **計劃 (Plan)** - 識別問題並制定解決方案\n2. **執行 (Do)** - 實施計劃並收集資料\n3. **檢查 (Check)** - 評估結果並識別差距\n4. **行動 (Act)** - 採取措施解決差距並改進",
                "RADIUS": "# RADIUS (Remote Authentication Dial-In User Service)\n\n**完整英文全名**: Remote Authentication Dial-In User Service\n\n**中文意義**: 遠端使用者撥號驗證服務\n\n**定義與重要性**:\nRADIUS是一種網路協定，用於提供集中式的AAA(認證、授權和稽核)管理，特別是用於網路裝置和遠端存取場景。\n\n**主要特點**:\n1. **集中式管理** - 在單一伺服器上管理所有用戶的認證資訊\n2. **客戶端/伺服器架構** - 使用UDP協定，預設端口為1812(認證)和1813(稽核)\n3. **可擴展性** - 支援多種認證方法，包括PAP、CHAP、EAP等\n4. **代理功能** - 可以將請求轉發到其他RADIUS伺服器",
                "TACACS+": "# TACACS+ (Terminal Access Controller Access-Control System Plus)\n\n**完整英文全名**: Terminal Access Controller Access-Control System Plus\n\n**中文意義**: 終端存取控制器存取控制系統增強版\n\n**定義與重要性**:\nTACACS+是一種網路安全協定，提供集中式的AAA(認證、授權和稽核)服務，主要用於管理網路設備存取。它是思科開發的，基於較早的TACACS協定進行了顯著增強。\n\n**主要特點**:\n1. **分離的AAA架構** - 獨立處理認證、授權和稽核功能\n2. **TCP傳輸** - 使用可靠的TCP協定(端口49)，而非UDP\n3. **加密連線** - 對整個封包內容進行加密，而非僅加密密碼\n4. **精細的授權控制** - 可以實現命令級別的授權"
            }
            
            for keyword, content in special_keywords.items():
                if keyword.lower() in enhancement_request.lower():
                    return {
                        'generated_content': content,
                        'success': True,
                        'model_used': 'predefined'
                    }
            
            # 構建提示詞 - 強化版，特別加強對特定術語的解釋能力
            prompt = f"""
作為一個專業的資訊科技教育內容寫作專家，請根據以下資訊生成高質量的內容增強：

**筆記標題：** {title}

**目前內容：**
{current_content}

**增強要求：** {enhancement_request}

**任務：**
請根據增強要求，生成具體的、實用的內容來增強這篇筆記。

**內容要求：**
1. 生成的內容應該直接有用，而不是重複增強要求的描述
2. 內容應該與現有筆記內容相關且互補
3. 使用適當的Markdown格式（標題、粗體、列表等）
4. 內容應該具有教育價值和實用性
5. 根據上下文調整內容的深度和風格

**特別注意：**
如果涉及以下術語的定義和解釋，請務必提供完整、正確的資訊：
- 如果是「CIA三要素」：詳細解釋機密性(Confidentiality)、完整性(Integrity)和可用性(Availability)
- 如果是「資安相關概念」：提供清晰的定義、應用場景和實施方法
- 如果是「網路協議」：解釋其運作原理、特點和常見應用
- 如果是「程式設計模式」：提供定義、使用案例和示例代碼
- 如果是「資料庫概念」：解釋其原理、使用情境和最佳實踐

**輸出格式：**
直接輸出生成的內容，使用適當的Markdown格式，不需要其他說明。

請開始生成：
"""

            # 直接使用輔助模型生成內容（提高速度）
            specific_prompt = f"""
請為以下筆記內容生成具體的增強內容（至少150字）：

現有內容：{current_content[:300]}...

增強要求：{enhancement_request}

請確保：
1. 提供具體的技術內容，不要空泛的描述
2. 如果涉及縮寫詞（如CIA、CPR等），提供完整名稱和定義
3. 如果是技術概念，提供定義、特點和應用場景
4. 使用Markdown格式增強可讀性
5. 盡量簡潔明瞭，專注於重要資訊

請直接生成內容，不需要前言或標題：
"""
            
            try:
                # 只使用輔助模型，確保速度
                response = self._run_async(
                    self.gemini_client.generate_async_simple(specific_prompt, is_json=False)
                )
                
                if response and len(response.strip()) > 50:
                    return {
                        'generated_content': response.strip(),
                        'success': True,
                        'model_used': 'simple'
                    }
            except Exception as inner_e:
                print(f"輔助模型生成失敗: {inner_e}")
            
            # 如果專門處理某些特定的常見要求
            special_terms = ["CIA", "CIA三要素", "CPR", "AAA", "CERT", "PDCA", "RADIUS", "TACACS+"]
            for term in special_terms:
                if term.upper() in enhancement_request.upper():
                    return {
                        'generated_content': special_keywords.get(term, special_keywords.get("CIA")),  # 預設是CIA
                        'success': True,
                        'model_used': 'predefined'
                    }
            
            # 如果都失敗，返回預設的增強內容
            fallback_content = self._get_fallback_enhancement(enhancement_request)
            return {
                'generated_content': fallback_content,
                'success': True,
                'model_used': 'fallback'
            }
            
        except Exception as e:
            print(f"內容增強生成錯誤: {e}")
            # 嘗試返回預設內容而不是原始建議
            fallback_content = self._get_fallback_enhancement(enhancement_request)
            return {
                'generated_content': fallback_content,
                'success': True,
                'model_used': 'error_fallback',
                'error': str(e)
            }
    
    def _get_fallback_enhancement(self, request: str) -> str:
        """返回預設的增強內容，根據請求類型提供不同的預設內容"""
        if "CIA" in request.upper():
            return """# CIA 三要素 (機密性、完整性、可用性)

**機密性 (Confidentiality)**
- 定義：確保資訊只能被授權的人員訪問和使用
- 實現方式：加密、訪問控制、身分驗證
- 威脅：竊聽、社交工程、未授權訪問

**完整性 (Integrity)**
- 定義：保護資料不被未經授權的修改，確保資訊的正確性和可靠性
- 實現方式：雜湊函數、數位簽章、存取控制
- 威脅：中間人攻擊、資料竄改、惡意軟體

**可用性 (Availability)**
- 定義：確保資訊系統及其資源對授權使用者的即時可用性，防止服務中斷
- 實現方式：備援系統、容災設計、分散式架構
- 威脅：DDoS攻擊、硬體故障、自然災害

CIA是資訊安全風險評估和安全控制設計的基本框架，任何資安策略都應該考慮這三個面向。"""
        elif "CPR" in request.upper():
            return """# CPR 資訊安全三原則

**機密性 (Confidentiality)**
- 定義：確保資訊只能被授權的人員訪問和使用，防止資料洩漏
- 控制措施：加密、最小權限原則、資料分類

**隱私性 (Privacy)**
- 定義：保護個人敏感資訊不被不當收集、使用或分享
- 控制措施：隱私政策、資料匿名化、用戶同意機制

**可靠性 (Reliability)**
- 定義：確保系統和資料的穩定性、一致性和可靠性
- 控制措施：備份還原、異常檢測、高可用性設計

CPR框架特別適合處理含有個人資料的系統，尤其在符合GDPR等隱私法規要求時非常有用。"""
        elif "格式" in request or "markdown" in request.lower():
            return """# Markdown格式化指南

## 標題使用
使用`#`符號來建立標題：
```markdown
# 一級標題
## 二級標題
### 三級標題
```

## 文本格式化
- **粗體文字**：`**粗體文字**`
- *斜體文字*：`*斜體文字*`
- ~~刪除線~~：`~~刪除線~~`

## 列表格式
### 無序列表
```markdown
- 第一項
- 第二項
  - 子項目
  - 子項目
```

### 有序列表
```markdown
1. 第一步
2. 第二步
3. 第三步
```

## 程式碼格式
### 行內程式碼
使用反引號：`程式碼`

### 程式碼區塊
```python
def hello_world():
    print("Hello, World!")
```

## 表格格式
```markdown
| 欄位1 | 欄位2 | 欄位3 |
|-------|-------|-------|
| 資料1 | 資料2 | 資料3 |
| 資料4 | 資料5 | 資料6 |
```

## 引用
```markdown
> 這是一段引用文字
> 可以有多行
```

這些格式能讓您的筆記更有結構，提高可讀性。"""
        else:
            # 通用增強內容
            return f"""## {request}

很抱歉，無法為此增強請求生成詳細內容。以下是一些建議：

- 嘗試提供更具體的增強請求
- 確認您的筆記內容包含足夠的上下文
- 您可以手動添加相關內容，或重新嘗試其他增強類型

如果您是在尋找特定技術概念的定義或解釋，請在增強請求中明確指出該概念的名稱。
"""

    def analyze_code_syntax(self, content: str, language: str = None) -> Dict[str, Any]:
        """
        語言伺服器協議(LSP)功能 - 即時語法解析與錯誤檢測
        
        Args:
            content: 用戶輸入的代碼內容
            language: 代碼語言 (python, javascript, sql等)，如果為None則自動檢測
            
        Returns:
            包含診斷、建議和補全的字典
        """
        # 如果內容太短，不進行分析
        if not content or len(content.strip()) < 5:
            return {
                'diagnostics': [],
                'suggestions': [],
                'has_issues': False
            }
            
        # 自動檢測語言 (簡單實現)
        if not language:
            language = self._detect_code_language(content)
            
        # 構建提示詞
        prompt = f"""
你現在是一個高效能的語言伺服器(Language Server Protocol, LSP)，負責代碼分析。請分析以下{language}代碼：

```{language}
{content}
```

請以JSON格式提供以下分析結果：

{{
    "diagnostics": [
        {{
            "severity": "error|warning|info",
            "message": "診斷訊息",
            "line": 行號(整數),
            "character": 字元位置(整數),
            "code": "問題代碼",
            "source": "問題來源"
        }}
    ],
    "suggestions": [
        {{
            "type": "completion|refactor|format",
            "label": "建議標籤",
            "insertText": "建議插入的代碼",
            "detail": "詳細說明"
        }}
    ],
    "semanticTokens": [
        {{
            "type": "class|method|variable|keyword",
            "range": "代碼範圍描述",
            "name": "符號名稱"
        }}
    ],
    "has_issues": true|false
}}

注意：
- 僅報告實際的語法或邏輯問題
- 提供具體的修復建議
- 盡可能簡潔但要有足夠信息
- 僅關注代碼質量與功能性問題
"""

        try:
            # 使用輔助模型進行快速分析
            response_data = self._run_async(
                self.gemini_client.generate_async_simple(prompt, is_json=True)
            )
            
            # 清理和解析回應
            if isinstance(response_data, str):
                response_data = self._parse_detection_response(response_data)
            
            # 確保回應格式正確
            if not isinstance(response_data, dict):
                return {
                    'diagnostics': [],
                    'suggestions': [],
                    'has_issues': False
                }
            
            # 確保has_issues欄位正確
            has_issues = bool(response_data.get('diagnostics'))
            response_data['has_issues'] = has_issues
            
            # 添加元數據
            response_data['analysis_timestamp'] = self._get_current_timestamp()
            response_data['detected_language'] = language
            response_data['model_used'] = 'simple'
            
            return response_data
            
        except Exception as e:
            print(f"代碼分析錯誤: {e}")
            return {
                'diagnostics': [],
                'suggestions': [],
                'has_issues': False,
                'error': str(e)
            }
    
    def _get_lsp_bridge(self) -> Optional[LSPBridge]:
        """
        取得或初始化LSP橋接實例
        
        Returns:
            LSPBridge實例，如果無法初始化則返回None
        """
        if not self._use_lsp:
            return None
        
        if self._lsp_bridge is None:
            try:
                self._lsp_bridge = LSPBridge()
            except Exception as e:
                print(f"無法初始化LSP橋接: {e}")
                self._use_lsp = False
                return None
                
        return self._lsp_bridge
    
    async def _try_lsp_diagnostics(self, content: str, language: str) -> List[Dict[str, Any]]:
        """
        嘗試使用LSP獲取診斷信息
        
        Args:
            content: 要診斷的內容
            language: 內容的語言
            
        Returns:
            診斷結果列表，如果無法使用LSP則返回空列表
        """
        bridge = self._get_lsp_bridge()
        if not bridge:
            return []
        
        # 映射到LSP支援的語言
        lsp_language = self._lsp_language_map.get(language)
        if not lsp_language:
            return []
        
        # 檢查LSP可用性
        if not bridge.check_lsp_availability(lsp_language):
            return []
        
        try:
            # 獲取診斷信息
            diagnostics = await bridge.get_diagnostics(lsp_language, content)
            return diagnostics
        except Exception as e:
            print(f"LSP診斷錯誤: {e}")
            return []
    
    def _detect_code_language(self, content: str) -> str:
        """嘗試根據內容特徵自動檢測程式語言"""
        content_lower = content.lower()
        
        # 簡單的語言檢測邏輯
        if any(kw in content_lower for kw in ['def ', 'import ', 'class ', ':', 'self.', '__init__']):
            return 'python'
        elif any(kw in content_lower for kw in ['function', 'var ', 'const ', 'let ', '=>', 'document.']):
            return 'javascript'
        elif any(kw in content_lower for kw in ['select ', 'from ', 'where ', 'insert into', 'update ', 'delete from']):
            return 'sql'
        elif any(kw in content_lower for kw in ['#include', 'int ', 'void ', 'char ', 'return 0;']):
            return 'c'
        elif any(kw in content_lower for kw in ['public class', 'private', 'protected', 'void ', 'String']):
            return 'java'
        elif any(kw in content_lower for kw in ['<!DOCTYPE', '<html>', '<div', '<p>', '<script']):
            return 'html'
        elif any(kw in content_lower for kw in ['#', '##', '###', '- ', '* ', '```', '|', '> ']):
            return 'markdown'
        elif any(kw in content_lower for kw in ['{', '}', ';', 'interface ', 'namespace ']):
            # 如果有C系語言特徵但找不到具體是哪種，就當作泛用程式碼處理
            return 'code'
        else:
            return 'text'
            
    def analyze_markdown_syntax(self, content: str) -> Dict[str, Any]:
        """
        為 Markdown 實現的 LSP (Language Server Protocol) 功能
        基於 unified-language-server 的概念，提供 Markdown 專用的語法分析和建議
        
        Args:
            content: 用戶輸入的 Markdown 內容
            
        Returns:
            包含診斷、建議和補全的字典
        """
        # 如果內容太短，不進行分析
        if not content or len(content.strip()) < 10:
            return {
                'diagnostics': [],
                'suggestions': [],
                'has_issues': False
            }
        
        # 構建針對 Markdown 的提示詞
        prompt = f"""
你現在是一個專門處理 Markdown 的語言伺服器(Language Server Protocol, LSP)，負責分析以下 Markdown 文本：

```markdown
{content}
```

請以JSON格式提供以下分析結果：

{{
    "diagnostics": [
        {{
            "severity": "error|warning|info",
            "message": "診斷訊息",
            "line": 行號(整數),
            "position": "問題位置描述",
            "rule": "問題規則名稱"
        }}
    ],
    "suggestions": [
        {{
            "type": "format|structure|reference|content",
            "label": "建議標籤",
            "description": "詳細說明",
            "suggested_change": "建議的修改"
        }}
    ],
    "structure": [
        {{
            "type": "heading|list|blockquote|codeblock|table",
            "level": 層級(整數，僅用於標題),
            "line": 行號(整數),
            "text": "內容摘要"
        }}
    ],
    "has_issues": true|false
}}

請特別關注以下 Markdown 規範和問題：
1. 標題層級順序（不應跳過層級，如 H1 後直接用 H3）
2. 列表格式一致性
3. 表格格式是否正確
4. 連結和圖片引用是否有效
5. 代碼區塊是否正確標記
6. 文件結構是否清晰合理

針對發現的問題提供具體、可操作的改進建議。
"""

        try:
            # 使用輔助模型進行快速分析
            response_data = self._run_async(
                self.gemini_client.generate_async_simple(prompt, is_json=True)
            )
            
            # 清理和解析回應
            if isinstance(response_data, str):
                response_data = self._parse_detection_response(response_data)
            
            # 確保回應格式正確
            if not isinstance(response_data, dict):
                return {
                    'diagnostics': [],
                    'suggestions': [],
                    'has_issues': False
                }
            
            # 確保has_issues欄位正確
            has_issues = bool(response_data.get('diagnostics'))
            response_data['has_issues'] = has_issues
            
            # 添加元數據
            response_data['analysis_timestamp'] = self._get_current_timestamp()
            response_data['content_type'] = 'markdown'
            response_data['model_used'] = 'simple'
            
            return response_data
            
        except Exception as e:
            print(f"Markdown 分析錯誤: {e}")
            return {
                'diagnostics': [],
                'suggestions': [],
                'has_issues': False,
                'error': str(e)
            }
