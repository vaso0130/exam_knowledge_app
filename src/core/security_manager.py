"""
v3.0 安全管理器
提供用戶認證、授權、IP 黑名單等安全功能
"""

import secrets
import hashlib
import bcrypt
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from .database import DatabaseManager


class SecurityManager:
    """安全管理器 - 統一處理身份驗證和授權"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.max_failed_attempts = 3  # 最大失敗嘗試次數
        self.lockout_window_minutes = 60  # 鎖定時間窗口（分鐘）
        
        # 邀請碼設定
        self.invitation_codes = {
            "我想要在資訊局準時下班": "admin",  # 管理員邀請碼
            "資訊處理高考三級合格": "viewer"     # 檢視者邀請碼
        }
    
    # === 邀請碼驗證 ===
    
    def validate_invitation_code(self, code: str) -> Optional[str]:
        """
        驗證邀請碼
        返回對應的角色，如果無效返回None
        """
        return self.invitation_codes.get(code, None)
    
    # === 密碼處理 ===
    
    def hash_password(self, password: str) -> str:
        """使用 bcrypt 雜湊密碼"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """驗證密碼"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception:
            return False
    
    def generate_session_token(self) -> str:
        """生成安全的會話 token"""
        return secrets.token_urlsafe(32)
    
    # === 用戶認證 ===
    
    def authenticate_user(self, username: str, password: str, ip_address: str, 
                         user_agent: str = None) -> Dict[str, Any]:
        """
        用戶認證
        返回格式: {
            'success': bool,
            'user': dict or None,
            'session_token': str or None,
            'message': str,
            'blocked': bool  # IP 是否被封鎖
        }
        """
        result = {
            'success': False,
            'user': None,
            'session_token': None,
            'message': '',
            'blocked': False
        }
        
        # 1. 檢查 IP 是否在黑名單
        if self.db.is_ip_blacklisted(ip_address):
            result['blocked'] = True
            result['message'] = 'IP 地址已被封鎖'
            self.db.record_login_attempt(ip_address, username, success=False, user_agent=user_agent)
            return result
        
        # 2. 檢查該 IP 失敗嘗試次數
        failed_attempts = self.db.get_failed_attempts_count(ip_address, self.lockout_window_minutes)
        if failed_attempts >= self.max_failed_attempts:
            # 自動加入黑名單
            self.db.add_ip_to_blacklist(
                ip_address, 
                f"超過 {self.max_failed_attempts} 次登入失敗", 
                "系統自動"
            )
            result['blocked'] = True
            result['message'] = f'登入失敗次數過多，IP 已被封鎖'
            self.db.record_login_attempt(ip_address, username, success=False, user_agent=user_agent)
            return result
        
        # 3. 獲取用戶資料
        user = self.db.get_user_by_username(username)
        if not user:
            result['message'] = '用戶名稱或密碼錯誤'
            self.db.record_login_attempt(ip_address, username, success=False, user_agent=user_agent)
            return result
        
        # 4. 驗證密碼
        if not self.verify_password(password, user['password_hash']):
            result['message'] = '用戶名稱或密碼錯誤'
            self.db.record_login_attempt(ip_address, username, user['id'], success=False, user_agent=user_agent)
            return result
        
        # 5. 登入成功
        session_token = self.generate_session_token()
        self.db.create_user_session(user['id'], session_token, ip_address, user_agent)
        self.db.update_user_last_login(user['id'])
        self.db.record_login_attempt(ip_address, username, user['id'], success=True, user_agent=user_agent)
        
        # 移除敏感資訊
        safe_user = {k: v for k, v in user.items() if k != 'password_hash'}
        
        result.update({
            'success': True,
            'user': safe_user,
            'session_token': session_token,
            'message': '登入成功'
        })
        
        return result
    
    def logout_user(self, session_token: str) -> bool:
        """用戶登出"""
        return self.db.invalidate_session(session_token)
    
    def get_user_from_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """根據會話 token 獲取用戶資訊"""
        if not session_token:
            return None
        
        session = self.db.get_session(session_token)
        if not session:
            return None
        
        user = self.db.get_user_by_id(session['user_id'])
        if not user:
            # 會話存在但用戶不存在，清理會話
            self.db.invalidate_session(session_token)
            return None
        
        # 更新會話訪問時間
        self.db.update_session_access(session_token)
        
        return user
    
    # === 權限檢查 ===
    
    def check_permission(self, session_token: str, required_role: str = "viewer") -> bool:
        """
        檢查用戶權限
        角色層級: admin > viewer
        """
        user = self.get_user_from_session(session_token)
        if not user:
            return False
        
        user_role = user['role']
        
        # 管理員擁有所有權限
        if user_role == 'admin':
            return True
        
        # 檢查角色匹配
        if required_role == 'viewer' and user_role in ['viewer', 'admin']:
            return True
        
        return False
    
    def require_admin(self, session_token: str) -> bool:
        """檢查是否為管理員"""
        return self.check_permission(session_token, "admin")
    
    def require_login(self, session_token: str) -> bool:
        """檢查是否已登入（任何角色）"""
        return self.get_user_from_session(session_token) is not None
    
    # === 用戶管理 ===
    
    def create_user(self, username: str, password: str, role: str = "viewer", 
                   email: str = None, created_by_session: str = None) -> Dict[str, Any]:
        """
        創建新用戶（需要管理員權限）
        """
        result = {'success': False, 'message': '', 'user_id': None}
        
        # 檢查創建者權限（如果提供會話）
        if created_by_session and not self.require_admin(created_by_session):
            result['message'] = '需要管理員權限'
            return result
        
        # 檢查用戶是否已存在
        existing_user = self.db.get_user_by_username(username)
        if existing_user:
            result['message'] = '用戶名稱已存在'
            return result
        
        # 驗證角色
        if role not in ['admin', 'viewer']:
            result['message'] = '無效的角色'
            return result
        
        try:
            # 雜湊密碼
            password_hash = self.hash_password(password)
            
            # 創建用戶
            user_id = self.db.create_user(username, password_hash, role, email)
            
            result.update({
                'success': True,
                'message': '用戶創建成功',
                'user_id': user_id
            })
            
        except Exception as e:
            result['message'] = f'創建用戶失敗: {str(e)}'
        
        return result
    
    def change_password(self, session_token: str, old_password: str, new_password: str) -> Dict[str, Any]:
        """用戶修改密碼"""
        result = {'success': False, 'message': ''}
        
        user = self.get_user_from_session(session_token)
        if not user:
            result['message'] = '請先登入'
            return result
        
        # 獲取完整用戶資料（包含密碼雜湊）
        full_user = self.db.get_user_by_username(user['username'])
        if not full_user:
            result['message'] = '用戶不存在'
            return result
        
        # 驗證舊密碼
        if not self.verify_password(old_password, full_user['password_hash']):
            result['message'] = '舊密碼錯誤'
            return result
        
        try:
            # 更新密碼
            new_password_hash = self.hash_password(new_password)
            self.db.update_user_password(user['id'], new_password_hash)
            
            # 使所有會話失效，強制重新登入
            self.db.invalidate_user_sessions(user['id'])
            
            result.update({
                'success': True,
                'message': '密碼修改成功，請重新登入'
            })
            
        except Exception as e:
            result['message'] = f'修改密碼失敗: {str(e)}'
        
        return result
    
    # === IP 管理 ===
    
    def unblock_ip(self, ip_address: str, admin_session: str) -> Dict[str, Any]:
        """解除 IP 封鎖（需要管理員權限）"""
        result = {'success': False, 'message': ''}
        
        if not self.require_admin(admin_session):
            result['message'] = '需要管理員權限'
            return result
        
        try:
            success = self.db.remove_ip_from_blacklist(ip_address)
            if success:
                result.update({
                    'success': True,
                    'message': f'IP {ip_address} 已解除封鎖'
                })
            else:
                result['message'] = 'IP 不在黑名單中'
        except Exception as e:
            result['message'] = f'解除封鎖失敗: {str(e)}'
        
        return result
    
    def manual_block_ip(self, ip_address: str, reason: str, admin_session: str) -> Dict[str, Any]:
        """手動封鎖 IP（需要管理員權限）"""
        result = {'success': False, 'message': ''}
        
        admin_user = self.get_user_from_session(admin_session)
        if not admin_user or not self.require_admin(admin_session):
            result['message'] = '需要管理員權限'
            return result
        
        try:
            self.db.add_ip_to_blacklist(ip_address, reason, admin_user['username'])
            result.update({
                'success': True,
                'message': f'IP {ip_address} 已加入黑名單'
            })
        except Exception as e:
            result['message'] = f'封鎖 IP 失敗: {str(e)}'
        
        return result
    
    # === 系統維護 ===
    
    def cleanup_sessions(self, hours: int = 24) -> int:
        """清理過期會話"""
        return self.db.cleanup_expired_sessions(hours)
    
    def get_security_stats(self, admin_session: str) -> Optional[Dict[str, Any]]:
        """獲取安全統計（管理員專用）"""
        if not self.require_admin(admin_session):
            return None
        
        try:
            blacklisted_ips = self.db.get_blacklisted_ips()
            recent_attempts = self.db.get_login_attempts(50)
            all_users = self.db.get_all_users()
            
            # 統計分析
            failed_attempts_today = len([
                a for a in recent_attempts 
                if not a['success'] and 
                datetime.fromisoformat(a['attempt_time']).date() == datetime.now().date()
            ])
            
            active_users = len([u for u in all_users if u['is_active']])
            
            return {
                'blacklisted_ips_count': len(blacklisted_ips),
                'failed_attempts_today': failed_attempts_today,
                'total_users': len(all_users),
                'active_users': active_users,
                'blacklisted_ips': blacklisted_ips[:10],  # 最近 10 個
                'recent_attempts': recent_attempts[:20]   # 最近 20 次嘗試
            }
        except Exception:
            return None
