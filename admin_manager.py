#!/usr/bin/env python3
"""
v3.0 管理員命令行工具
用於本地管理用戶帳號、查看安全日誌等
提供與 admin_server.py 相同的完整管理功能
"""

import os
import sys
import argparse
import getpass
from datetime import datetime
from tabulate import tabulate
import re

# 添加專案根目錄到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import DatabaseManager
from src.core.security_manager import SecurityManager


def init_managers():
    """初始化管理器"""
    try:
        db_manager = DatabaseManager()
        security_manager = SecurityManager(db_manager)
        return db_manager, security_manager
    except Exception as e:
        print(f"❌ 初始化失敗: {e}")
        sys.exit(1)


def create_user_command(args):
    """創建用戶命令"""
    db_manager, security_manager = init_managers()
    
    username = args.username
    role = args.role
    email = args.email
    
    # 獲取密碼
    if args.password:
        password = args.password
    else:
        password = getpass.getpass("請輸入密碼: ")
        confirm_password = getpass.getpass("請確認密碼: ")
        
        if password != confirm_password:
            print("❌ 密碼確認不符")
            return
    
    # 創建用戶（管理員工具，跳過會話檢查）
    try:
        password_hash = security_manager.hash_password(password)
        user_id = db_manager.create_user(username, password_hash, role, email)
        print(f"✅ 用戶 '{username}' 創建成功 (ID: {user_id})")
    except Exception as e:
        print(f"❌ 創建用戶失敗: {e}")


def list_users_command(args):
    """列出所有用戶"""
    db_manager, _ = init_managers()
    
    try:
        users = db_manager.get_all_users()
        
        if not users:
            print("📝 目前沒有用戶")
            return
        
        print(f"\n📋 用戶列表 (共 {len(users)} 個用戶):")
        
        # 準備表格資料
        table_data = []
        for user in users:
            status = "✅ 啟用" if user['is_active'] else "❌ 停用"
            last_login = user['last_login'][:19] if user['last_login'] else "從未"
            email = user['email'] or ""
            
            # 角色圖示
            role_icon = "👑" if user['role'] == 'admin' else "👤"
            role_display = f"{role_icon} {user['role']}"
            
            table_data.append([
                user['id'],
                user['username'],
                role_display,
                status,
                last_login,
                email
            ])
        
        headers = ['ID', '用戶名', '角色', '狀態', '最後登入', 'Email']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        
        # 統計
        active_count = len([u for u in users if u['is_active']])
        admin_count = len([u for u in users if u['role'] == 'admin'])
        print(f"\n📊 統計: 啟用 {active_count} 個, 管理員 {admin_count} 個")
        
    except Exception as e:
        print(f"❌ 查詢用戶失敗: {e}")


def reset_password_command(args):
    """重設用戶密碼"""
    db_manager, security_manager = init_managers()
    
    username = args.username
    
    # 檢查用戶是否存在
    user = db_manager.get_user_by_username(username)
    if not user:
        print(f"❌ 用戶 '{username}' 不存在")
        return
    
    # 獲取新密碼
    if args.password:
        new_password = args.password
    else:
        new_password = getpass.getpass("請輸入新密碼: ")
        confirm_password = getpass.getpass("請確認新密碼: ")
        
        if new_password != confirm_password:
            print("❌ 密碼確認不符")
            return
    
    try:
        # 更新密碼
        new_password_hash = security_manager.hash_password(new_password)
        db_manager.update_user_password(user['id'], new_password_hash)
        
        # 使該用戶所有會話失效
        db_manager.invalidate_user_sessions(user['id'])
        
        print(f"✅ 用戶 '{username}' 密碼已重設，所有會話已失效")
        
    except Exception as e:
        print(f"❌ 重設密碼失敗: {e}")


