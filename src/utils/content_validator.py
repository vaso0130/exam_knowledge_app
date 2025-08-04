"""
v3.1 內容驗證器
使用 AI 檢查上傳內容是否為考試或學習相關材料
"""

import json
import logging
from typing import Dict, Any, Optional
from ..core.gemini_client import GeminiClient
from ..core.database import DatabaseManager, ContentValidation

logger = logging.getLogger(__name__)

class ContentValidator:
    """內容驗證器"""
    
    def __init__(self, gemini_client: GeminiClient, db_manager: DatabaseManager):
        self.gemini = gemini_client
        self.db = db_manager
    
    def validate_content_sync(self, document_id: int, content: str, user_id: int) -> Dict[str, Any]:
        """同步版本的內容驗證方法，用於非異步環境"""
        import asyncio
        
        try:
            # 檢查是否已經在事件循環中
            try:
                loop = asyncio.get_running_loop()
                # 如果已經在事件循環中，在新線程中運行
                import concurrent.futures
                import threading
                
                result_container = {'result': None, 'error': None}
                
                def run_validation():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result = new_loop.run_until_complete(
                                self.validate_content(document_id, content, user_id)
                            )
                            result_container['result'] = result
                        finally:
                            new_loop.close()
                    except Exception as e:
                        result_container['error'] = e
                
                thread = threading.Thread(target=run_validation)
                thread.start()
                thread.join(timeout=60)  # 60秒超時
                
                if thread.is_alive():
                    return {
                        "is_valid": False,
                        "confidence": 0.0,
                        "reason": "驗證超時，為安全起見拒絕處理",
                        "details": "內容驗證超時"
                    }
                    
                if result_container['error']:
                    raise result_container['error']
                    
                return result_container['result']
                
            except RuntimeError:
                # 沒有運行的事件循環，可以直接使用 asyncio.run
                return asyncio.run(self.validate_content(document_id, content, user_id))
                
        except Exception as e:
            logger.error(f"同步內容驗證失敗: {str(e)}")
            return {
                "is_valid": False,
                "confidence": 0.0,
                "reason": "驗證系統錯誤，為安全起見拒絕處理",
                "details": f"驗證過程中發生錯誤: {str(e)}"
            }

    async def validate_content(self, document_id: int, content: str, user_id: int) -> Dict[str, Any]:
        """
        驗證內容是否為考試或學習相關
        
        Returns:
            {
                "is_valid": bool,
                "confidence": float,
                "reason": str,
                "details": str
            }
        """
        
        # 構建驗證提示
        validation_prompt = self._build_validation_prompt(content)
        
        try:
            # 使用輔助模型進行內容驗證 (更經濟實惠的簡單分類任務)
            response = await self.gemini.generate_async_simple(validation_prompt, is_json=True)
            
            # 解析 AI 回應
            validation_result = self._parse_validation_response(response)
            
            # 只有在 document_id > 0 時才記錄驗證結果到資料庫
            if document_id > 0:
                self._save_validation_record(
                    document_id=document_id,
                    user_id=user_id,
                    is_valid=validation_result["is_valid"],
                    confidence=validation_result["confidence"],
                    details=validation_result["details"]
                )
            
            logger.info(f"內容驗證完成: 文件ID={document_id}, 有效={validation_result['is_valid']}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"內容驗證失敗: {str(e)}")
            # 發生錯誤時預設為無效，採用更嚴格的安全策略
            return {
                "is_valid": False,
                "confidence": 0.0,
                "reason": "驗證系統錯誤，為安全起見拒絕處理",
                "details": f"驗證過程中發生錯誤，請稍後重試: {str(e)}"
            }
    
    def _build_validation_prompt(self, content: str) -> str:
        """構建內容驗證提示"""
        
        # 截取內容前1000字符進行分析（避免太長）
        content_sample = content[:1000] if len(content) > 1000 else content
        
        prompt = f"""
你是一個開放且包容的教育內容審核員。請分析以下內容是否包含有價值的學習知識，即使內容帶有商業性質也可以接受。

**重要：請採用開放標準，只要內容包含技術知識、新概念或教育價值，都應該通過驗證！**

**審核標準：**
✅ 有效內容（應該接受）：
- 考試題目、練習題、模擬考試
- 課程教材、教學講義、學習筆記
- 學術論文、研究資料、技術文檔
- 教學影片文字稿、課程大綱
- 學習指南、複習資料、知識點整理
- 專業技能培訓內容、證照考試資料
- **科技/資訊技術相關的新聞報導**
- **介紹新技術、新概念的商業文章或產品介紹（如AI、大數據、雲端運算、CRM、ERP等）**
- **包含技術原理說明的行銷內容**
- **產業趨勢分析、技術發展文章**
- **新工具、新方法的使用教學**

❌ 無效內容（必須拒絕）：
- 純娛樂內容（遊戲、影視、體育等，除非與技術相關）
- 個人生活記錄、日記、聊天記錄（除非包含技術討論）
- 純商業促銷（不含技術說明的廣告）
- 小說、故事、文學作品（除非是技術相關教材）
- 違法、色情、暴力內容
- 垃圾郵件、詐騙信息
- 完全無關學習或技術的日常生活內容

**待審核內容：**
```
{content_sample}
```

**回應格式（必須是有效的JSON）：**
{{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "reason": "判斷理由",
    "category": "內容類別",
    "details": "詳細說明"
}}

請嚴格按照JSON格式回應，不要添加其他文字。
"""
        return prompt
    
    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """解析 AI 驗證回應"""
        try:
            # 嘗試解析 JSON
            result = json.loads(response.strip())
            
            # 驗證必要欄位
            is_valid = bool(result.get("is_valid", True))
            confidence = float(result.get("confidence", 0.5))
            reason = str(result.get("reason", "未提供理由"))
            category = str(result.get("category", "未分類"))
            details = str(result.get("details", "未提供詳細說明"))
            
            # 確保 confidence 在合理範圍內
            confidence = max(0.0, min(1.0, confidence))
            
            return {
                "is_valid": is_valid,
                "confidence": confidence,
                "reason": reason,
                "category": category,
                "details": f"類別: {category}. {details}"
            }
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"無法解析 AI 回應: {response[:100]}... 錯誤: {str(e)}")
            
            # 嘗試從文字中提取判斷
            response_lower = response.lower()
            
            # 簡單的關鍵字判斷
            if any(word in response_lower for word in ['true', '有效', '接受', '通過', '考試', '學習', '教育']):
                is_valid = True
                reason = "關鍵字判斷為有效內容"
            else:
                is_valid = False
                reason = "無法確認為學習內容，預設拒絕"
            
            return {
                "is_valid": is_valid,
                "confidence": 0.5,
                "reason": reason,
                "category": "解析失敗",
                "details": f"AI回應解析失敗，原始回應: {response[:200]}"
            }
    
    def _save_validation_record(self, document_id: int, user_id: int, 
                               is_valid: bool, confidence: float, details: str) -> None:
        """保存驗證記錄到資料庫"""
        try:
            with self.db._session_scope() as session:
                validation_record = ContentValidation(
                    document_id=document_id,
                    user_id=user_id,
                    is_valid_content=1 if is_valid else 0,
                    confidence_score=confidence,
                    validation_details=details,
                    penalty_applied=0
                )
                session.add(validation_record)
                
        except Exception as e:
            logger.error(f"保存驗證記錄失敗: {str(e)}")
    
    def get_validation_history(self, user_id: Optional[int] = None, 
                             limit: int = 50) -> list:
        """獲取驗證歷史記錄"""
        try:
            with self.db._session_scope() as session:
                query = session.query(ContentValidation)
                
                if user_id:
                    query = query.filter(ContentValidation.user_id == user_id)
                
                validations = query.order_by(ContentValidation.created_at.desc())\
                                 .limit(limit).all()
                
                return [{
                    "id": v.id,
                    "document_id": v.document_id,
                    "user_id": v.user_id,
                    "is_valid": bool(v.is_valid_content),
                    "confidence": v.confidence_score,
                    "details": v.validation_details,
                    "penalty_applied": bool(v.penalty_applied),
                    "created_at": v.created_at
                } for v in validations]
                
        except Exception as e:
            logger.error(f"獲取驗證歷史失敗: {str(e)}")
            return []
    
    def get_user_violation_count(self, user_id: int, days: int = 30) -> int:
        """獲取用戶在指定天數內的違規次數"""
        try:
            from datetime import datetime, timedelta
            
            with self.db._session_scope() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                violation_count = session.query(ContentValidation)\
                    .filter(ContentValidation.user_id == user_id)\
                    .filter(ContentValidation.is_valid_content == 0)\
                    .filter(ContentValidation.created_at >= cutoff_date)\
                    .count()
                
                return violation_count
                
        except Exception as e:
            logger.error(f"獲取用戶違規次數失敗: {str(e)}")
            return 0
