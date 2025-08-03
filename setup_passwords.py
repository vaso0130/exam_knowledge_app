"""
為現有用戶設定密碼的工具
"""
import os
import sys
import hashlib
from pathlib import Path

# 添加專案根目錄到路徑
sys.path.append(str(Path(__file__).parent))

from src.core.database import DatabaseManager

def set_user_password(username: str, password: str):
    """為用戶設定密碼"""
    db = DatabaseManager()
    
    try:
        with db._session_scope() as session:
            from src.core.database import User
            user = session.query(User).filter(User.username == username).first()
            
            if user:
                # 更新密碼
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                user.password_hash = password_hash
                session.commit()
                print(f"✅ 用戶 {username} 的密碼已更新")
            else:
                # 創建新用戶
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                role = 'admin' if username == 'vasou' else 'viewer'
                user = User(username=username, password_hash=password_hash, role=role)
                session.add(user)
                session.commit()
                print(f"✅ 新用戶 {username} 已創建，角色：{role}")
                
    except Exception as e:
        print(f"❌ 錯誤：{e}")

if __name__ == "__main__":
    print("🔧 用戶密碼設定工具")
    print("="*50)
    
    # 為管理者設定密碼
    print("為管理者 vasou 設定密碼...")
    set_user_password("vasou", "admin123")
    
    # 為測試用戶設定密碼
    print("為測試用戶 test 設定密碼...")
    set_user_password("test", "test123")
    
    print("="*50)
    print("✅ 密碼設定完成！")
    print()
    print("📋 登入資訊：")
    print("👑 管理者: vasou / admin123")
    print("👤 測試用戶: test / test123")
    print()
    print("💡 提示：新用戶註冊時需要設定密碼")