def toggle_user_command(args):
    """啟用/停用用戶"""
    db_manager, _ = init_managers()
    
    username = args.username
    action = args.action
    
    # 檢查用戶是否存在
    user = db_manager.get_user_by_username(username)
    if not user:
        print(f"❌ 用戶 '{username}' 不存在")
        return
    
    try:
        if action == 'enable':
            db_manager.enable_user(user['id'])
            print(f"✅ 用戶 '{username}' 已啟用")
        else:  # disable
            db_manager.disable_user(user['id'])
            # 使該用戶所有會話失效
            db_manager.invalidate_user_sessions(user['id'])
            print(f"✅ 用戶 '{username}' 已停用，所有會話已失效")
            
    except Exception as e:
        print(f"❌ 操作失敗: {e}")


def show_blacklist_command(args):
    """顯示 IP 黑名單"""
    db_manager, _ = init_managers()
    
    try:
        blacklist = db_manager.get_blacklisted_ips()
        
        if not blacklist:
            print("📝 IP 黑名單為空")
            return
        
        print(f"\n🚫 IP 黑名單 (共 {len(blacklist)} 個):")
        
        # 準備表格資料
        table_data = []
        for entry in blacklist:
            blocked_at = entry['blocked_at'][:19]
            blocked_by = entry['blocked_by'] or "系統"
            reason = entry['reason'][:40] + "..." if len(entry['reason']) > 40 else entry['reason']
            
            table_data.append([
                entry['id'],
                entry['ip_address'],
                blocked_at,
                blocked_by,
                reason
            ])
        
        headers = ['ID', 'IP 地址', '封鎖時間', '封鎖者', '原因']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        
    except Exception as e:
        print(f"❌ 查詢黑名單失敗: {e}")


def unblock_ip_command(args):
    """解除 IP 封鎖"""
    db_manager, _ = init_managers()
    
    ip_address = args.ip
    
    try:
        # 檢查 IP 是否在黑名單中
        if not db_manager.is_ip_blacklisted(ip_address):
            print(f"❌ IP '{ip_address}' 不在黑名單中")
            return
        
        # 解除封鎖
        success = db_manager.remove_ip_from_blacklist(ip_address)
        if success:
            print(f"✅ IP '{ip_address}' 已解除封鎖")
        else:
            print(f"❌ 解除封鎖失敗")
            
    except Exception as e:
        print(f"❌ 操作失敗: {e}")


def show_login_attempts_command(args):
    """顯示登入記錄"""
    db_manager, _ = init_managers()
    
    limit = args.limit
    
    try:
        attempts = db_manager.get_login_attempts(limit)
        
        if not attempts:
            print("📝 沒有登入記錄")
            return
        
        print(f"\n📊 最近 {len(attempts)} 次登入嘗試:")
        
        # 準備表格資料
        table_data = []
        for attempt in attempts:
            attempt_time = attempt['attempt_time'][:19]
            username = attempt['username'] or "未知"
            result = "✅ 成功" if attempt['success'] else "❌ 失敗"
            user_agent = (attempt['user_agent'] or "")[:40]
            
            table_data.append([
                attempt['id'],
                attempt_time,
                attempt['ip_address'],
                username,
                result,
                user_agent
            ])
        
        headers = ['ID', '時間', 'IP 地址', '用戶名', '結果', 'User Agent']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        
        # 統計
        successful = len([a for a in attempts if a['success']])
        failed = len(attempts) - successful
        print(f"\n📊 統計: 成功 {successful} 次, 失敗 {failed} 次")
        
    except Exception as e:
        print(f"❌ 查詢登入記錄失敗: {e}")


