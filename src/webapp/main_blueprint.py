"""
v3.0 主要藍圖 - 處理一般用戶功能與儀表板
"""

from flask import Blueprint, render_template, redirect, url_for, g
from .auth_middleware import require_login

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """首頁 - 重定向到儀表板或登入頁面"""
    if g.current_user:
        return redirect(url_for('main.dashboard'))
    else:
        return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@require_login
def dashboard():
    """用戶儀表板"""
    user = g.current_user
    
    # 所有用戶看到相同的儀表板，只是會顯示不同的角色標識
    return render_template('dashboard/user_dashboard.html', user=user)


@main_bp.context_processor
def inject_navigation():
    """注入導航資訊到模板中"""
    navigation = []
    
    if g.current_user:
        # 所有用戶的基本導航
        navigation.extend([
            {'name': '儀表板', 'url': url_for('main.dashboard'), 'icon': 'dashboard'},
            {'name': '文件庫', 'url': '/documents', 'icon': 'folder'},
            {'name': '知識點', 'url': '/knowledge', 'icon': 'lightbulb'},
            {'name': '問題集', 'url': '/questions', 'icon': 'help'},
        ])
        
        # 管理員會看到一個本地管理提示
        if g.current_user.get('role') == 'admin':
            navigation.append({
                'name': '系統管理', 
                'url': '#', 
                'icon': 'settings',
                'tooltip': '請使用本地管理工具進行系統管理'
            })
    
    return {'navigation': navigation}
