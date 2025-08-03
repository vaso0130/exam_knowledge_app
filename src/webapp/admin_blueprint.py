"""
v3.0 主系統管理員藍圖 - 僅提供統計顯示，無操作功能
所有管理操作都引導到本地管理介面
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime, timedelta
from ..core.security_manager import SecurityManager
from ..core.database import DatabaseManager
from .auth_middleware import require_admin

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@require_admin
def dashboard():
    """管理員儀表板 - 僅顯示統計，無操作功能"""
    security_manager: SecurityManager = current_app.security_manager
    db_manager: DatabaseManager = current_app.db_manager
    
    # 獲取系統統計
    try:
        all_users = db_manager.get_all_users()
        blacklisted_ips = db_manager.get_blacklisted_ips()
        recent_attempts = db_manager.get_login_attempts(20)
        
        # 計算統計數據
        total_users = len(all_users)
        active_users = len([u for u in all_users if u['is_active']])
        admin_users = len([u for u in all_users if u['role'] == 'admin'])
        
        failed_attempts_today = len([
            a for a in recent_attempts 
            if not a['success'] and 
            datetime.fromisoformat(a['attempt_time']).date() == datetime.now().date()
        ])
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'admin_users': admin_users,
            'blacklisted_ips': len(blacklisted_ips),
            'failed_attempts_today': failed_attempts_today,
            'recent_attempts': recent_attempts[:10]  # 最近 10 次
        }
        
    except Exception as e:
        flash(f'獲取統計資料失敗: {str(e)}', 'error')
        stats = {}
    
    return render_template('admin/readonly_dashboard.html', stats=stats)


@admin_bp.route('/manage-locally')
@require_admin
def manage_locally():
    """引導到本地管理的說明頁面"""
    return render_template('admin/local_management_guide.html')


# 移除所有操作相關的路由
# 不再提供 create_user, edit_user, toggle_user 等功能
# 這些功能只能在本地管理介面中執行

# 移除所有操作相關的路由
# 不再提供 create_user, edit_user, toggle_user 等功能
# 這些功能只能在本地管理介面中執行
