import os
import json
import asyncio
import re
import threading
import logging
from typing import Dict, List, Any
from datetime import datetime

# Assuming the main Gemini client is in the core directory
from ..core.gemini_client import GeminiClient
from ..utils.json_parser import extract_json_from_text

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NoteAIClient:
    """
    A dedicated AI client for handling all AI-related tasks for the notes system.
    It leverages the core GeminiClient for actual API communication.
    Ghost 功能已移至 ghost_ai_client.py
    """
    def __init__(self):
        # Initialize the core Gemini client
        # This assumes API keys and other configurations are handled within GeminiClient
        self.gemini_client = GeminiClient()
        # Allow small tolerance for formatting-only verification
        self._strict_tolerance_ratio = 0.06  # up to 6% diff for whitespace/marks

    # === Formatting-only strict pipeline ===
    def format_markdown_strict(self, raw_text: str) -> Dict[str, Any]:
        """
        Convert raw text into Markdown formatting ONLY, without adding any new content.
        - Allowed changes: headings markers (#), emphasis (**, *), lists (-, 1.), blockquotes (>),
          code fences (```), links/images syntax [], (), and whitespace/newlines.
        - Forbidden: adding new words/sentences not present in raw text; translation; summarization.

        Returns: { success, markdown, model_used, guard: {input_len, output_len, normalized_match} }
        """
        raw_text = (raw_text or "").strip("\n")
        if not raw_text:
            return { 'success': True, 'markdown': '' }

        # Build a very strict instruction
        prompt = (
            "你是嚴格的Markdown格式整理器。\n"
            "任務：只為下列『原文』加上 Markdown 格式與結構，不得新增任何未出現於原文的詞彙或句子。\n"
            "規則：\n"
            "1) 僅允許加入 Markdown 標記符號 (# * - > ` [ ] ( ) |) 與必要的空白/換行。\n"
            "2) 禁止：改寫、翻譯、摘要、擴寫、杜撰、刪除實質內容。不得創作新標題文字。\n"
            "3) 若需要標題或項目，請直接將原有文字前加上適當的#或-，不得新增任何新詞。\n"
            "4) 保持文字順序一致；可適度換行以提升可讀性。\n"
            "5) 偵測明顯的程式碼或偽碼片段時，以```語法包裹；不要修改內容本身。\n"
            "輸出：只輸出Markdown格式內容，切勿輸出解釋或其它文字。\n\n"
            "【原文】\n" + raw_text
        )

        # Use auxiliary model for cost and latency
        ai_resp = self._run_async(self.gemini_client.generate_text_async(prompt, use_simple_model=True))
        candidate = (ai_resp or {}).get('text') or ''
        markdown = (candidate or '').strip()

        if not markdown:
            # Fallback to baseline heuristic formatter
            fallback = self._baseline_format_to_markdown(raw_text)
            return {
                'success': True,
                'markdown': fallback,
                'model_used': 'fallback-baseline',
                'guard': self._build_guard_meta(raw_text, fallback, normalized_match=False)
            }

        # Guardrail: ensure output doesn't invent content
        ok = self._verify_formatting_only(raw_text, markdown)
        if not ok:
            # If failed, fall back to deterministic baseline formatter that never adds content
            safe_md = self._baseline_format_to_markdown(raw_text)
            return {
                'success': True,
                'markdown': safe_md,
                'model_used': 'guard-fallback',
                'guard': self._build_guard_meta(raw_text, markdown, normalized_match=False)
            }

        return {
            'success': True,
            'markdown': markdown,
            'model_used': 'simple',
            'guard': self._build_guard_meta(raw_text, markdown, normalized_match=True)
        }

    def _normalize_text_for_compare(self, s: str) -> str:
        """Normalize to compare content equality ignoring Markdown and punctuation."""
        import re
        if not s:
            return ''
        # Remove code fences and inline code markers (but keep content inside)
        s = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).replace('`', ''), s)
        s = s.replace('`', '')
        # Remove markdown control chars and links syntax while keeping inner text
        s = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", s)  # [text](url) -> text
        s = re.sub(r"^\s*#+\s*", "", s, flags=re.MULTILINE)
        s = re.sub(r"^\s*[-*+]\s+", "", s, flags=re.MULTILINE)
        s = re.sub(r"^\s*>\s*", "", s, flags=re.MULTILINE)
        s = s.replace('|', ' ')
        # Remove whitespace and common punctuations
        s = re.sub(r"[\s\u3000]+", "", s)
        s = re.sub(r"[\,\.。；;、，：:！!？?\(\)（）\[\]【】<>《》\-—_]+", "", s)
        return s.lower()

    def _verify_formatting_only(self, raw_text: str, out_md: str) -> bool:
        """Heuristic check: out_md must contain raw_text content (ignoring markdown) with small tolerance."""
        norm_in = self._normalize_text_for_compare(raw_text)
        norm_out = self._normalize_text_for_compare(out_md)
        if not norm_in:
            return True
        # Basic containment heuristic
        if norm_in in norm_out:
            return True
        # Ratio heuristic: input chars that appear in output
        import difflib
        matcher = difflib.SequenceMatcher(a=norm_in, b=norm_out)
        ratio = matcher.quick_ratio()
        try:
            full_ratio = matcher.ratio()
        except Exception:
            full_ratio = ratio
        # Allow minor losses due to whitespace and bullets
        return full_ratio >= (1.0 - self._strict_tolerance_ratio)

    def _baseline_format_to_markdown(self, text: str) -> str:
        """Deterministic minimal formatter that never adds new content words.
        - Promote short standalone lines to headings by prefixing '# ' but using the same text
        - Convert lines with 常見清單分隔符 to bullet by prefixing '- '
        - Ensure double newlines between logical blocks
        - Wrap obvious code/pseudocode blocks with fences without altering inner text
        """
        if not text:
            return ''
        import re
        lines = text.split('\n')
        out = []
        for i, line in enumerate(lines):
            raw = line.rstrip()
            stripped = raw.strip()
            if not stripped:
                out.append('')
                continue
            # Code fence detection (heuristic): lines with many braces/semicolons/keywords
            if re.search(r"\b(class|def|function|SELECT|INSERT|UPDATE|for\s*\(|while\s*\(|if\s*\(|else|elif|try|catch)\b", stripped, re.IGNORECASE):
                out.append('```')
                out.append(stripped)
                out.append('```')
                continue
            # Heading heuristic: short line without sentence end punctuation and next line non-empty
            is_head = len(stripped) <= 30 and not re.search(r"[。.?？！!；;]$", stripped)
            if is_head:
                out.append('# ' + stripped)
                continue
            # Bullet heuristic: lines with separators like '：' inside can be bulletized by prefixing '- '
            if '：' in stripped or ':' in stripped:
                out.append('- ' + stripped)
                continue
            out.append(stripped)
        # Collapse excessive blank lines to max 2
        joined = '\n'.join(out)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip('\n')

    def _build_guard_meta(self, raw_text: str, out_md: str, normalized_match: bool) -> Dict[str, Any]:
        try:
            return {
                'input_len': len(raw_text or ''),
                'output_len': len(out_md or ''),
                'normalized_match': bool(normalized_match)
            }
        except Exception:
            return {'normalized_match': bool(normalized_match)}

    def _run_async(self, coro):
        """Helper method to run async functions synchronously - fixed"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in a running loop, we can't use run_until_complete
                # Instead, we'll use a thread pool to avoid blocking
                result = [None]
                exception = [None]
                
                def run_in_thread():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result[0] = new_loop.run_until_complete(coro)
                        new_loop.close()
                    except Exception as e:
                        exception[0] = e
                
                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join()
                
                if exception[0]:
                    raise exception[0]
                return result[0]
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop, create a new one
            return asyncio.run(coro)

    async def _safe_generate_json(self, prompt: str, use_simple_model: bool = False) -> Dict[str, Any]:
        """
        Safely generate JSON response with error handling
        """
        try:
            if use_simple_model:
                response = await self.gemini_client.generate_async_simple(prompt)
            else:
                response = await self.gemini_client.generate_async(prompt)
            
            if not response:
                return {'success': False, 'error': 'Empty response'}
            
            # Try to parse as JSON first
            try:
                parsed_json = json.loads(response)
                # 確保返回的數據包含success字段
                return {
                    'success': True,
                    'data': parsed_json
                }
            except json.JSONDecodeError:
                # If not JSON, return as content
                return {
                    'success': True,
                    'content': response
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _fix_common_json_issues(self, json_str: str) -> str:
        """Fix common JSON formatting issues"""
        if not json_str:
            return json_str
        
        # Remove extra backslashes
        json_str = json_str.replace('\\\\', '\\')
        
        # Fix newline characters
        json_str = json_str.replace('\n', '\\n')
        json_str = json_str.replace('\r', '\\r')
        json_str = json_str.replace('\t', '\\t')
        
        # Fix unescaped quotes
        json_str = re.sub(r'(?<!\\)"(?![,}\]:])', '\\"', json_str)
        
        return json_str

    def _extract_structured_content(self, text: str) -> Dict[str, Any]:
        """Extract structured content from AI response"""
        try:
            # Try to extract JSON first
            json_content = extract_json_from_text(text)
            if json_content:
                return json_content
            
            # If no JSON found, return basic structure
            return {
                'content': text,
                'success': True
            }
        except Exception:
            return {
                'content': text or '',
                'success': False
            }

    # === Analysis Functions ===
    
    def analyze_note_content(self, content: str) -> Dict[str, Any]:
        """Analyze note content for key concepts and structure"""
        prompt = f"""
        請以繁體中文（台灣用語）分析以下筆記內容，提取關鍵概念和建議的改進方向：

        內容：
        {content}

        請以JSON格式回傳分析結果，所有回應內容請使用繁體中文：
        {{
            "summary": "簡短摘要",
            "keywords": ["關鍵詞1", "關鍵詞2", "關鍵詞3"],
            "suggested_tags": ["標籤1", "標籤2", "標籤3"],
            "key_concepts": ["概念1", "概念2", "概念3"],
            "content_quality": {{"score": 0-10, "notes": "評估說明"}},
            "suggestions": ["建議1", "建議2", "建議3"],
            "knowledge_points": ["知識點1", "知識點2"]
        }}
        """
        
        try:
            result = self._run_async(self._safe_generate_json(prompt, use_simple_model=True))
            if result.get('success'):
                # 提取實際的AI回應數據
                ai_data = result.get('data', result.get('content', result))
                return ai_data if isinstance(ai_data, dict) else result
            else:
                return self._get_default_analysis_structure()
        except Exception as e:
            print(f"Error analyzing content: {e}")
            return self._get_default_analysis_structure()

    def suggest_related_content(self, note_content: str, existing_notes: List[str], all_knowledge_points: List[str]) -> Dict[str, List]:
        """Suggest related content based on note content and existing knowledge"""
        prompt = f"""
        基於以下筆記內容，從現有的筆記和知識點中建議相關內容：

        筆記內容：
        {note_content}

        現有筆記標題：
        {', '.join(existing_notes[:10])}  

        知識點：
        {', '.join(all_knowledge_points[:20])}

        請以JSON格式回傳：
        {{
            "related_notes": ["相關筆記1", "相關筆記2"],
            "suggested_topics": ["建議主題1", "建議主題2"],
            "knowledge_gaps": ["知識缺口1", "知識缺口2"]
        }}
        """
        
        try:
            result = self._run_async(self._safe_generate_json(prompt, use_simple_model=True))
            if result.get('success'):
                # 提取實際的AI回應數據
                ai_data = result.get('data', result.get('content', result))
                return ai_data if isinstance(ai_data, dict) else result
            else:
                return {"related_notes": [], "suggested_topics": [], "knowledge_gaps": []}
        except Exception as e:
            print(f"Error suggesting related content: {e}")
            return {"related_notes": [], "suggested_topics": [], "knowledge_gaps": []}

    # === Note Organization Methods ===

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
        """Organize content using Q&A learning approach"""
        prompt = f"""
        請將以下內容組織成問答式學習格式，建立完整的學習體系：

        內容：
        {content}

        請深入分析內容，創建多層次的問答學習結構。請以JSON格式回傳，包含以下要素：

        {{
            "topic": "主題名稱",
            "qa_pairs": [
                {{
                    "question": "基礎理解問題",
                    "answer": "詳細答案，包含具體說明",
                    "explanation": "深入解釋概念原理",
                    "key_points": ["關鍵要點1", "關鍵要點2", "關鍵要點3"]
                }},
                {{
                    "question": "應用分析問題", 
                    "answer": "實際應用的詳細說明",
                    "explanation": "為什麼這樣應用，背後的邏輯",
                    "key_points": ["應用要點1", "應用要點2"]
                }},
                {{
                    "question": "批判思考問題",
                    "answer": "深度思考的答案",
                    "explanation": "多角度分析和評估",
                    "key_points": ["分析角度1", "分析角度2"]
                }}
            ],
            "summary": "整體學習重點總結",
            "review_questions": [
                "復習檢測問題1",
                "復習檢測問題2", 
                "復習檢測問題3"
            ],
            "learning_tips": [
                "學習建議1",
                "學習建議2"
            ]
        }}

        要求：
        1. 問題要有層次性：從基礎理解→實際應用→批判思考
        2. 答案要詳細具體，避免空泛
        3. 解釋要深入，說明why而不只是what
        4. 關鍵要點要精準，便於記憶
        5. 創建至少5-8個高質量問答對
        6. 復習問題要能檢測學習效果
        """

        try:
            result = self._run_async(self._safe_generate_json(prompt))
            
            if result.get('success'):
                # 提取實際的AI回應數據
                ai_data = result.get('data', result.get('content', result))
                # Post-process the result to ensure proper structure
                return self._post_process_qa_learning_result(ai_data)
            else:
                return self._get_default_organize_result("qa_learning")
        except Exception as e:
            print(f"Error organizing with Q&A learning: {e}")
            return self._get_default_organize_result("qa_learning")

    def _post_process_qa_learning_result(self, qa_result: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process Q&A learning result to ensure proper structure"""
        try:
            # Ensure we have the required structure
            if not self._validate_qa_structure(qa_result):
                # Try to reformat using AI
                return self._format_qa_content_with_ai(qa_result)
            
            return qa_result
        except Exception as e:
            print(f"Error post-processing Q&A result: {e}")
            return self._get_default_organize_result("qa_learning")

    def _validate_qa_structure(self, qa_data: Dict[str, Any]) -> bool:
        """Validate Q&A structure"""
        try:
            required_fields = ['topic', 'qa_pairs']
            if not all(field in qa_data for field in required_fields):
                return False
            
            # Validate qa_pairs structure
            qa_pairs = qa_data.get('qa_pairs', [])
            if not isinstance(qa_pairs, list) or len(qa_pairs) == 0:
                return False
            
            # Check each Q&A pair
            for pair in qa_pairs:
                if not isinstance(pair, dict):
                    return False
                if 'question' not in pair or 'answer' not in pair:
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

    def organize_with_mandala_ninegrid(self, content: str) -> Dict[str, Any]:
        """曼陀羅九宮格思考法 - 將內容轉換成九宮格結構化思考"""
        prompt = f"""
        請將以下筆記內容轉換成曼陀羅九宮格思考法的格式，將核心主題放在中央，周圍8個格子包含相關的子主題或關鍵要素。

        筆記內容：
        ---
        {content}
        ---

        **--- JSON 格式範例 START ---**
        {{
            "central_theme": "人工智慧",
            "grid_layout": {{
                "center": "人工智慧",
                "top_left": "機器學習",
                "top_center": "深度學習", 
                "top_right": "自然語言處理",
                "middle_left": "電腦視覺",
                "middle_right": "專家系統",
                "bottom_left": "神經網路",
                "bottom_center": "資料科學",
                "bottom_right": "演算法"
            }},
            "detailed_explanations": {{
                "center": "人工智慧是讓機器模擬人類智慧的技術領域",
                "top_left": "機器學習讓電腦從資料中自動學習模式",
                "top_center": "深度學習是機器學習的進階技術，模擬人腦神經網路",
                "top_right": "自然語言處理讓電腦理解和生成人類語言",
                "middle_left": "電腦視覺讓機器能夠理解和分析圖像",
                "middle_right": "專家系統模擬領域專家的決策過程",
                "bottom_left": "神經網路是深度學習的基礎架構",
                "bottom_center": "資料科學提供AI所需的資料分析技能",
                "bottom_right": "演算法是AI系統的核心邏輯"
            }},
            "connections": [
                {{
                    "from": "center",
                    "to": "top_left", 
                    "relation": "機器學習是AI的核心技術之一"
                }},
                {{
                    "from": "top_left",
                    "to": "top_center",
                    "relation": "深度學習是機器學習的子領域"
                }}
            ],
            "thinking_process": "從核心概念出發，探索相關的技術領域和應用方向，建立完整的知識架構",
            "practical_applications": ["智慧型手機助理", "自動駕駛", "醫療診斷", "金融風控"],
            "learning_path": "建議從機器學習基礎開始，逐步深入各個專業領域"
        }}
        **--- JSON 格式範例 END ---**

        請**務必**以以下 JSON 格式回傳，**必須**是有效的JSON結構：
        {{
            "central_theme": "核心主題名稱",
            "grid_layout": {{
                "center": "中央主題",
                "top_left": "左上子主題",
                "top_center": "正上子主題",
                "top_right": "右上子主題", 
                "middle_left": "左側子主題",
                "middle_right": "右側子主題",
                "bottom_left": "左下子主題",
                "bottom_center": "正下子主題",
                "bottom_right": "右下子主題"
            }},
            "detailed_explanations": {{
                "center": "中央主題的詳細說明",
                "top_left": "左上子主題的詳細說明",
                "top_center": "正上子主題的詳細說明",
                "top_right": "右上子主題的詳細說明",
                "middle_left": "左側子主題的詳細說明", 
                "middle_right": "右側子主題的詳細說明",
                "bottom_left": "左下子主題的詳細說明",
                "bottom_center": "正下子主題的詳細說明",
                "bottom_right": "右下子主題的詳細說明"
            }},
            "connections": [
                {{
                    "from": "起始位置",
                    "to": "目標位置",
                    "relation": "關聯性描述"
                }}
            ],
            "thinking_process": "整體思考過程和邏輯",
            "practical_applications": ["實際應用1", "應用2", "應用3"],
            "learning_path": "學習建議和路徑"
        }}

        重點：
        1. central_theme 是整個九宮格的核心概念
        2. grid_layout 包含9個位置的主題名稱（要簡潔）
        3. detailed_explanations 包含每個位置的詳細說明
        4. connections 描述各格子之間的關聯性
        5. 確保各個子主題都與中央主題有邏輯連結
        6. 回傳格式必須是有效的JSON，不要包含其他文字
        """
        # 曼陀羅九宮格：使用主模型（需要結構化思考和關聯分析）
        return self._safe_ai_call(prompt, "mandala_ninegrid", use_simple_model=False)

    def format_and_enhance_content(self, content: str) -> Dict[str, Any]:
        """Format and enhance content - now returns plain markdown"""
        prompt = f"""
        請優化並增強以下筆記內容的格式和結構，使其更易讀和更有條理：

        原始內容：
        {content}

        請直接輸出優化後的 Markdown 格式內容，不要包含任何 JSON 結構。
        要求：
        1. 改善標題層次結構
        2. 優化段落組織
        3. 添加適當的格式標記（粗體、斜體、列表等）
        4. 保持原始內容的完整性
        5. 使用清晰的 Markdown 語法
        """

        try:
            result = self._run_async(self.gemini_client.generate_async(prompt))
            if result:
                return {
                    'generated_content': result,
                    'success': True,
                    'model_used': 'gemini'
                }
            else:
                return {
                    'generated_content': content,  # 返回原始內容作為備用
                    'success': False,
                    'model_used': 'fallback'
                }
        except Exception as e:
            print(f"Error formatting and enhancing content: {e}")
            return {
                'generated_content': content,  # 返回原始內容作為備用
                'success': False,
                'error': str(e),
                'model_used': 'fallback'
            }

    def generate_interactive_quiz(self, content: str) -> Dict[str, Any]:
        """Generate interactive quiz from content"""
        prompt = f"""
        基於以下內容生成互動測驗：

        內容：
        {content}

        請以JSON格式回傳測驗：
        {{
            "quiz_title": "測驗標題",
            "questions": [
                {{
                    "type": "multiple_choice",
                    "question": "問題",
                    "options": ["選項A", "選項B", "選項C", "選項D"],
                    "correct_answer": 0,
                    "explanation": "答案解釋"
                }}
            ]
        }}
        """

        try:
            result = self._run_async(self._safe_generate_json(prompt))
            if result.get('success'):
                # 提取實際的AI回應數據
                ai_data = result.get('data', result.get('content', result))
                return ai_data if isinstance(ai_data, dict) else result
            else:
                return self._get_default_organize_result("quiz")
        except Exception as e:
            print(f"Error generating interactive quiz: {e}")
            return self._get_default_organize_result("quiz")

    def generate_note_from_questions(self, questions_data: List[Dict]) -> Dict[str, Any]:
        """Generate note from question data"""
        questions_text = "\n".join([
            f"Q: {q.get('question', '')}\nA: {q.get('answer', '')}\n"
            for q in questions_data
        ])

        prompt = f"""
        基於以下題目和答案生成學習筆記：

        題目和答案：
        {questions_text}

        請以JSON格式回傳：
        {{
            "title": "筆記標題",
            "content": "筆記內容（Markdown格式）",
            "key_concepts": ["概念1", "概念2"],
            "summary": "總結"
        }}
        """

        try:
            result = self._run_async(self._safe_generate_json(prompt))
            if result.get('success'):
                # 提取實際的AI回應數據
                ai_data = result.get('data', result.get('content', result))
                return ai_data if isinstance(ai_data, dict) else result
            else:
                return self._get_default_organize_result("note_from_questions")
        except Exception as e:
            print(f"Error generating note from questions: {e}")
            return self._get_default_organize_result("note_from_questions")

    def generate_smart_note_content(self, context: Dict[str, Any]) -> str:
        """
        智能生成筆記內容，支援複雜JSON結構或簡單文字
        
        Args:
            context: 包含question_text, answer_text, user_content, user_prompt, title的字典
        
        Returns:
            生成的筆記內容（Markdown格式）
        """
        # 檢查是否是複雜的結構化數據（你的新格式）
        if 'title' in context and 'sections' in context:
            return self._convert_structured_data_to_markdown(context)
        
        # 檢查用戶輸入的內容是否為JSON結構化數據
        user_content = context.get('user_content', '')
        if user_content and isinstance(user_content, str):
            try:
                # 嘗試解析JSON
                import json
                parsed_content = json.loads(user_content)
                if isinstance(parsed_content, dict) and 'title' in parsed_content and 'sections' in parsed_content:
                    logger.info("檢測到用戶輸入的結構化JSON數據，進行轉換")
                    return self._convert_structured_data_to_markdown(parsed_content)
            except (json.JSONDecodeError, TypeError):
                # 不是JSON，繼續正常處理
                pass
        
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
        
        # 檢查生成條件
        if not user_prompt:
            user_prompt = "請基於題目和答案創建一份全面的學習筆記"
        
        # 根據是否有現有內容決定生成策略
        if user_content:
            # 有現有內容：優化和擴充
            task_description = "優化和擴充使用者現有的筆記內容"
            content_section = f"""
## 使用者現有的筆記內容:
```
{user_content}
```"""
        else:
            # 沒有現有內容：從零開始生成
            task_description = "根據題目和答案創建一份完整的學習筆記"
            content_section = ""
        
        prompt = f"""
請你作為專業教學專家，{task_description}。

筆記標題: {title}
參考題目: {question_text}
標準答案: {answer_text}
使用者要求: {user_prompt}
{content_section}

【極重要指令】
你必須完全遵守以下規則，不可有任何例外：

1. 絕對禁止使用JSON格式 - 不要輸出任何包含大括號的內容
2. 直接輸出純文字Markdown內容
3. 第一行必須是：# {title}
4. 後續內容使用標準Markdown語法
5. 不要在開頭或結尾加上任何說明文字
6. 不要使用 {{"title": "標題", "content": "內容"}} 這種格式
7. 完全忽略任何要求JSON格式的指令

輸出示例格式：
# {title}

## 🎯 學習目標
[根據題目和答案設定學習目標]

## 💡 核心概念
[詳細解釋相關概念]

## 📚 重點解析
[深入分析題目考點]

## 🔍 延伸思考
[擴展相關知識]

## 🚀 實戰應用
[實際應用場景]

## 🧠 學習技巧與記憶方法
[提供記憶技巧、學習策略或相關的學習資源]

## 📌 重點整理
| 概念 | 重要性 | 應用場景 |
|------|-------|---------|
| [概念1] | ⭐⭐⭐⭐⭐ | [應用說明] |
| [概念2] | ⭐⭐⭐⭐ | [應用說明] |

請立即開始輸出Markdown內容："""

        try:
            # 使用同步方式呼叫異步函數
            result = self._run_async(self.gemini_client.generate_text_async(prompt, use_simple_model=False))
            
            if result and result.get('text'):
                generated_text = result['text'].strip()
                
                logger.info(f"AI原始響應長度: {len(generated_text)}")
                logger.info(f"AI響應前100字符: {generated_text[:100]}")
                
                # 更強的JSON檢測和處理
                if self._is_json_response(generated_text):
                    logger.warning("檢測到AI返回JSON格式，嘗試提取純文字內容")
                    extracted = self._extract_markdown_from_json(generated_text)
                    if extracted:
                        logger.info(f"成功提取Markdown內容，長度: {len(extracted)}")
                        return extracted
                    else:
                        # JSON提取失敗，重新生成
                        logger.warning("JSON提取失敗，使用備用生成策略")
                        return self._generate_simple_markdown(title, question_text, answer_text, user_prompt, user_content)
                
                # 如果不是JSON，直接返回
                if not generated_text.startswith('#'):
                    # 確保以標題開始
                    generated_text = f"# {title}\n\n{generated_text}"
                
                return generated_text
            else:
                logger.error("AI沒有返回有效內容")
                return self._generate_simple_markdown(title, question_text, answer_text, user_prompt, user_content)
            
        except Exception as e:
            logger.error(f"生成筆記時發生錯誤: {e}")
            return self._generate_simple_markdown(title, question_text, answer_text, user_prompt, user_content)

    def _generate_smart_note_without_question(self, context: Dict[str, Any]) -> str:
        """普通筆記生成（無題目情況）"""
        user_content = context.get('user_content', '').strip()
        user_prompt = context.get('user_prompt', '').strip()
        title = context.get('title', '')
        
        # 檢查生成條件
        if not user_prompt:
            return "請提供您希望AI幫助生成的筆記主題或學習重點。"
        
        # 根據是否有現有內容決定生成策略
        if user_content:
            # 有現有內容：優化和擴充
            task_description = "優化和擴充使用者現有的筆記內容"
            content_section = f"""
## 使用者現有的筆記內容:
```
{user_content}
```"""
        else:
            # 沒有現有內容：從零開始生成
            task_description = "根據使用者的要求從零開始生成一份完整的學習筆記"
            content_section = ""
        
        prompt = f"""
請你作為專業教學專家，{task_description}。

筆記標題: {title}
使用者要求: {user_prompt}
{content_section}

請參考以下結構，生成一份詳細且實用的學習筆記。請確保內容豐富、有條理，並包含實際的學習指導：

## 標準筆記結構
以 "# {title}" 作為標題開始，然後包含以下部分：

1. **📖 概述** - 主題的基本介紹和重要性
2. **🎯 核心概念** - 關鍵知識點和定義
3. **📚 詳細內容** - 深入的說明和分析
4. **💡 學習技巧** - 記憶方法和理解要點
5. **🔍 實際應用** - 應用場景和案例
6. **📊 重點整理** - 表格或清單形式的總結
7. **🧠 延伸思考** - 進階概念和相關主題
8. **📝 學習建議** - 具體的學習策略



【重要注意事項】
- 絕對不要使用JSON格式輸出
- 直接輸出純Markdown文字內容
- 確保內容具體且有實用價值
- 每個章節都要有具體內容，不要只是空框架
- 根據主題特性調整章節內容和重點

請現在就開始生成完整的筆記內容："""

        try:
            result = self._run_async(self.gemini_client.generate_text_async(prompt, use_simple_model=False))
            
            if result and result.get('text'):
                generated_text = result['text'].strip()
                
                logger.info(f"AI原始響應長度: {len(generated_text)}")
                
                # 使用相同的JSON檢測和處理邏輯
                if self._is_json_response(generated_text):
                    logger.warning("檢測到AI返回JSON格式，嘗試提取純文字內容")
                    extracted = self._extract_markdown_from_json(generated_text)
                    if extracted:
                        logger.info(f"成功提取Markdown內容，長度: {len(extracted)}")
                        return extracted
                    else:
                        # JSON提取失敗，使用備用生成
                        logger.warning("JSON提取失敗，使用備用生成策略")
                        return self._generate_simple_markdown(title, "", "", user_prompt, user_content)
                
                # 如果不是JSON，確保格式正確
                if not generated_text.startswith('#'):
                    generated_text = f"# {title}\n\n{generated_text}"
                
                return generated_text
            else:
                logger.error("AI沒有返回有效內容")
                return self._generate_simple_markdown(title, "", "", user_prompt, user_content)
            
        except Exception as e:
            logger.error(f"生成筆記時發生錯誤: {e}")
            return self._generate_simple_markdown(title, "", "", user_prompt, user_content)

    def _is_json_response(self, text: str) -> bool:
        """檢測回應是否為JSON格式"""
        text = text.strip()
        # 多種JSON格式檢測
        json_indicators = [
            text.startswith('{') and text.endswith('}'),
            '{"title":' in text,
            '{"content":' in text,
            '"title":' in text and '"content":' in text,
            text.startswith('```json') and text.endswith('```')
        ]
        return any(json_indicators)
    
    def _extract_markdown_from_json(self, json_text: str) -> str:
        """從JSON響應中提取Markdown內容"""
        try:
            import json
            import re
            
            # 移除可能的程式碼標記
            clean_text = json_text.strip()
            if clean_text.startswith('```json'):
                clean_text = clean_text[7:]
            if clean_text.endswith('```'):
                clean_text = clean_text[:-3]
            
            # 嘗試解析JSON
            parsed = json.loads(clean_text.strip())
            
            # 提取內容的多種策略
            content = None
            if isinstance(parsed, dict):
                # 策略1：直接取content欄位
                if 'content' in parsed:
                    content = parsed['content']
                # 策略2：取第一個字串值較長的欄位
                elif any(key in parsed for key in ['markdown', 'text', 'note', 'result']):
                    for key in ['markdown', 'text', 'note', 'result']:
                        if key in parsed and isinstance(parsed[key], str) and len(parsed[key]) > 50:
                            content = parsed[key]
                            break
                # 策略3：組合title和content
                elif 'title' in parsed:
                    title = parsed.get('title', '')
                    body = parsed.get('content', '') or parsed.get('body', '') or parsed.get('text', '')
                    if body:
                        content = f"# {title}\n\n{body}"
            
            if content:
                # 處理轉義字符
                content = content.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                return content
                
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"JSON解析失敗: {e}")
            
            # 備用方案：使用正則表達式提取
            try:
                import re
                # 匹配content欄位的值
                content_patterns = [
                    r'"content":\s*"(.*?)"(?=\s*[,}])',
                    r'"markdown":\s*"(.*?)"(?=\s*[,}])',
                    r'"text":\s*"(.*?)"(?=\s*[,}])'
                ]
                
                for pattern in content_patterns:
                    match = re.search(pattern, json_text, re.DOTALL)
                    if match:
                        content = match.group(1)
                        content = content.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                        if len(content) > 50:  # 確保內容足夠長
                            return content
                            
            except Exception as e2:
                logger.warning(f"正則表達式提取也失敗: {e2}")
        
        return None
    
    def _generate_simple_markdown(self, title: str, question: str, answer: str, user_prompt: str, user_content: str = "") -> str:
        """生成簡單的Markdown格式筆記（備用方案）"""
        logger.info("使用簡單Markdown生成策略")
        
        content_parts = [f"# {title}", ""]
        
        if user_prompt:
            content_parts.extend([
                "## 🎯 學習目標",
                user_prompt,
                ""
            ])
        
        if question:
            content_parts.extend([
                "## 📋 題目內容", 
                question,
                ""
            ])
        
        if answer:
            content_parts.extend([
                "## ✅ 標準答案",
                answer,
                ""
            ])
        
        if user_content:
            content_parts.extend([
                "## 📝 現有筆記內容",
                user_content,
                ""
            ])
        
        # 添加基本結構
        content_parts.extend([
            "## 💡 重點整理",
            "- 請根據上述內容自行整理重點",
            "",
            "## 🔍 深入思考", 
            "- 請思考相關概念的應用",
            "",
            "## 📚 延伸學習",
            "- 請自行補充相關學習資源",
            ""
        ])
        
        return "\n".join(content_parts)

    def _generate_fallback_note(self, title: str, user_prompt: str, user_content: str = "") -> str:
        """生成備用筆記格式"""
        return f"""# {title}

## 📚 核心知識與概念
{user_prompt}

{"## 📝 現有筆記內容" if user_content else "## 📝 學習內容"}
{user_content if user_content else "請補充具體的學習內容..."}

## 💡 重要概念與要點
- 待補充重要概念
- 待補充關鍵要點

## 🎯 應用與實例
- 待補充應用場景
- 待補充具體實例

## 🧠 學習技巧與記憶方法
- 待補充記憶技巧
- 待補充學習策略

## � 重點整理
| 概念 | 重要性 | 應用場景 |
|------|-------|---------|
| 待補充 | ⭐⭐⭐ | 待說明 |

## � 延伸學習
- 待補充進階主題
- 待補充相關資源

---
*此為備用筆記格式，請根據需要補充內容*"""

    def _generate_basic_note_template(self, title: str) -> str:
        """生成基本筆記模板"""
        timestamp = self._get_current_timestamp()
        
        return f"""# {title}

> 筆記建立時間：{timestamp}

## 📖 概述

*（請在這裡補充主題的基本概述）*

## 🎯 核心概念

### 重要知識點
- *（請補充核心知識點）*
- *（請補充核心知識點）*
- *（請補充核心知識點）*

## 📚 詳細內容

### 主要內容
*（請在這裡展開詳細說明）*

### 相關概念
*（請補充相關的概念或理論）*

## 💡 學習技巧

- **記憶方法：** *（請補充有效的記憶技巧）*
- **理解要點：** *（請補充理解的關鍵要點）*

## 🔍 實際應用

*（請補充實際的應用場景或案例）*

## 📋 總結

*（請補充本主題的重點總結）*

---

> 💬 **提示：** 這是一個空白的筆記模板，請根據學習內容填入具體資訊。
"""

    def _post_process_generated_content(self, content: str) -> str:
        """後處理生成的內容，確保格式正確"""
        if not content:
            return content
        
        # 確保標題格式正確
        lines = content.split('\n')
        processed_lines = []
        
        for line in lines:
            # 修復標題格式
            if line.strip().startswith('#'):
                # 確保 # 後面有空格
                title_match = re.match(r'^(#+)(.*)$', line.strip())
                if title_match:
                    hashes, title_text = title_match.groups()
                    if not title_text.startswith(' '):
                        line = f"{hashes} {title_text.strip()}"
                    else:
                        line = f"{hashes}{title_text}"
            
            processed_lines.append(line)
        
        content = '\n'.join(processed_lines)
        
        # 移除過多的空行
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 確保內容開頭和結尾沒有多餘的空行
        content = content.strip()
        
        return content

    def _convert_structured_data_to_markdown(self, data: Dict[str, Any]) -> str:
        """將複雜的結構化數據轉換為簡單的Markdown格式"""
        try:
            markdown_lines = []
            
            # 標題
            title = data.get('title', '未命名筆記')
            markdown_lines.append(f"# {title}")
            markdown_lines.append("")
            
            # 處理sections
            sections = data.get('sections', [])
            for section in sections:
                if isinstance(section, dict):
                    # 處理有heading的section
                    if 'heading' in section:
                        markdown_lines.append(f"## {section['heading']}")
                        markdown_lines.append("")
                    
                    # 處理content
                    if 'content' in section:
                        content = section['content']
                        markdown_lines.append(content)
                        markdown_lines.append("")
                    
                    # 處理points
                    if 'points' in section:
                        points = section['points']
                        if isinstance(points, list):
                            for point in points:
                                if isinstance(point, dict):
                                    if 'title' in point:
                                        markdown_lines.append(f"### {point['title']}")
                                        markdown_lines.append("")
                                    if 'description' in point:
                                        description = point['description']
                                        markdown_lines.append(description)
                                        markdown_lines.append("")
                                elif isinstance(point, str):
                                    markdown_lines.append(f"- {point}")
                    
                    # 處理嵌套的sections
                    if 'sections' in section:
                        nested_sections = section['sections']
                        if isinstance(nested_sections, list):
                            for nested_section in nested_sections:
                                if isinstance(nested_section, dict):
                                    if 'heading' in nested_section:
                                        markdown_lines.append(f"### {nested_section['heading']}")
                                        markdown_lines.append("")
                                    if 'content' in nested_section:
                                        markdown_lines.append(nested_section['content'])
                                        markdown_lines.append("")
                
                elif isinstance(section, str):
                    markdown_lines.append(section)
                    markdown_lines.append("")
            
            # 組合結果
            result = '\n'.join(markdown_lines)
            
            # 清理多餘的空行
            result = re.sub(r'\n{3,}', '\n\n', result)
            
            return result.strip()
            
        except Exception as e:
            logger.error(f"Error converting structured data to markdown: {e}")
            # 如果轉換失敗，返回基本格式
            title = data.get('title', '筆記')
            return f"# {title}\n\n轉換過程中發生錯誤，請手動編輯內容。\n\n原始數據：\n```json\n{str(data)}\n```"

    def _get_current_timestamp(self) -> str:
        """獲取當前時間戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        2. `content`: 整理後的筆記內容（使用 Markdown 格式）
        3. `key_points`: 重點整理（陣列）
        4. `suggestions`: 學習建議（陣列）
        """
        # 從教材生成筆記：使用主模型（需要教學性整理）
        return self._safe_ai_call(prompt, "note_from_materials", use_simple_model=False)

    # === Ghost 功能已移至 ghost_ai_client.py ===

    def detect_and_suggest_text(self, content: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        [已棄用] AI文字偵測功能已移至 GhostAIClient
        請使用 ghost_ai_client.GhostAIClient().detect_and_suggest_text(content, context)
        """
        from .ghost_ai_client import GhostAIClient
        ghost_client = GhostAIClient()
        return ghost_client.detect_and_suggest_text(content, context)

    def generate_content_enhancement(self, enhancement_request: str, current_content: str, title: str = "", context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        [已棄用] 內容增強功能已移至 GhostAIClient
        請使用 ghost_ai_client.GhostAIClient().generate_content_enhancement(enhancement_request, current_content, title, context)
        """
        from .ghost_ai_client import GhostAIClient
        ghost_client = GhostAIClient()
        return ghost_client.generate_content_enhancement(enhancement_request, current_content, title, context)

    # === Helper Methods ===

    def _get_default_organize_result(self, method_type: str) -> Dict[str, Any]:
        """Get default organize result for fallback"""
        return {
            "success": False,
            "method": method_type,
            "error": "無法組織內容",
            "content": "組織功能暫時不可用，請稍後再試。"
        }

    def _get_default_analysis_structure(self, error_message: str = "") -> Dict[str, Any]:
        """獲取預設的分析結構"""
        return {
            'summary': '',
            'keywords': [],
            'suggested_tags': [],
            'key_concepts': [],
            'content_quality': {'score': 0, 'notes': error_message or '分析功能暫時不可用'},
            'suggestions': [],
            'knowledge_points': []
        }

    def _safe_ai_call(self, prompt: str, operation_type: str, use_simple_model: bool = False) -> Dict[str, Any]:
        """安全的AI呼叫包裝器"""
        try:
            if use_simple_model:
                result = self._run_async(self.gemini_client.generate_async_simple(prompt))
            else:
                result = self._run_async(self.gemini_client.generate_async(prompt))
            
            return {
                'success': True,
                'content': result,
                'operation_type': operation_type
            }
        except Exception as e:
            print(f"Error in {operation_type}: {e}")
            return {
                'success': False,
                'error': str(e),
                'operation_type': operation_type
            }
