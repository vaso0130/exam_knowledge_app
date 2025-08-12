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
                response = await self.gemini_client.generate_simple_async(prompt)
            else:
                response = await self.gemini_client.generate_async(prompt)
            
            if not response:
                return {'success': False, 'error': 'Empty response'}
            
            # Try to parse as JSON first
            try:
                return json.loads(response)
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
        請分析以下筆記內容，提取關鍵概念和建議的改進方向：

        內容：
        {content}

        請以JSON格式回傳分析結果：
        {{
            "key_concepts": ["概念1", "概念2", "概念3"],
            "content_quality": {{"score": 0-10, "notes": "評估說明"}},
            "suggestions": ["建議1", "建議2", "建議3"],
            "knowledge_points": ["知識點1", "知識點2"]
        }}
        """
        
        try:
            result = self._run_async(self._safe_generate_json(prompt, use_simple_model=True))
            if result.get('success'):
                return result
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
                return result
            else:
                return {"related_notes": [], "suggested_topics": [], "knowledge_gaps": []}
        except Exception as e:
            print(f"Error suggesting related content: {e}")
            return {"related_notes": [], "suggested_topics": [], "knowledge_gaps": []}

    # === Note Organization Methods ===

    def organize_with_mindmap(self, content: str) -> Dict[str, Any]:
        """Organize content using mindmap structure"""
        prompt = f"""
        請將以下內容組織成心智圖結構：

        內容：
        {content}

        請以JSON格式回傳心智圖結構：
        {{
            "central_topic": "中心主題",
            "main_branches": [
                {{
                    "name": "主分支1",
                    "sub_branches": [
                        {{"name": "子分支1", "details": ["詳細1", "詳細2"]}},
                        {{"name": "子分支2", "details": ["詳細1", "詳細2"]}}
                    ]
                }}
            ],
            "connections": [
                {{"from": "分支A", "to": "分支B", "relationship": "關聯描述"}}
            ]
        }}
        """

        try:
            result = self._run_async(self._safe_generate_json(prompt))
            if result.get('success'):
                return result
            else:
                return self._get_default_organize_result("mindmap")
        except Exception as e:
            print(f"Error organizing with mindmap: {e}")
            return self._get_default_organize_result("mindmap")

    def organize_hierarchically(self, content: str) -> Dict[str, Any]:
        """Organize content in hierarchical structure"""
        prompt = f"""
        請將以下內容組織成階層結構：

        內容：
        {content}

        請以JSON格式回傳階層結構：
        {{
            "title": "主標題",
            "levels": [
                {{
                    "level": 1,
                    "title": "一級標題",
                    "content": "內容",
                    "sub_levels": [
                        {{"level": 2, "title": "二級標題", "content": "內容"}}
                    ]
                }}
            ]
        }}
        """

        try:
            result = self._run_async(self._safe_generate_json(prompt))
            if result.get('success'):
                return result
            else:
                return self._get_default_organize_result("hierarchical")
        except Exception as e:
            print(f"Error organizing hierarchically: {e}")
            return self._get_default_organize_result("hierarchical")

    def organize_with_feynman_technique(self, content: str) -> Dict[str, Any]:
        """Organize content using Feynman technique"""
        prompt = f"""
        請用費曼學習法組織以下內容：

        內容：
        {content}

        請以JSON格式回傳費曼學習法結構：
        {{
            "concept": "核心概念",
            "simple_explanation": "簡單解釋（用自己的話）",
            "examples": ["例子1", "例子2"],
            "analogies": ["類比1", "類比2"],
            "knowledge_gaps": ["需要進一步了解的部分"],
            "teaching_points": ["教學要點"]
        }}
        """

        try:
            result = self._run_async(self._safe_generate_json(prompt))
            if result.get('success'):
                return result
            else:
                return self._get_default_organize_result("feynman")
        except Exception as e:
            print(f"Error organizing with Feynman technique: {e}")
            return self._get_default_organize_result("feynman")

    def organize_with_qa_learning(self, content: str) -> Dict[str, Any]:
        """Organize content using Q&A learning approach"""
        prompt = f"""
        請將以下內容組織成問答式學習格式：

        內容：
        {content}

        請以JSON格式回傳問答結構：
        {{
            "topic": "主題",
            "qa_pairs": [
                {{
                    "question": "問題1",
                    "answer": "答案1",
                    "explanation": "詳細解釋",
                    "key_points": ["要點1", "要點2"]
                }}
            ],
            "summary": "總結",
            "review_questions": ["復習問題1", "復習問題2"]
        }}
        """

        try:
            result = self._run_async(self._safe_generate_json(prompt))
            
            if result.get('success'):
                # Post-process the result to ensure proper structure
                return self._post_process_qa_learning_result(result)
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
        """Use AI to reformat Q&A content if structure is invalid"""
        try:
            content_text = str(raw_qa_data)
            
            prompt = f"""
            以下是需要重新格式化的問答內容，請整理成標準的JSON格式：

            原始內容：
            {content_text}

            請輸出標準的JSON格式：
            {{
                "topic": "主題名稱",
                "qa_pairs": [
                    {{
                        "question": "問題",
                        "answer": "答案",
                        "explanation": "詳細解釋",
                        "key_points": ["要點1", "要點2"]
                    }}
                ],
                "summary": "內容總結",
                "review_questions": ["復習問題1", "復習問題2"]
            }}
            """
            
            result = self._run_async(self._safe_generate_json(prompt))
            if result.get('success') and self._validate_qa_structure(result):
                return result
            else:
                return self._get_default_organize_result("qa_learning")
                
        except Exception as e:
            print(f"Error formatting Q&A content with AI: {e}")
            return self._get_default_organize_result("qa_learning")

    def organize_with_comparison(self, content: str) -> Dict[str, Any]:
        """Organize content using comparison approach"""
        prompt = f"""
        請將以下內容組織成比較分析格式：

        內容：
        {content}

        請以JSON格式回傳比較結構：
        {{
            "comparison_title": "比較主題",
            "items": [
                {{
                    "name": "項目1",
                    "features": {{"特徵A": "值1", "特徵B": "值2"}},
                    "advantages": ["優點1", "優點2"],
                    "disadvantages": ["缺點1", "缺點2"]
                }}
            ],
            "comparison_table": [
                {{"feature": "特徵", "item1": "項目1值", "item2": "項目2值"}}
            ],
            "conclusion": "比較結論"
        }}
        """

        try:
            result = self._run_async(self._safe_generate_json(prompt))
            if result.get('success'):
                return result
            else:
                return self._get_default_organize_result("comparison")
        except Exception as e:
            print(f"Error organizing with comparison: {e}")
            return self._get_default_organize_result("comparison")

    def organize_with_memory_palace(self, content: str) -> Dict[str, Any]:
        """Organize content using memory palace technique"""
        prompt = f"""
        請將以下內容組織成記憶宮殿結構：

        內容：
        {content}

        請以JSON格式回傳記憶宮殿結構：
        {{
            "palace_theme": "宮殿主題",
            "rooms": [
                {{
                    "room_name": "房間名稱",
                    "description": "房間描述",
                    "memory_anchors": [
                        {{
                            "anchor": "記憶錨點",
                            "content": "相關內容",
                            "visual_cue": "視覺提示"
                        }}
                    ]
                }}
            ],
            "journey_path": ["房間1", "房間2", "房間3"],
            "memory_tips": ["記憶技巧1", "記憶技巧2"]
        }}
        """

        try:
            result = self._run_async(self._safe_generate_json(prompt))
            if result.get('success'):
                return result
            else:
                return self._get_default_organize_result("memory_palace")
        except Exception as e:
            print(f"Error organizing with memory palace: {e}")
            return self._get_default_organize_result("memory_palace")

    def organize_with_mandala_ninegrid(self, content: str) -> Dict[str, Any]:
        """Organize content using Mandala Nine-Grid thinking method"""
        prompt = f"""
        請將以下內容組織成曼陀羅九宮格思考法結構：

        內容：
        {content}

        請以JSON格式回傳曼陀羅九宮格結構：
        {{
            "central_theme": "中心主題",
            "grid_layout": {{
                "top_left": "左上角內容",
                "top_center": "上方中央內容",
                "top_right": "右上角內容",
                "middle_left": "左側中央內容",
                "center": "中心主題內容",
                "middle_right": "右側中央內容",
                "bottom_left": "左下角內容",
                "bottom_center": "下方中央內容",
                "bottom_right": "右下角內容"
            }},
            "detailed_explanations": {{
                "top_left": "左上角內容的詳細說明",
                "top_center": "上方中央內容的詳細說明",
                "top_right": "右上角內容的詳細說明",
                "middle_left": "左側中央內容的詳細說明",
                "center": "中心主題的詳細說明",
                "middle_right": "右側中央內容的詳細說明",
                "bottom_left": "左下角內容的詳細說明",
                "bottom_center": "下方中央內容的詳細說明",
                "bottom_right": "右下角內容的詳細說明"
            }},
            "connections": [
                {{"from": "center", "to": "top_left", "relation": "關聯描述"}},
                {{"from": "center", "to": "top_center", "relation": "關聯描述"}},
                {{"from": "center", "to": "top_right", "relation": "關聯描述"}},
                {{"from": "center", "to": "middle_left", "relation": "關聯描述"}},
                {{"from": "center", "to": "middle_right", "relation": "關聯描述"}},
                {{"from": "center", "to": "bottom_left", "relation": "關聯描述"}},
                {{"from": "center", "to": "bottom_center", "relation": "關聯描述"}},
                {{"from": "center", "to": "bottom_right", "relation": "關聯描述"}}
            ],
            "thinking_process": "整體思考過程描述",
            "practical_applications": ["實際應用1", "實際應用2", "實際應用3"],
            "learning_path": "學習建議和路徑"
        }}
        """

        try:
            result = self._run_async(self._safe_generate_json(prompt))
            if result.get('success'):
                return result
            else:
                return self._get_default_organize_result("mandala_ninegrid")
        except Exception as e:
            print(f"Error organizing with mandala ninegrid: {e}")
            return self._get_default_organize_result("mandala_ninegrid")

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
                return result
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
                return result
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

## � 核心概念
[詳細解釋相關概念]

## 💡 重點解析
[深入分析題目考點]

## 🔍 延伸思考
[擴展相關知識]

## � 實戰應用
[實際應用場景]

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
            'key_concepts': [],
            'content_quality': {'score': 0, 'notes': error_message or '分析功能暫時不可用'},
            'suggestions': [],
            'knowledge_points': []
        }

    def _safe_ai_call(self, prompt: str, operation_type: str, use_simple_model: bool = False) -> Dict[str, Any]:
        """安全的AI呼叫包裝器"""
        try:
            if use_simple_model:
                result = self._run_async(self.gemini_client.generate_simple_async(prompt))
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
