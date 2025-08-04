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
    
    return render_template('admin_dashboard.html', stats=stats)


@admin_bp.route('/maintenance')
@require_admin  
def maintenance():
    """資料庫維護頁面"""
    db_manager: DatabaseManager = current_app.db_manager
    
    try:
        # 獲取維護統計資訊
        maintenance_stats = db_manager.comprehensive_cleanup(dry_run=True)
        orphaned_details = db_manager.get_orphaned_knowledge_points_details()
        
        stats = {
            'orphaned_knowledge_points': maintenance_stats['orphaned_knowledge_points'],
            'expired_sessions': maintenance_stats['expired_sessions'], 
            'old_async_jobs': maintenance_stats['old_async_jobs'],
            'old_login_attempts': maintenance_stats['old_login_attempts'],
            'orphaned_details': orphaned_details[:20]  # 只顯示前20個
        }
        
    except Exception as e:
        flash(f'獲取維護資訊失敗: {str(e)}', 'error')
        stats = {}
    
    return render_template('admin_maintenance.html', stats=stats)


@admin_bp.route('/maintenance/cleanup', methods=['POST'])
@require_admin
def maintenance_cleanup():
    """執行資料庫清理"""
    db_manager: DatabaseManager = current_app.db_manager
    
    try:
        cleanup_type = request.form.get('cleanup_type', 'full')
        
        if cleanup_type == 'orphaned_only':
            # 只清理孤立知識點
            count = db_manager.clean_orphaned_knowledge_points()
            flash(f'成功清理 {count} 個孤立知識點', 'success')
        else:
            # 全面清理
            stats = db_manager.comprehensive_cleanup(dry_run=False)
            total = sum(stats.values())
            flash(f'資料庫清理完成！清理了 {total} 個項目', 'success')
            
            if stats['orphaned_knowledge_points'] > 0:
                flash(f'- 孤立知識點: {stats["orphaned_knowledge_points"]} 個', 'info')
            if stats['expired_sessions'] > 0:
                flash(f'- 過期會話: {stats["expired_sessions"]} 個', 'info') 
            if stats['old_async_jobs'] > 0:
                flash(f'- 舊非同步工作: {stats["old_async_jobs"]} 個', 'info')
            if stats['old_login_attempts'] > 0:
                flash(f'- 舊登入記錄: {stats["old_login_attempts"]} 個', 'info')
    
    except Exception as e:
        flash(f'清理過程中發生錯誤: {str(e)}', 'error')
    
    return redirect(url_for('admin.maintenance'))


@admin_bp.route('/api/maintenance/stats')
@require_admin
def api_maintenance_stats():
    """API: 獲取維護統計資訊"""
    db_manager: DatabaseManager = current_app.db_manager
    
    try:
        stats = db_manager.comprehensive_cleanup(dry_run=True)
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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
