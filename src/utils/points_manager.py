"""
v3.1 點數系統管理器
處理用戶點數的增減、驗證和記錄
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from ..core.database import DatabaseManager, User, PointTransaction, ContentValidation
import logging

logger = logging.getLogger(__name__)

class PointsManager:
    """點數系統管理器"""
    
    # 點數價格表
    POINT_COSTS = {
        'upload_document': 0,           # 上傳文件不扣分（但會檢查內容）
        'generate_quiz': 10,            # 生成完整考題：10分
        'generate_quiz_large': 30,      # 大型考題（>20題）：30分
        'generate_quiz_xl': 50,         # 超大考題（>50題）：50分
        'regenerate_answer': 10,        # 重新生成答案：10分
        'generate_mindmap': 5,          # 心智圖：5分
        'generate_techniques': 5,       # 解題技巧：5分
        'invalid_content_penalty': -4800,  # 違規內容懲罰：-4800分（48小時禁用）
    }
    
    MAX_POINTS = 100               # 點數上限
    HOURLY_REFILL = 100           # 每小時恢復點數
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def get_user_points(self, user_id: int) -> Dict[str, Any]:
        """獲取用戶當前點數狀態"""
        with self.db._session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return {"error": "用戶不存在"}
            
            # 檢查是否需要恢復點數
            self._refill_points_if_needed(session, user)
            
            # 檢查是否被禁用
            is_banned = self._check_ban_status(user)
            
            return {
                "points": user.points,
                "max_points": self.MAX_POINTS,
                "is_banned": is_banned,
                "ban_until": user.ban_until,
                "points_updated_at": user.points_updated_at
            }
    
    def can_afford(self, user_id: int, action_type: str, question_count: int = 0) -> Dict[str, Any]:
        """檢查用戶是否能負擔某個操作"""
        cost = self._calculate_cost(action_type, question_count)
        user_status = self.get_user_points(user_id)
        
        if user_status.get("error"):
            return user_status
        
        if user_status["is_banned"]:
            return {
                "can_afford": False,
                "reason": f"賬戶被禁用至 {user_status['ban_until']}",
                "cost": cost,
                "current_points": user_status["points"]
            }
        
        can_afford = user_status["points"] >= cost
        return {
            "can_afford": can_afford,
            "cost": cost,
            "current_points": user_status["points"],
            "remaining_after": user_status["points"] - cost if can_afford else None
        }
    
    def deduct_points(self, user_id: int, action_type: str, question_count: int = 0, 
                     description: str = None, document_id: int = None) -> Dict[str, Any]:
        """扣除用戶點數"""
        cost = self._calculate_cost(action_type, question_count)
        
        with self.db._session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "error": "用戶不存在"}
            
            # 檢查禁用狀態
            if self._check_ban_status(user):
                return {
                    "success": False, 
                    "error": f"賬戶被禁用至 {user.ban_until}"
                }
            
            # 檢查點數是否足夠
            if user.points < cost:
                return {
                    "success": False,
                    "error": f"點數不足。需要 {cost} 點，目前只有 {user.points} 點"
                }
            
            # 扣除點數
            points_before = user.points
            user.points -= cost
            user.points_updated_at = datetime.utcnow()
            
            # 記錄交易
            transaction = PointTransaction(
                user_id=user_id,
                action_type=action_type,
                points_change=-cost,
                points_before=points_before,
                points_after=user.points,
                description=description or f"{action_type}消耗",
                related_document_id=document_id
            )
            session.add(transaction)
            
            logger.info(f"用戶 {user.username} 執行 {action_type}，扣除 {cost} 點數")
            
            return {
                "success": True,
                "points_deducted": cost,
                "points_remaining": user.points,
                "action_type": action_type
            }
    
    def apply_penalty(self, user_id: int, document_id: int, validation_details: str) -> Dict[str, Any]:
        """對違規用戶應用懲罰"""
        penalty_points = self.POINT_COSTS['invalid_content_penalty']
        
        with self.db._session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "error": "用戶不存在"}
            
            points_before = user.points
            user.points += penalty_points  # 負數，實際是扣除
            user.is_banned = 1
            user.ban_until = datetime.utcnow() + timedelta(hours=48)
            user.points_updated_at = datetime.utcnow()
            
            # 記錄懲罰交易
            transaction = PointTransaction(
                user_id=user_id,
                action_type='invalid_content_penalty',
                points_change=penalty_points,
                points_before=points_before,
                points_after=user.points,
                description="違規內容上傳懲罰",
                related_document_id=document_id
            )
            session.add(transaction)
            
            logger.warning(f"用戶 {user.username} 上傳違規內容，被禁用48小時")
            
            return {
                "success": True,
                "penalty_applied": abs(penalty_points),
                "banned_until": user.ban_until,
                "remaining_points": user.points
            }
    
    def get_transaction_history(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """獲取用戶點數交易歷史"""
        with self.db._session_scope() as session:
            transactions = session.query(PointTransaction)\
                .filter(PointTransaction.user_id == user_id)\
                .order_by(PointTransaction.created_at.desc())\
                .limit(limit).all()
            
            return [{
                "id": t.id,
                "action_type": t.action_type,
                "points_change": t.points_change,
                "points_before": t.points_before,
                "points_after": t.points_after,
                "description": t.description,
                "created_at": t.created_at,
                "related_document_id": t.related_document_id
            } for t in transactions]
    
    def _calculate_cost(self, action_type: str, question_count: int = 0) -> int:
        """計算操作成本"""
        if action_type == 'generate_quiz':
            if question_count > 50:
                return self.POINT_COSTS['generate_quiz_xl']
            elif question_count > 20:
                return self.POINT_COSTS['generate_quiz_large']
            else:
                return self.POINT_COSTS['generate_quiz']
        
        return self.POINT_COSTS.get(action_type, 0)
    
    def _refill_points_if_needed(self, session: Session, user: User) -> None:
        """檢查並恢復點數"""
        now = datetime.utcnow()
        last_update = user.points_updated_at or user.created_at
        
        # 計算需要恢復的小時數
        hours_passed = int((now - last_update).total_seconds() / 3600)
        
        if hours_passed > 0 and user.points < self.MAX_POINTS:
            # 恢復點數，但不超過上限
            points_to_add = min(hours_passed * self.HOURLY_REFILL, 
                               self.MAX_POINTS - user.points)
            
            if points_to_add > 0:
                user.points += points_to_add
                user.points_updated_at = now
                
                # 記錄恢復交易
                transaction = PointTransaction(
                    user_id=user.id,
                    action_type='hourly_refill',
                    points_change=points_to_add,
                    points_before=user.points - points_to_add,
                    points_after=user.points,
                    description=f"每小時自動恢復點數 ({hours_passed}小時)"
                )
                session.add(transaction)
                session.commit()
    
    def _check_ban_status(self, user: User) -> bool:
        """檢查用戶是否被禁用"""
        if not user.is_banned:
            return False
        
        if user.ban_until and datetime.utcnow() > user.ban_until:
            # 禁用期已過，解除禁用
            with self.db._session_scope() as session:
                user_obj = session.query(User).filter(User.id == user.id).first()
                if user_obj:
                    user_obj.is_banned = 0
                    user_obj.ban_until = None
            return False
        
        return True