def show_invite_attempts_command(args):
    """顯示邀請碼嘗試記錄"""
    db_manager, _ = init_managers()
    
    limit = args.limit
    
    try:
        attempts = db_manager.get_invite_code_attempts(limit)
        
        if not attempts:
            print("📝 沒有邀請碼嘗試記錄")
            return
        
        print(f"\n🔑 最近 {len(attempts)} 次邀請碼嘗試:")
        
        # 準備表格資料
        table_data = []
        for attempt in attempts:
            attempt_time = attempt['attempt_time'][:19]
            username = attempt['username_attempted'] or "未提供"
            invite_code = (attempt['invite_code'] or "")[:15] + "..."
            result = "✅ 成功" if attempt['success'] else "❌ 失敗"
            user_agent = (attempt['user_agent'] or "")[:30] + "..."
            
            table_data.append([
                attempt['id'],
                attempt_time,
                attempt['ip_address'],
                username,
                invite_code,
                result,
                user_agent
            ])
        
        headers = ['ID', '時間', 'IP 地址', '嘗試用戶名', '邀請碼', '結果', 'User Agent']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        
        # 統計
        successful = len([a for a in attempts if a['success']])
        failed = len(attempts) - successful
        print(f"\n📊 統計: 成功 {successful} 次, 失敗 {failed} 次")
        
        # 顯示最近失敗的 IP
        failed_ips = {}
        for attempt in attempts:
            if not attempt['success']:
                ip = attempt['ip_address']
                failed_ips[ip] = failed_ips.get(ip, 0) + 1
        
        if failed_ips:
            print(f"\n⚠️  失敗次數最多的 IP:")
            for ip, count in sorted(failed_ips.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"   {ip}: {count} 次失敗")
        
    except Exception as e:
        print(f"❌ 查詢邀請碼嘗試記錄失敗: {e}")


def delete_user_command(args):
    """刪除用戶"""
    db_manager, _ = init_managers()
    
    username = args.username
    force = args.force
    
    # 檢查用戶是否存在
    user = db_manager.get_user_by_username(username)
    if not user:
        print(f"❌ 用戶 '{username}' 不存在")
        return
    
    # 確認刪除
    if not force:
        print(f"⚠️  即將刪除用戶: {username} (ID: {user['id']})")
        print(f"   角色: {user['role']}")
        print(f"   電子郵件: {user['email'] or '未設定'}")
        print(f"   創建時間: {user['created_at']}")
        print(f"   最後登入: {user['last_login'] or '從未'}")
        
        confirm = input("\n❗ 此操作無法復原！確定要刪除嗎？(輸入 'DELETE' 確認): ").strip()
        if confirm != 'DELETE':
            print("❌ 操作已取消")
            return
    
    try:
        # 先使所有會話失效
        db_manager.invalidate_user_sessions(user['id'])
        
        # 刪除用戶
        success = db_manager.delete_user(user['id'])
        if success:
            print(f"✅ 用戶 '{username}' 已刪除")
        else:
            print(f"❌ 刪除用戶失敗")
        
    except Exception as e:
        print(f"❌ 刪除失敗: {e}")


def edit_user_command(args):
    """編輯用戶資訊"""
    db_manager, _ = init_managers()
    
    username = args.username
    new_username = args.new_username
    role = args.role
    email = args.email
    
    # 檢查用戶是否存在
    user = db_manager.get_user_by_username(username)
    if not user:
        print(f"❌ 用戶 '{username}' 不存在")
        return
    
    # 顯示當前資訊
    print(f"📝 編輯用戶: {username}")
    print(f"   當前角色: {user['role']}")
    print(f"   當前電子郵件: {user['email'] or '未設定'}")
    
    # 設置新值
    final_username = new_username if new_username else user['username']
    final_role = role if role else user['role']
    final_email = email if email is not None else user['email']
    
    # 檢查用戶名是否被其他用戶使用
    if final_username != user['username']:
        existing_user = db_manager.get_user_by_username(final_username)
        if existing_user:
            print(f"❌ 用戶名 '{final_username}' 已被使用")
            return
    
    try:
        # 更新用戶資訊
        success = db_manager.update_user_info(user['id'], final_username, final_role, final_email)
        if success:
            print(f"✅ 用戶資訊已更新:")
            print(f"   用戶名: {final_username}")
            print(f"   角色: {final_role}")
            print(f"   電子郵件: {final_email or '未設定'}")
        else:
            print("❌ 更新用戶資訊失敗")
        
    except Exception as e:
        print(f"❌ 更新失敗: {e}")


