"""
v3.0 Flask 權限裝飾器與中介軟體
"""

from functools import wraps
from flask import request, session, redirect, url_for, flash, jsonify, g
from typing import Optional, Dict, Any

from ..core.security_manager import SecurityManager
from ..core.database import DatabaseManager


class AuthMiddleware:
    """認證中介軟體"""
    
    def __init__(self, app=None, db_manager: DatabaseManager = None):
        self.db = db_manager
        self.security = SecurityManager(db_manager) if db_manager else None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """初始化 Flask 應用"""
        app.before_request(self.check_ip_blacklist)
        app.before_request(self.load_user)
    
    def check_ip_blacklist(self):
        """檢查 IP 是否在黑名單中"""
        if not self.db:
            return
        
        client_ip = self.get_client_ip()
        
        # 如果是本地 IP，跳過檢查
        if client_ip in ['127.0.0.1', 'localhost', '::1']:
            return
        
        if self.db.is_ip_blacklisted(client_ip):
            return jsonify({
                'error': 'IP 地址已被封鎖',
                'message': '如有疑問請聯繫管理員'
            }), 403
    
    def load_user(self):
        """載入當前用戶資訊"""
        g.current_user = None
        
        if not self.security:
            return
        
        session_token = session.get('session_token')
        if session_token:
            user = self.security.get_user_from_session(session_token)
            if user:
                g.current_user = user
            else:
                # 會話無效，清除
                session.pop('session_token', None)
    
    def get_client_ip(self) -> str:
        """獲取客戶端 IP 地址"""
        # 檢查 X-Forwarded-For 標頭（代理伺服器）
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        
        # 檢查 X-Real-IP 標頭
        if request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        
        # 使用遠端地址
        return request.remote_addr or '127.0.0.1'


def require_login(f):
    """需要登入的裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.current_user:
            flash('請先登入', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def require_role(required_role: str):
    """需要特定角色的裝飾器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not g.current_user:
                flash('請先登入', 'warning')
                return redirect(url_for('auth.login'))
            
            user_role = g.current_user.get('role')
            
            # 管理員擁有所有權限
            if user_role == 'admin':
                return f(*args, **kwargs)
            
            # 檢查角色匹配
            if required_role == 'viewer' and user_role in ['viewer', 'admin']:
                return f(*args, **kwargs)
            
            # 權限不足
            flash('權限不足', 'error')
            return redirect(url_for('main.dashboard'))
        
        return decorated_function
    return decorator


def require_admin(f):
    """需要管理員權限的裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.current_user:
            flash('請先登入', 'warning')
            return redirect(url_for('auth.login'))
        
        if g.current_user.get('role') != 'admin':
            flash('需要管理員權限', 'error')
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


def require_viewer(f):
    """需要檢視者權限的裝飾器（admin 和 viewer 都可以）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.current_user:
            flash('請先登入', 'warning')
            return redirect(url_for('auth.login'))
        
        user_role = g.current_user.get('role')
        if user_role not in ['admin', 'viewer']:
            flash('權限不足', 'error')
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


def login_user(user: Dict[str, Any], session_token: str) -> None:
    """用戶登入，設置會話"""
    session['session_token'] = session_token
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session.permanent = True  # 持久會話


def logout_user() -> None:
    """用戶登出，清除會話"""
    session_token = session.get('session_token')
    
    # 清除資料庫中的會話
    if session_token:
        try:
            from flask import current_app
            security_manager = current_app.security_manager
            security_manager.logout_user(session_token)
        except Exception:
            pass  # 靜默處理錯誤
    
    # 清除所有會話資料
    session.clear()


def is_authenticated() -> bool:
    """檢查用戶是否已認證"""
    return g.current_user is not None


def is_admin() -> bool:
    """檢查用戶是否為管理員"""
    return g.current_user and g.current_user.get('role') == 'admin'


def get_current_user() -> Optional[Dict[str, Any]]:
    """獲取當前用戶資訊"""
    return g.current_user


def get_user_role() -> Optional[str]:
    """獲取當前用戶角色"""
    return g.current_user.get('role') if g.current_user else None
