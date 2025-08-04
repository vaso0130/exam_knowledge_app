#!/usr/bin/env python3
"""
v3.0 本地管理伺服器
獨立運行在隨機 port，僅限本地訪問的管理介面
"""

import os
import sys
import socket
import random
import webbrowser
from threading import Timer

# 添加專案根目錄到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from datetime import datetime, timedelta

from src.core.database import DatabaseManager
from src.core.security_manager import SecurityManager


def find_free_port():
    """找到一個可用的隨機端口"""
    while True:
        port = random.randint(8002, 9999)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('127.0.0.1', port))
            sock.close()
            return port
        except OSError:
            continue


def create_admin_app():
    """創建管理應用"""
    app = Flask(__name__, template_folder='templates')
    app.secret_key = os.urandom(24)  # 隨機生成密鑰
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)  # 2小時後自動登出
    
    # 初始化管理器
    try:
        db_manager = DatabaseManager()
        security_manager = SecurityManager(db_manager)
        app.db_manager = db_manager
        app.security_manager = security_manager
    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        sys.exit(1)
    
    # 僅允許本地訪問的中介軟體
    @app.before_request
    def local_only():
        """確保只能本地訪問"""
        if request.remote_addr not in ['127.0.0.1', '::1']:
            return "❌ 僅允許本地訪問", 403
    
    @app.before_request
    def load_admin():
        """載入管理員資訊"""
        g.admin = None
        admin_id = session.get('admin_id')
        if admin_id:
            user = db_manager.get_user_by_id(admin_id)
            if user and user['role'] == 'admin' and user['is_active']:
                g.admin = user
            else:
                session.clear()
    
    # === 認證相關 ===
    
    @app.route('/')
    def index():
        """首頁"""
        if g.admin:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """管理員登入"""
        if g.admin:
            return redirect(url_for('dashboard'))
        
        if request.method == 'GET':
            return render_template('admin_login.html')
        
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('請輸入用戶名稱和密碼', 'error')
            return render_template('admin_login.html')
        
        # 檢查是否為管理員
        user = db_manager.get_user_by_username(username)
        if not user or user['role'] != 'admin' or not user['is_active']:
            flash('無效的管理員帳號', 'error')
            return render_template('admin_login.html')
        
        # 驗證密碼
        if not security_manager.verify_password(password, user['password_hash']):
            flash('密碼錯誤', 'error')
            return render_template('admin_login.html')
        
        # 登入成功 - 更新最後登入時間
        db_manager.update_user_last_login(user['id'])
        
        session['admin_id'] = user['id']
        session['admin_username'] = user['username']
        session.permanent = True
        
        flash(f'歡迎，{username} 管理員！', 'success')
        return redirect(url_for('dashboard'))
    
    @app.route('/logout')
    def logout():
        """登出"""
        session.clear()
        flash('已登出', 'success')
        return redirect(url_for('login'))
    
    def require_admin(f):
        """需要管理員權限的裝飾器"""
        def wrapper(*args, **kwargs):
            if not g.admin:
                flash('請先登入', 'warning')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    
    # === 儀表板 ===
    
    @app.route('/dashboard')
    @require_admin
    def dashboard():
        """管理員儀表板"""
        try:
            all_users = db_manager.get_all_users()
            blacklisted_ips = db_manager.get_blacklisted_ips()
            recent_attempts = db_manager.get_login_attempts(20)
            
            stats = {
                'total_users': len(all_users),
                'active_users': len([u for u in all_users if u['is_active']]),
                'admin_users': len([u for u in all_users if u['role'] == 'admin']),
                'blacklisted_ips': len(blacklisted_ips),
                'failed_attempts_today': len([
                    a for a in recent_attempts 
                    if not a['success'] and 
                    datetime.fromisoformat(a['attempt_time']).date() == datetime.now().date()
                ]),
                'recent_attempts': recent_attempts[:10]
            }
        except Exception as e:
            flash(f'獲取統計資料失敗: {str(e)}', 'error')
            stats = {}
        
        return render_template('admin_dashboard.html', stats=stats)
    
    # === 用戶管理 ===
    
    @app.route('/users')
    @require_admin
    def users_list():
        """用戶列表"""
        try:
            users = db_manager.get_all_users()
            return render_template('admin_users.html', users=users)
        except Exception as e:
            flash(f'獲取用戶列表失敗: {str(e)}', 'error')
            return render_template('admin_users.html', users=[])
    
    @app.route('/users/create', methods=['GET', 'POST'])
    @require_admin
    def create_user():
        """創建用戶"""
        if request.method == 'GET':
            return render_template('admin_create_user.html')
        
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'viewer')
        email = request.form.get('email', '').strip() or None
        
        if not username or not password:
            flash('用戶名稱和密碼不能為空', 'error')
            return render_template('admin_create_user.html')
        
        if role not in ['admin', 'viewer']:
            flash('無效的角色', 'error')
            return render_template('admin_create_user.html')
        
        if len(password) < 6:
            flash('密碼長度至少 6 個字元', 'error')
            return render_template('admin_create_user.html')
        
        try:
            password_hash = security_manager.hash_password(password)
            user_id = db_manager.create_user(username, password_hash, role, email)
            flash(f'用戶 "{username}" 創建成功', 'success')
            return redirect(url_for('users_list'))
        except Exception as e:
            flash(f'創建用戶失敗: {str(e)}', 'error')
            return render_template('admin_create_user.html')
    
    @app.route('/users/<int:user_id>/toggle', methods=['POST'])
    @require_admin
    def toggle_user(user_id):
        """啟用/停用用戶"""
        user = db_manager.get_user_by_id(user_id, include_inactive=True)
        if not user:
            flash('用戶不存在', 'error')
            return redirect(url_for('users_list'))
        
        try:
            if user['is_active']:
                db_manager.disable_user(user_id)
                db_manager.invalidate_user_sessions(user_id)
                flash(f'用戶 "{user["username"]}" 已停用', 'success')
            else:
                db_manager.enable_user(user_id)
                flash(f'用戶 "{user["username"]}" 已啟用', 'success')
        except Exception as e:
            flash(f'操作失敗: {str(e)}', 'error')
        
        return redirect(url_for('users_list'))
    
    @app.route('/users/<int:user_id>/delete', methods=['POST'])
    @require_admin
    def delete_user(user_id):
        """刪除用戶"""
        user = db_manager.get_user_by_id(user_id, include_inactive=True)
        if not user:
            flash('用戶不存在', 'error')
            return redirect(url_for('users_list'))
        
        # 防止刪除自己
        if user_id == g.admin['id']:
            flash('不能刪除自己的帳號', 'error')
            return redirect(url_for('users_list'))
        
        try:
            # 先使所有會話失效
            db_manager.invalidate_user_sessions(user_id)
            # 刪除用戶
            success = db_manager.delete_user(user_id)
            if success:
                flash(f'用戶 "{user["username"]}" 已刪除', 'success')
            else:
                flash('刪除用戶失敗', 'error')
        except Exception as e:
            flash(f'刪除失敗: {str(e)}', 'error')
        
        return redirect(url_for('users_list'))
    
    @app.route('/users/<int:user_id>/reset-password', methods=['GET', 'POST'])
    @require_admin
    def reset_password(user_id):
        """重設密碼"""
        user = db_manager.get_user_by_id(user_id, include_inactive=True)
        if not user:
            flash('用戶不存在', 'error')
            return redirect(url_for('users_list'))
        
        if request.method == 'GET':
            return render_template('admin_reset_password.html', user=user)
        
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not new_password or new_password != confirm_password:
            flash('密碼不符或為空', 'error')
            return render_template('admin_reset_password.html', user=user)
        
        if len(new_password) < 6:
            flash('密碼長度至少 6 個字元', 'error')
            return render_template('admin_reset_password.html', user=user)
        
        try:
            new_password_hash = security_manager.hash_password(new_password)
            db_manager.update_user_password(user_id, new_password_hash)
            db_manager.invalidate_user_sessions(user_id)
            flash(f'用戶 "{user["username"]}" 密碼已重設', 'success')
            return redirect(url_for('users_list'))
        except Exception as e:
            flash(f'重設密碼失敗: {str(e)}', 'error')
            return render_template('admin_reset_password.html', user=user)
    
    @app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
    @require_admin
    def edit_user(user_id):
        """編輯用戶資訊"""
        user = db_manager.get_user_by_id(user_id, include_inactive=True)
        if not user:
            flash('用戶不存在', 'error')
            return redirect(url_for('users_list'))
        
        if request.method == 'GET':
            return render_template('admin_edit_user.html', user=user)
        
        # 獲取表單資料
        username = request.form.get('username', '').strip()
        role = request.form.get('role', '')
        email = request.form.get('email', '').strip() or None
        
        if not username:
            flash('用戶名稱不能為空', 'error')
            return render_template('admin_edit_user.html', user=user)
        
        if role not in ['admin', 'viewer']:
            flash('無效的角色', 'error')
            return render_template('admin_edit_user.html', user=user)
        
        # 檢查用戶名是否被其他用戶使用
        if username != user['username']:
            existing_user = db_manager.get_user_by_username(username)
            if existing_user:
                flash('用戶名稱已被使用', 'error')
                return render_template('admin_edit_user.html', user=user)
        
        try:
            # 更新用戶資訊
            success = db_manager.update_user_info(user_id, username, role, email)
            if success:
                flash(f'用戶 "{username}" 資訊已更新', 'success')
                return redirect(url_for('users_list'))
            else:
                flash('更新用戶資訊失敗', 'error')
        except Exception as e:
            flash(f'更新失敗: {str(e)}', 'error')
        
        return render_template('admin_edit_user.html', user=user)
    
    # === 安全管理 ===
    
    @app.route('/security')
    @require_admin
    def security_overview():
        """安全概覽"""
        try:
            blacklisted_ips = db_manager.get_blacklisted_ips()
            recent_attempts = db_manager.get_login_attempts(50)
            invite_attempts = db_manager.get_invite_code_attempts(50)  # 獲取最近50次邀請碼嘗試
            return render_template('admin_security.html', 
                                 blacklisted_ips=blacklisted_ips,
                                 recent_attempts=recent_attempts,
                                 invite_attempts=invite_attempts)
        except Exception as e:
            flash(f'獲取安全資料失敗: {str(e)}', 'error')
            return render_template('admin_security.html', 
                                 blacklisted_ips=[], recent_attempts=[], invite_attempts=[])
    
    @app.route('/security/unblock/<ip_address>', methods=['POST'])
    @require_admin
    def unblock_ip(ip_address):
        """解除 IP 封鎖"""
        try:
            success = db_manager.remove_ip_from_blacklist(ip_address)
            if success:
                flash(f'IP {ip_address} 已解除封鎖', 'success')
            else:
                flash('IP 不在黑名單中', 'warning')
        except Exception as e:
            flash(f'解除封鎖失敗: {str(e)}', 'error')
        
        return redirect(url_for('security_overview'))
    
    @app.route('/security/cleanup', methods=['POST'])
    @require_admin
    def cleanup_system():
        """系統清理"""
        try:
            expired_sessions = db_manager.cleanup_expired_sessions(24)
            flash(f'清理完成：移除了 {expired_sessions} 個過期會話', 'success')
        except Exception as e:
            flash(f'清理失敗: {str(e)}', 'error')
        
        return redirect(url_for('security_overview'))
    
    @app.route('/security/block', methods=['GET', 'POST'])
    @require_admin
    def block_ip():
        """手動封鎖 IP"""
        if request.method == 'GET':
            return render_template('admin_block_ip.html')
        
        ip_address = request.form.get('ip_address', '').strip()
        reason = request.form.get('reason', '').strip()
        
        if not ip_address:
            flash('請輸入 IP 地址', 'error')
            return render_template('admin_block_ip.html')
        
        if not reason:
            reason = '手動封鎖'
        
        try:
            # 直接調用資料庫方法
            admin_username = g.admin['username']
            db_manager.add_ip_to_blacklist(ip_address, reason, admin_username)
            flash(f'IP {ip_address} 已加入黑名單', 'success')
            return redirect(url_for('security_overview'))
        except Exception as e:
            flash(f'封鎖 IP 失敗: {str(e)}', 'error')
            return render_template('admin_block_ip.html')
    
    @app.route('/security/attempts')
    @require_admin
    def login_attempts():
        """登入嘗試記錄"""
        try:
            attempts = db_manager.get_login_attempts(100)  # 獲取最近100次嘗試
            return render_template('admin_login_attempts.html', attempts=attempts)
        except Exception as e:
            flash(f'獲取登入記錄失敗: {str(e)}', 'error')
            return render_template('admin_login_attempts.html', attempts=[])
    
    # 錯誤處理
    @app.errorhandler(404)
    def not_found(error):
        return "<h1>404 - 頁面不存在</h1><p><a href='/'>返回首頁</a></p>", 404
    
    @app.errorhandler(500)
    def server_error(error):
        return "<h1>500 - 伺服器錯誤</h1><p><a href='/'>返回首頁</a></p>", 500
    
    return app


