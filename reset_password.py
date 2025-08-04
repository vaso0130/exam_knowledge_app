#!/usr/bin/env python3
"""
快速重設用戶密碼工具
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from src.core.database import DatabaseManager, User
from src.core.security_manager import SecurityManager

def reset_user_password(username, new_password):
    """重設用戶密碼"""
    try:
        db = DatabaseManager()
        security_manager = SecurityManager(db)
        
        with db._session_scope() as session:
            user = session.query(User).filter(User.username == username).first()
            if not user:
                print(f"❌ 用戶 {username} 不存在")
                return False
            
            # 生成新的密碼雜湊
            new_password_hash = security_manager.hash_password(new_password)
            
            # 更新密碼
            user.password_hash = new_password_hash
            session.commit()
            
            print(f"✅ 用戶 {username} 密碼重設成功")
            print(f"🔑 新密碼: {new_password}")
            
            # 驗證密碼
            if security_manager.verify_password(new_password, new_password_hash):
                print("✅ 密碼驗證通過")
                return True
            else:
                print("❌ 密碼驗證失敗")
                return False
                
    except Exception as e:
        print(f"❌ 重設密碼失敗: {e}")
        return False

def main():
    import getpass
    
    print("🔧 用戶密碼重設工具")
    print("=" * 30)
    
    # 列出所有用戶
    try:
        db = DatabaseManager()
        with db._session_scope() as session:
            users = session.query(User).all()
            print("📊 當前用戶列表:")
            for user in users:
                print(f"   - {user.username} (ID: {user.id}, 角色: {user.role})")
    except Exception as e:
        print(f"❌ 無法獲取用戶列表: {e}")
        return
    
    # 選擇用戶
    username = input("\n請輸入要重設密碼的用戶名: ").strip()
    if not username:
        print("❌ 用戶名不能為空")
        return
    
    # 輸入新密碼
    new_password = getpass.getpass("請輸入新密碼: ").strip()
    if not new_password:
        print("❌ 密碼不能為空")
        return
    
    confirm_password = getpass.getpass("請確認新密碼: ").strip()
    if new_password != confirm_password:
        print("❌ 兩次輸入的密碼不一致")
        return
    
    # 重設密碼
    if reset_user_password(username, new_password):
        print("\n🎉 密碼重設完成！現在可以使用新密碼登入系統")
    else:
        print("\n❌ 密碼重設失敗")

if __name__ == "__main__":
    main()