def block_ip_command(args):
    """手動封鎖 IP"""
    db_manager, _ = init_managers()
    
    ip_address = args.ip
    reason = args.reason or "手動封鎖"
    blocked_by = args.blocked_by or "CLI-Admin"
    
    # 驗證 IP 格式
    if not is_valid_ip(ip_address):
        print(f"❌ IP 地址格式不正確: {ip_address}")
        return
    
    # 檢查是否已經在黑名單中
    if db_manager.is_ip_blacklisted(ip_address):
        print(f"⚠️  IP '{ip_address}' 已在黑名單中")
        return
    
    try:
        db_manager.add_ip_to_blacklist(ip_address, reason, blocked_by)
        print(f"✅ IP '{ip_address}' 已加入黑名單")
        print(f"   原因: {reason}")
        print(f"   封鎖者: {blocked_by}")
        
    except Exception as e:
        print(f"❌ 封鎖 IP 失敗: {e}")


def cleanup_system_command(args):
    """系統清理"""
    db_manager, _ = init_managers()
    
    hours = args.hours
    
    try:
        expired_sessions = db_manager.cleanup_expired_sessions(hours)
        print(f"✅ 系統清理完成:")
        print(f"   清理了 {expired_sessions} 個過期會話 (超過 {hours} 小時)")
        
    except Exception as e:
        print(f"❌ 系統清理失敗: {e}")


def show_stats_command(args):
    """顯示系統統計"""
    db_manager, _ = init_managers()
    
    try:
        # 獲取統計資料
        all_users = db_manager.get_all_users()
        blacklisted_ips = db_manager.get_blacklisted_ips()
        recent_attempts = db_manager.get_login_attempts(100)
        invite_attempts = db_manager.get_invite_code_attempts(100)
        
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
            'failed_invites_today': len([
                a for a in invite_attempts 
                if not a['success'] and 
                datetime.fromisoformat(a['attempt_time']).date() == datetime.now().date()
            ])
        }
        
        print("📊 系統統計資訊:")
        print("=" * 50)
        print(f"👥 用戶統計:")
        print(f"   總用戶數: {stats['total_users']}")
        print(f"   活躍用戶: {stats['active_users']}")
        print(f"   管理員數: {stats['admin_users']}")
        
        print(f"\n🛡️  安全統計:")
        print(f"   封鎖 IP 數: {stats['blacklisted_ips']}")
        print(f"   今日失敗登入: {stats['failed_attempts_today']}")
        print(f"   今日邀請碼失敗: {stats['failed_invites_today']}")
        
        print(f"\n📅 最近活動:")
        if recent_attempts:
            latest_attempt = recent_attempts[0]
            print(f"   最新登入嘗試: {latest_attempt['attempt_time'][:19]}")
            print(f"   來源 IP: {latest_attempt['ip_address']}")
            print(f"   結果: {'成功' if latest_attempt['success'] else '失敗'}")
        else:
            print("   無登入記錄")
        
    except Exception as e:
        print(f"❌ 獲取統計資料失敗: {e}")


def show_user_detail_command(args):
    """顯示用戶詳細資訊"""
    db_manager, _ = init_managers()
    
    username = args.username
    
    # 檢查用戶是否存在
    user = db_manager.get_user_by_username(username)
    if not user:
        print(f"❌ 用戶 '{username}' 不存在")
        return
    
    try:
        print(f"👤 用戶詳細資訊: {username}")
        print("=" * 50)
        print(f"ID: {user['id']}")
        print(f"用戶名: {user['username']}")
        print(f"角色: {user['role']}")
        print(f"電子郵件: {user['email'] or '未設定'}")
        print(f"完整姓名: {user.get('full_name') or '未設定'}")
        print(f"狀態: {'啟用' if user['is_active'] else '停用'}")
        print(f"創建時間: {user['created_at']}")
        print(f"最後登入: {user['last_login'] or '從未'}")
        
        # 點數資訊 (v3.1)
        if 'points' in user:
            print(f"當前點數: {user['points']}")
            print(f"點數更新時間: {user.get('points_updated_at', '未知')}")
            print(f"是否被禁用: {'是' if user.get('is_banned') else '否'}")
            if user.get('ban_until'):
                print(f"禁用到期: {user['ban_until']}")
        
        # 查看該用戶的登入記錄
        attempts = db_manager.get_login_attempts(20)
        user_attempts = [a for a in attempts if a.get('username') == username]
        
        if user_attempts:
            print(f"\n📊 最近登入記錄 (最多 10 次):")
            table_data = []
            for attempt in user_attempts[:10]:
                table_data.append([
                    attempt['attempt_time'][:19],
                    attempt['ip_address'],
                    "✅ 成功" if attempt['success'] else "❌ 失敗",
                    (attempt['user_agent'] or "")[:40]
                ])
            
            headers = ['時間', 'IP 地址', '結果', 'User Agent']
            print(tabulate(table_data, headers=headers, tablefmt='grid'))
        
    except Exception as e:
        print(f"❌ 獲取用戶詳細資訊失敗: {e}")


