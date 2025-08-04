# CLI 管理工具使用說明

## 概述

`admin_manager.py` 是一個功能完整的命令行管理工具，提供與 Web 管理介面 (`admin_server.py`) 相同的所有功能。

## 安裝依賴

```bash
pip install tabulate
```

## 基本用法

```bash
python admin_manager.py <command> [arguments]
```

## 可用命令

### 資料庫管理

```bash
# 初始化資料庫
python admin_manager.py init
```

### 用戶管理

```bash
# 創建新用戶
python admin_manager.py create-user alice --role admin --email alice@example.com

# 列出所有用戶
python admin_manager.py list-users

# 顯示用戶詳細資訊
python admin_manager.py user-detail alice

# 編輯用戶資訊
python admin_manager.py edit-user alice --new-username alice_admin --role admin

# 重設用戶密碼
python admin_manager.py reset-password alice

# 啟用用戶
python admin_manager.py toggle-user alice enable

# 停用用戶
python admin_manager.py toggle-user alice disable

# 刪除用戶
python admin_manager.py delete-user alice
python admin_manager.py delete-user alice --force  # 強制刪除，無需確認
```

### 安全管理

```bash
# 顯示 IP 黑名單
python admin_manager.py show-blacklist

# 手動封鎖 IP
python admin_manager.py block-ip 192.168.1.100 --reason "惡意攻擊"

# 解除 IP 封鎖
python admin_manager.py unblock-ip 192.168.1.100

# 顯示登入嘗試記錄
python admin_manager.py show-attempts --limit 100
```

### 系統管理

```bash
# 顯示系統統計
python admin_manager.py show-stats

# 清理過期會話
python admin_manager.py cleanup --hours 24
```

## 互動式操作

某些命令會提示輸入敏感資訊（如密碼）：

```bash
# 創建用戶時會提示輸入密碼
python admin_manager.py create-user bob
請輸入密碼: ********
請確認密碼: ********

# 重設密碼時會提示輸入新密碼
python admin_manager.py reset-password bob
請輸入新密碼: ********
請確認新密碼: ********
```

## 安全確認

危險操作（如刪除用戶）會要求確認：

```bash
python admin_manager.py delete-user alice
⚠️  即將刪除用戶: alice (ID: 2)
   角色: admin
   電子郵件: alice@example.com
   創建時間: 2025-01-01 12:00:00
   最後登入: 2025-01-02 10:30:00

❗ 此操作無法復原！確定要刪除嗎？(輸入 'DELETE' 確認): DELETE
✅ 用戶 'alice' 已刪除
```

## 輸出格式

工具使用美觀的表格格式顯示資料：

```
📋 用戶列表 (共 3 個用戶):
┌────┬──────────┬────────────┬────────┬─────────────────────┬───────────────────┐
│ ID │ 用戶名   │ 角色       │ 狀態   │ 最後登入            │ Email             │
├────┼──────────┼────────────┼────────┼─────────────────────┼───────────────────┤
│ 1  │ admin    │ 👑 admin   │ ✅ 啟用 │ 2025-01-02 10:30:00 │ admin@example.com │
│ 2  │ viewer1  │ 👤 viewer  │ ✅ 啟用 │ 2025-01-02 09:15:00 │                   │
│ 3  │ test     │ 👤 viewer  │ ❌ 停用 │ 從未                │ test@example.com  │
└────┴──────────┴────────────┴────────┴─────────────────────┴───────────────────┘

📊 統計: 啟用 2 個, 管理員 1 個
```

## 錯誤處理

工具提供清晰的錯誤訊息：

```bash
python admin_manager.py delete-user nonexistent
🔧 執行命令: delete-user
--------------------------------------------------
❌ 用戶 'nonexistent' 不存在
```

## 幫助資訊

```bash
# 顯示所有可用命令
python admin_manager.py --help

# 顯示特定命令的詳細說明
python admin_manager.py create-user --help
```

## 優勢

相比 Web 介面，CLI 工具提供：

1. **批次操作**: 可以寫腳本批量處理
2. **自動化**: 易於集成到自動化流程中
3. **遠端管理**: 通過 SSH 等方式遠端執行
4. **日誌記錄**: 輸出可以重定向到檔案
5. **腳本化**: 可以寫 shell 腳本自動執行管理任務

## 範例腳本

```bash
#!/bin/bash
# 批量創建用戶

users=("alice" "bob" "charlie")
for user in "${users[@]}"; do
    echo "創建用戶: $user"
    python admin_manager.py create-user "$user" --role viewer --password "temp123"
done

echo "用戶創建完成！"
python admin_manager.py list-users
```
