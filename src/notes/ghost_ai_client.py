"""
Ghost AI 客戶端 - 專門處理智能筆記生成功能
從原本的 ai_client.py 中分離出來，專注於 Ghost 功能
"""

import asyncio
import threading
import json
import logging
import re
from typing import Dict, Any, List
from datetime import datetime

from ..core.gemini_client import GeminiClient

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GhostAIClient:
    """Ghost AI 客戶端 - 專門處理智能筆記生成和內容增強功能"""
    
    def __init__(self):
        """初始化 Ghost AI 客戶端"""
        self.gemini_client = GeminiClient()
        self.max_retries = 3
        self.timeout = 60
        
    def _run_async(self, coro):
        """在同步環境中運行異步協程"""
        try:
            # 嘗試獲取當前的事件循環
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循環正在運行，在新線程中創建新的事件循環
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
                # 如果事件循環沒有運行，直接使用它
                return loop.run_until_complete(coro)
        except RuntimeError:
            # 如果沒有事件循環，創建一個新的
            return asyncio.run(coro)

    async def _safe_generate_json(self, prompt: str, use_simple_model: bool = False) -> Dict[str, Any]:
        """安全地生成JSON響應"""
        try:
            for attempt in range(self.max_retries):
                try:
                    if use_simple_model:
                        response = await self.gemini_client.generate_simple_async(prompt)
                    else:
                        response = await self.gemini_client.generate_async(prompt)
                    
                    if not response:
                        logger.warning(f"Empty response on attempt {attempt + 1}")
                        continue
                    
                    # 嘗試解析JSON
                    json_text = self._extract_json_from_response(response)
                    if json_text:
                        return json.loads(json_text)
                    
                    # 如果不是JSON格式，返回基本結構
                    return {
                        'content': response,
                        'success': True,
                        'model_used': 'simple' if use_simple_model else 'advanced'
                    }
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error on attempt {attempt + 1}: {e}")
                    if attempt == self.max_retries - 1:
                        return {
                            'content': response if 'response' in locals() else '',
                            'success': False,
                            'error': f'JSON decode error: {str(e)}'
                        }
                except Exception as e:
                    logger.error(f"Error on attempt {attempt + 1}: {e}")
                    if attempt == self.max_retries - 1:
                        return {
                            'content': '',
                            'success': False,
                            'error': str(e)
                        }
            
            return {
                'content': '',
                'success': False,
                'error': 'All retry attempts failed'
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in _safe_generate_json: {e}")
            return {
                'content': '',
                'success': False,
                'error': str(e)
            }

    def _extract_json_from_response(self, response: str) -> str:
        """從響應中提取JSON部分"""
        if not response:
            return ""
        
        # 嘗試找到JSON代碼塊
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(json_pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
        
        # 如果沒有找到代碼塊，嘗試直接找JSON結構
        json_pattern = r'\{.*\}'
        match = re.search(json_pattern, response, re.DOTALL)
        if match:
            return match.group(0)
        
        return ""

    def _fix_common_json_issues(self, json_str: str) -> str:
        """修復常見的JSON格式問題"""
        if not json_str:
            return json_str
        
        # 移除多餘的反斜線
        json_str = json_str.replace('\\\\', '\\')
        
        # 修復換行符問題
        json_str = json_str.replace('\n', '\\n')
        json_str = json_str.replace('\r', '\\r')
        json_str = json_str.replace('\t', '\\t')
        
        # 修復未轉義的引號
        json_str = re.sub(r'(?<!\\)"(?![,}\]:])', '\\"', json_str)
        
        return json_str

    def _get_current_timestamp(self) -> str:
        """獲取當前時間戳"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # === Ghost 智能文字偵測功能 ===

    def detect_and_suggest_text(self, content: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        AI文字偵測 - 即時分析用戶輸入的文字內容並提供智慧建議
        類似 VS Code IntelliSense 的即時建議功能
        
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
        
        # 如果沒有預定義的建議，則使用AI生成建議
        prompt = f"""
        你是一個智慧文字助手，類似 VS Code 的 IntelliSense。請分析用戶正在輸入的文字內容，並提供即時的智慧建議。

        ## 分析內容
        **筆記標題：** {note_title}
        **用戶輸入：** {content}
        **已有內容：** {existing_content[:200] + "..." if len(existing_content) > 200 else existing_content}

        ## 任務要求
        請分析用戶的輸入內容，並以JSON格式返回建議：

        ```json
        {{
            "suggestions": [
                {{
                    "type": "概念延伸",
                    "title": "建議標題",
                    "content": "具體建議內容",
                    "priority": "high|medium|low"
                }}
            ],
            "has_suggestions": true,
            "analysis_note": "簡短的分析說明",
            "detected_topics": ["主題1", "主題2"],
            "suggested_structure": [
                "建議的段落結構1",
                "建議的段落結構2"
            ]
        }}
        ```

        ## 建議類型
        - **概念延伸**: 相關概念的深入說明
        - **格式優化**: Markdown格式的改進建議
        - **內容補充**: 缺失信息的補充建議
        - **結構調整**: 內容組織的優化建議
        - **關鍵詞解釋**: 專業術語的解釋
        - **實例補充**: 相關案例或例子的建議

        請提供3-5個最有價值的建議，確保建議具體、實用且符合學習需求。
        """

        try:
            result = self._run_async(self._safe_generate_json(prompt, use_simple_model=True))
            
            if result.get('success', False):
                # 解析JSON內容
                if 'content' in result:
                    try:
                        json_content = json.loads(result['content'])
                        return json_content
                    except json.JSONDecodeError:
                        pass
                
                # 如果有直接的結構化數據
                if 'suggestions' in result:
                    return result
            
            # 返回默認響應
            return self._get_default_detection_response("AI分析暫時不可用")
            
        except Exception as e:
            logger.error(f"Error in detect_and_suggest_text: {e}")
            return self._get_default_detection_response(f"分析過程中發生錯誤: {str(e)}")

    def _get_default_detection_response(self, error_msg: str = "") -> Dict[str, Any]:
        """獲取默認的偵測響應"""
        return {
            'suggestions': [],
            'has_suggestions': False,
            'analysis_note': error_msg or '暫時無法提供建議',
            'detected_topics': [],
            'suggested_structure': []
        }

    # === 內容增強功能 ===

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
            
            # 如果是簡單的內容延續建議，使用更簡潔的處理
            if "延續" in enhancement_request or "supplement" in str(context):
                prompt = f"""
請根據以下內容，提供1-2句自然的延續文字，幫助用戶繼續寫作：

目前內容：
{current_content}

請生成簡潔、相關的延續建議（不超過50字）：
"""
                try:
                    result = self._run_async(self.gemini_client.generate_async_simple(prompt, is_json=False))
                    
                    if result and result.strip():
                        # 清理和格式化結果
                        suggestion = result.strip()
                        # 移除可能的引號或格式符號
                        suggestion = suggestion.strip('"\'').strip()
                        # 限制長度
                        if len(suggestion) > 100:
                            suggestion = suggestion[:100] + "..."
                        
                        return {
                            'generated_content': suggestion,
                            'success': True,
                            'model_used': 'gemini_simple'
                        }
                except Exception as e:
                    logger.warning(f"Simple generation failed: {e}")
                    pass
            
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
請根據增強要求，生成相應的內容來改善或補充現有筆記。請確保：

1. **內容準確性** - 提供正確、最新的技術資訊
2. **結構清晰** - 使用適當的Markdown格式和層次結構
3. **實用性** - 包含實際應用場景和具體例子
4. **教育價值** - 適合學習和理解，解釋清楚專業術語

**特別注意：**
- 如果涉及技術術語，請提供完整的英文全名和中文翻譯
- 包含具體的技術規格、標準或最佳實踐
- 適當添加表格、清單等結構化內容
- 提供記憶技巧或重點總結

請生成補充或改善的內容：
"""

            try:
                result = self._run_async(self.gemini_client.generate_async(prompt))
                
                if not result:
                    return {
                        'generated_content': self._get_fallback_enhancement(enhancement_request),
                        'success': False,
                        'model_used': 'fallback'
                    }
                
                # 後處理生成的內容
                processed_content = self._post_process_enhancement_content(result)
                
                return {
                    'generated_content': processed_content,
                    'success': True,
                    'model_used': 'gemini'
                }
                
            except Exception as e:
                logger.error(f"Error generating content enhancement: {e}")
                return {
                    'generated_content': self._get_fallback_enhancement(enhancement_request),
                    'success': False,
                    'error': str(e),
                    'model_used': 'fallback'
                }
                
        except Exception as e:
            logger.error(f"Error in generate_content_enhancement: {e}")
            return {
                'generated_content': self._get_fallback_enhancement(enhancement_request),
                'success': False,
                'error': str(e),
                'model_used': 'fallback'
            }

    def _post_process_enhancement_content(self, content: str) -> str:
        """後處理增強生成的內容"""
        if not content:
            return content
        
        # 移除可能的prompt殘留
        lines = content.split('\n')
        processed_lines = []
        
        # 檢查開頭是否包含prompt相關內容
        skip_lines = 0
        for i, line in enumerate(lines):
            # 如果行包含prompt關鍵字，跳過這些行
            if any(keyword in line for keyword in [
                "作為一個專業的資訊科技教育內容寫作專家",
                "請根據以下資訊生成",
                "筆記標題：",
                "目前內容：",
                "增強要求：",
                "任務：",
                "請根據增強要求",
                "特別注意：",
                "請生成補充或改善的內容：",
                "---"
            ]):
                skip_lines = i + 1
                continue
            break
        
        # 從非prompt內容開始
        for i, line in enumerate(lines[skip_lines:], skip_lines):
            # 如果遇到明顯的內容開始標記，從這裡開始
            if line.strip().startswith('#') or line.strip().startswith('**') or (line.strip() and not any(keyword in line for keyword in ["作為", "請根據", "任務", "特別注意"])):
                processed_lines = lines[i:]
                break
        
        if not processed_lines:
            processed_lines = lines[skip_lines:]
        
        # 重新組合內容
        result = '\n'.join(processed_lines)
        
        # 清理多餘的空行
        import re
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        # 確保內容開頭和結尾沒有多餘的空行
        result = result.strip()
        
        # 確保換行符正確處理
        result = result.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
        
        return result

    def _get_fallback_enhancement(self, request: str) -> str:
        """獲取備用的內容增強"""
        timestamp = self._get_current_timestamp()
        
        return f"""## 內容增強

> 生成時間：{timestamp}
> 增強要求：{request}

### 📝 增強內容

*（AI 內容生成暫時不可用，請手動補充以下內容）*

#### 主要內容
- *（請根據要求補充具體內容）*
- *（請補充相關的說明或例子）*
- *（請補充重要的注意事項）*

#### 相關資源
- *（請補充相關的參考資料或連結）*
- *（請補充延伸學習的建議）*

---

> 💡 **提示：** 請手動編輯此區塊，根據增強要求補充具體內容。
"""


def hello_world():
    """測試函式"""
    return "Hello from Ghost AI Client!"