def open_browser(url):
    """延遲打開瀏覽器"""
    webbrowser.open(url)


def main():
    """主函數"""
    print("🚀 正在啟動本地管理伺服器...")
    
    # 檢查是否有管理員用戶
    try:
        db_manager = DatabaseManager()
        users = db_manager.get_all_users()
        admins = [u for u in users if u['role'] == 'admin' and u['is_active']]
        
        if not admins:
            print("\n❌ 錯誤：目前沒有啟用的管理員帳號")
            print("請先使用以下命令創建管理員：")
            print("python admin_manager.py create-user 你的用戶名 --role admin")
            sys.exit(1)
        
        print(f"✅ 找到 {len(admins)} 個管理員帳號")
        
    except Exception as e:
        print(f"❌ 資料庫檢查失敗: {e}")
        sys.exit(1)
    
    # 創建應用並找到可用端口
    app = create_admin_app()
    port = find_free_port()
    
    print(f"\n🔒 本地管理介面啟動成功！")
    print(f"📍 網址: http://127.0.0.1:{port}")
    print(f"🔐 僅限本機訪問")
    print(f"⏰ 會話將在 2 小時後自動過期")
    print(f"\n按 Ctrl+C 停止伺服器")
    
    # 2秒後自動打開瀏覽器
    Timer(2.0, open_browser, [f"http://127.0.0.1:{port}"]).start()
    
    try:
        app.run(
            host='127.0.0.1',  # 僅綁定本地
            port=port,
            debug=False,
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n👋 管理伺服器已停止")


if __name__ == '__main__':
    main()