def is_valid_ip(ip):
    """驗證 IP 地址格式"""
    pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    return re.match(pattern, ip) is not None


def init_db_command(args):
    """初始化資料庫"""
    try:
        db_manager = DatabaseManager()
        print("✅ 資料庫初始化成功")
        
        # 檢查是否有管理員用戶
        users = db_manager.get_all_users()
        admins = [u for u in users if u['role'] == 'admin']
        
        if not admins:
            print("\n⚠️  目前沒有管理員用戶")
            create_admin = input("是否要創建管理員用戶? (y/N): ").strip().lower()
            
            if create_admin == 'y':
                username = input("管理員用戶名: ").strip()
                if username:
                    password = getpass.getpass("管理員密碼: ")
                    confirm_password = getpass.getpass("確認密碼: ")
                    
                    if password and password == confirm_password:
                        security_manager = SecurityManager(db_manager)
                        password_hash = security_manager.hash_password(password)
                        user_id = db_manager.create_user(username, password_hash, 'admin')
                        print(f"✅ 管理員 '{username}' 創建成功 (ID: {user_id})")
                    else:
                        print("❌ 密碼確認不符或為空")
        else:
            print(f"✅ 目前有 {len(admins)} 個管理員用戶")
            
    except Exception as e:
        print(f"❌ 資料庫初始化失敗: {e}")


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description="知識庫系統 v3.0 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例用法:
  python admin_manager.py init                           # 初始化資料庫
  python admin_manager.py create-user alice --role admin # 創建管理員
  python admin_manager.py list-users                     # 列出所有用戶
  python admin_manager.py show-stats                     # 顯示系統統計
  python admin_manager.py reset-password alice          # 重設密碼
  python admin_manager.py block-ip 192.168.1.100        # 封鎖 IP
  python admin_manager.py show-blacklist                # 顯示黑名單
  python admin_manager.py cleanup --hours 24            # 清理過期會話
        """
    )
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # === 資料庫管理 ===
    init_parser = subparsers.add_parser('init', help='初始化資料庫')
    init_parser.set_defaults(func=init_db_command)
    
    # === 用戶管理 ===
    # 創建用戶
    create_parser = subparsers.add_parser('create-user', help='創建新用戶')
    create_parser.add_argument('username', help='用戶名稱')
    create_parser.add_argument('--role', choices=['admin', 'viewer'], default='viewer', help='用戶角色 (預設: viewer)')
    create_parser.add_argument('--email', help='電子郵件')
    create_parser.add_argument('--password', help='密碼（不指定則提示輸入）')
    create_parser.set_defaults(func=create_user_command)
    
    # 列出用戶
    list_parser = subparsers.add_parser('list-users', help='列出所有用戶')
    list_parser.set_defaults(func=list_users_command)
    
    # 用戶詳細資訊
    detail_parser = subparsers.add_parser('user-detail', help='顯示用戶詳細資訊')
    detail_parser.add_argument('username', help='用戶名稱')
    detail_parser.set_defaults(func=show_user_detail_command)
    
    # 編輯用戶
    edit_parser = subparsers.add_parser('edit-user', help='編輯用戶資訊')
    edit_parser.add_argument('username', help='當前用戶名稱')
    edit_parser.add_argument('--new-username', help='新用戶名稱')
    edit_parser.add_argument('--role', choices=['admin', 'viewer'], help='新角色')
    edit_parser.add_argument('--email', help='新電子郵件 (使用空字串清空)')
    edit_parser.set_defaults(func=edit_user_command)
    
    # 重設密碼
    reset_parser = subparsers.add_parser('reset-password', help='重設用戶密碼')
    reset_parser.add_argument('username', help='用戶名稱')
    reset_parser.add_argument('--password', help='新密碼（不指定則提示輸入）')
    reset_parser.set_defaults(func=reset_password_command)
    
    # 啟用/停用用戶
    toggle_parser = subparsers.add_parser('toggle-user', help='啟用或停用用戶')
    toggle_parser.add_argument('username', help='用戶名稱')
    toggle_parser.add_argument('action', choices=['enable', 'disable'], help='操作類型')
    toggle_parser.set_defaults(func=toggle_user_command)
    
    # 刪除用戶
    delete_parser = subparsers.add_parser('delete-user', help='刪除用戶')
    delete_parser.add_argument('username', help='用戶名稱')
    delete_parser.add_argument('--force', action='store_true', help='強制刪除，不要確認')
    delete_parser.set_defaults(func=delete_user_command)
    
    # === 安全管理 ===
    # 顯示黑名單
    blacklist_parser = subparsers.add_parser('show-blacklist', help='顯示 IP 黑名單')
    blacklist_parser.set_defaults(func=show_blacklist_command)
    
    # 封鎖 IP
    block_parser = subparsers.add_parser('block-ip', help='手動封鎖 IP')
    block_parser.add_argument('ip', help='IP 地址')
    block_parser.add_argument('--reason', help='封鎖原因')
    block_parser.add_argument('--blocked-by', help='封鎖者名稱')
    block_parser.set_defaults(func=block_ip_command)
    
    # 解除 IP 封鎖
    unblock_parser = subparsers.add_parser('unblock-ip', help='解除 IP 封鎖')
    unblock_parser.add_argument('ip', help='IP 地址')
    unblock_parser.set_defaults(func=unblock_ip_command)
    
    # 顯示登入記錄
    attempts_parser = subparsers.add_parser('show-attempts', help='顯示登入嘗試記錄')
    attempts_parser.add_argument('--limit', type=int, default=50, help='顯示數量限制 (預設: 50)')
    attempts_parser.set_defaults(func=show_login_attempts_command)
    
    # 顯示邀請碼嘗試記錄
    invite_attempts_parser = subparsers.add_parser('show-invite-attempts', help='顯示邀請碼嘗試記錄')
    invite_attempts_parser.add_argument('--limit', type=int, default=50, help='顯示數量限制 (預設: 50)')
    invite_attempts_parser.set_defaults(func=show_invite_attempts_command)
    
    # === 系統管理 ===
    # 系統統計
    stats_parser = subparsers.add_parser('show-stats', help='顯示系統統計資訊')
    stats_parser.set_defaults(func=show_stats_command)
    
    # 系統清理
    cleanup_parser = subparsers.add_parser('cleanup', help='清理過期會話')
    cleanup_parser.add_argument('--hours', type=int, default=24, help='清理超過指定小時的會話 (預設: 24)')
    cleanup_parser.set_defaults(func=cleanup_system_command)
    
    # 解析參數
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        print("\n💡 提示: 使用 'python admin_manager.py <command> --help' 查看特定命令的詳細說明")
        return
    
    # 顯示正在執行的命令
    print(f"🔧 執行命令: {args.command}")
    print("-" * 50)
    
    # 執行命令
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n❌ 操作被用戶中斷")
    except Exception as e:
        print(f"\n❌ 未預期的錯誤: {e}")
        if '--debug' in sys.argv:
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    main()
