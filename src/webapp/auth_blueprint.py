"""
v3.0 認證藍圖 - 處理登入、登出等認證相關功能
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, g
from ..core.security_manager import SecurityManager
from ..core.database import DatabaseManager
from .auth_middleware import login_user, logout_user, get_client_ip

auth_bp = Blueprint('auth', __name__, url_prefix='')


def get_client_ip() -> str:
    """獲取客戶端 IP 地址"""
    # 檢查 X-Forwarded-For 標頭（代理伺服器）
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    
    # 檢查 X-Real-IP 標頭
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    
    # 使用遠端地址
    return request.remote_addr or '127.0.0.1'


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """登入頁面"""
    # 如果已經登入，重定向到儀表板
    if g.current_user:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'GET':
        return render_template('auth/login.html')
    
    # POST 請求 - 處理登入
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    
    if not username or not password:
        flash('請輸入用戶名稱和密碼', 'error')
        return render_template('auth/login.html')
    
    # 獲取 SecurityManager
    security_manager: SecurityManager = current_app.security_manager
    
    # 獲取客戶端資訊
    client_ip = get_client_ip()
    user_agent = request.headers.get('User-Agent', '')
    
    # 嘗試認證
    auth_result = security_manager.authenticate_user(
        username=username,
        password=password,
        ip_address=client_ip,
        user_agent=user_agent
    )
    
    if auth_result['blocked']:
        flash('IP 地址已被封鎖，如有疑問請聯繫管理員', 'error')
        return render_template('auth/login.html'), 403
    
    if not auth_result['success']:
        flash(auth_result['message'], 'error')
        return render_template('auth/login.html')
    
    # 登入成功
    user = auth_result['user']
    session_token = auth_result['session_token']
    
    # 設置會話
    login_user(user, session_token)
    
    flash(f'歡迎回來，{user["username"]}！', 'success')
    
    # 重定向到原來想訪問的頁面，或者儀表板
    next_page = request.args.get('next')
    if next_page:
        return redirect(next_page)
    
    return redirect(url_for('main.dashboard'))


@auth_bp.route('/logout')
def logout():
    """登出"""
    if g.current_user:
        logout_user()
        flash('已成功登出', 'success')
    
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
def profile():
    """個人資料頁面"""
    from .auth_middleware import require_login
    
    @require_login
    def _profile():
        return render_template('auth/profile.html', user=g.current_user)
    
    return _profile()


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """修改密碼"""
    from .auth_middleware import require_login
    
    @require_login
    def _change_password():
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not all([old_password, new_password, confirm_password]):
            flash('請填寫所有密碼欄位', 'error')
            return redirect(url_for('auth.profile'))
        
        if new_password != confirm_password:
            flash('新密碼與確認密碼不符', 'error')
            return redirect(url_for('auth.profile'))
        
        if len(new_password) < 6:
            flash('密碼長度至少 6 個字元', 'error')
            return redirect(url_for('auth.profile'))
        
        # 使用 SecurityManager 修改密碼
        security_manager: SecurityManager = current_app.security_manager
        session_token = session.get('session_token')
        
        result = security_manager.change_password(
            session_token=session_token,
            old_password=old_password,
            new_password=new_password
        )
        
        if result['success']:
            # 密碼修改成功，強制重新登入
            logout_user()
            flash('密碼修改成功，請重新登入', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(result['message'], 'error')
            return redirect(url_for('auth.profile'))
    
    return _change_password()


@auth_bp.context_processor
def inject_auth_info():
    """注入認證相關資訊到模板中"""
    return {
        'current_user': g.current_user,
        'is_authenticated': g.current_user is not None,
        'is_admin': g.current_user and g.current_user.get('role') == 'admin'
    }
