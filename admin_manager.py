#!/usr/bin/env python3
"""
v3.0 管理員命令行工具
用於本地管理用戶帳號、查看安全日誌等
"""

import os
import sys
import argparse
import getpass
from datetime import datetime

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
        
        print("\n📋 用戶列表:")
        print("-" * 80)
        print(f"{'ID':<4} {'用戶名':<15} {'角色':<8} {'狀態':<6} {'最後登入':<20} {'Email':<25}")
        print("-" * 80)
        
        for user in users:
            status = "啟用" if user['is_active'] else "停用"
            last_login = user['last_login'][:19] if user['last_login'] else "從未"
            email = user['email'] or ""
            
            print(f"{user['id']:<4} {user['username']:<15} {user['role']:<8} {status:<6} {last_login:<20} {email:<25}")
        
        print("-" * 80)
        print(f"總計: {len(users)} 個用戶")
        
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
            print("📝 黑名單為空")
            return
        
        print("\n🚫 IP 黑名單:")
        print("-" * 80)
        print(f"{'ID':<4} {'IP 地址':<15} {'封鎖時間':<20} {'封鎖者':<12} {'原因':<25}")
        print("-" * 80)
        
        for entry in blacklist:
            blocked_at = entry['blocked_at'][:19]
            blocked_by = entry['blocked_by'] or "系統"
            reason = entry['reason'][:25] + "..." if len(entry['reason']) > 25 else entry['reason']
            
            print(f"{entry['id']:<4} {entry['ip_address']:<15} {blocked_at:<20} {blocked_by:<12} {reason:<25}")
        
        print("-" * 80)
        print(f"總計: {len(blacklist)} 個被封鎖的 IP")
        
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
        print("-" * 100)
        print(f"{'ID':<6} {'時間':<20} {'IP 地址':<15} {'用戶名':<15} {'結果':<6} {'User Agent':<30}")
        print("-" * 100)
        
        for attempt in attempts:
            attempt_time = attempt['attempt_time'][:19]
            username = attempt['username'] or "未知"
            result = "成功" if attempt['success'] else "失敗"
            user_agent = (attempt['user_agent'] or "")[:30]
            
            print(f"{attempt['id']:<6} {attempt_time:<20} {attempt['ip_address']:<15} {username:<15} {result:<6} {user_agent:<30}")
        
        print("-" * 100)
        
        # 統計
        successful = len([a for a in attempts if a['success']])
        failed = len(attempts) - successful
        print(f"統計: 成功 {successful} 次, 失敗 {failed} 次")
        
    except Exception as e:
        print(f"❌ 查詢登入記錄失敗: {e}")


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
    parser = argparse.ArgumentParser(description="知識庫系統 v3.0 管理工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 初始化資料庫
    init_parser = subparsers.add_parser('init', help='初始化資料庫')
    init_parser.set_defaults(func=init_db_command)
    
    # 創建用戶
    create_parser = subparsers.add_parser('create-user', help='創建新用戶')
    create_parser.add_argument('username', help='用戶名稱')
    create_parser.add_argument('--role', choices=['admin', 'viewer'], default='viewer', help='用戶角色')
    create_parser.add_argument('--email', help='電子郵件')
    create_parser.add_argument('--password', help='密碼（不指定則提示輸入）')
    create_parser.set_defaults(func=create_user_command)
    
    # 列出用戶
    list_parser = subparsers.add_parser('list-users', help='列出所有用戶')
    list_parser.set_defaults(func=list_users_command)
    
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
    
    # 顯示黑名單
    blacklist_parser = subparsers.add_parser('show-blacklist', help='顯示 IP 黑名單')
    blacklist_parser.set_defaults(func=show_blacklist_command)
    
    # 解除 IP 封鎖
    unblock_parser = subparsers.add_parser('unblock-ip', help='解除 IP 封鎖')
    unblock_parser.add_argument('ip', help='IP 地址')
    unblock_parser.set_defaults(func=unblock_ip_command)
    
    # 顯示登入記錄
    attempts_parser = subparsers.add_parser('show-attempts', help='顯示登入嘗試記錄')
    attempts_parser.add_argument('--limit', type=int, default=50, help='顯示數量限制')
    attempts_parser.set_defaults(func=show_login_attempts_command)
    
    # 解析參數
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 執行命令
    args.func(args)


if __name__ == '__main__':
    main()
