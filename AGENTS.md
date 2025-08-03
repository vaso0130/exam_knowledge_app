
# 🚀 AI 智慧考題知識整理系統 v3.0 開發計畫

## 🎯 v3.0 主要目標：完整的安全與權限管理系統

### 🔐 優先任務：帳號系統與資安防護

**背景**：系統已部署上線，需要完整的權限控制與安全防護機制。#### 3.2 主系統管理：❌#### 4.1 主系統路由架構（完全移除管理功能）

```
# 使用者認證
/login              # 登入頁面
/logout             # 登出功能
/profile            # 個人資料頁面

# 主要功能（需要登入，所有用戶相同）
/dashboard          # 統一儀表板（admin 和 viewer 看到相同內容）
/                   # 原有主頁功能保持不變

# ❌ 完全移除所有管理路由
# 不再有任何 /admin/* 路由
# 所有管理操作都只能在本地端執行
```

**本地管理伺服器路由**（僅在 admin_server.py 中）:
```
# 本地管理介面（隨機端口，僅 127.0.0.1）
http://127.0.0.1:{random_port}/
├── /login              # 管理員登入
├── /dashboard          # 管理統計
├── /users              # 用戶管理
├── /users/create       # 創建用戶
├── /users/{id}/reset   # 重設密碼
├── /security           # 安全監控
└── /security/cleanup   # 系統清理
```*
- ✅ **登入系統**：完整的用戶認證與會話管理
- ✅ **基本儀表板**：所有用戶看到相同的功能導航
- ❌ **無管理操作**：不能創建/刪除用戶、不能管理 IP 黑名單
- ❌ **無管理頁面**：所有 `/admin/*` 路由都已移除
- 💡 **僅提示**：管理員會看到「請使用本地管理工具」的提示### 核心安全需求
1. **雙層權限系統**：管理者 vs 檢視者
2. **本地端帳號管理**：完全脫離 Web 介面的安全管理
3. **IP 黑名單機制**：3 次密碼錯誤自動封鎖
4. **為個人筆記功能做準備**：未來版本的基礎架構

---

## 📋 v3.0 開發任務清單

### 🔒 Phase 1: 帳號系統架構設計

#### 1.1 資料庫設計
```sql
-- 用戶管理表
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'viewer') DEFAULT 'viewer',
    email VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    is_active BOOLEAN DEFAULT TRUE
);

-- 登入記錄表
CREATE TABLE login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_address VARCHAR(45) NOT NULL,
    username VARCHAR(50),
    success BOOLEAN DEFAULT FALSE,
    attempt_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_agent TEXT
);

-- IP 黑名單表
CREATE TABLE ip_blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_address VARCHAR(45) UNIQUE NOT NULL,
    reason VARCHAR(255) DEFAULT 'Too many failed login attempts',
    blocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    blocked_by VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE
);

-- 會話管理表
CREATE TABLE user_sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

#### 1.2 權限定義
- **🔴 管理者 (admin)**：
  - ✅ 完整 CRUD 權限（增刪改查所有內容）
  - ✅ 刪除文件與問題
  - ✅ 編輯問題內容
  - ✅ 重新生成答案、心智圖、解題技巧
  - ✅ 查看系統統計與日誌
  - ✅ 上傳檔案分析
  
- **🟡 檢視者 (viewer)**：
  - ✅ 檢視所有內容（文件、問題、知識點）
  - ✅ 上傳檔案給 AI 分析
  - ❌ 無法刪除或編輯現有內容
  - ❌ 無法重新生成內容

### 🛡️ Phase 2: 安全防護機制

#### 2.1 登入保護
- **密碼策略**：bcrypt + salt
- **失敗次數限制**：3 次錯誤 → IP 自動加入黑名單
- **會話管理**：JWT 或 Flask-Session
- **CSRF 保護**：所有表單都需要 CSRF token

#### 2.2 IP 黑名單系統
```python
# 核心功能
class SecurityManager:
    def check_ip_blacklist(self, ip_address: str) -> bool
    def add_to_blacklist(self, ip_address: str, reason: str) -> None
    def remove_from_blacklist(self, ip_address: str) -> None
    def record_login_attempt(self, ip: str, username: str, success: bool) -> None
    def get_failed_attempts(self, ip: str, time_window: int = 3600) -> int
```

#### 2.3 中介軟體保護
- **IP 黑名單檢查**：每個請求都先檢查 IP
- **登入狀態驗證**：保護所有路由
- **權限驗證**：admin/viewer 權限分離
- **速率限制**：防止暴力破解

### 🖥️ Phase 3: 雙軌管理系統

#### 3.1 本地專用管理：`admin_server.py`（完整管理權限）
```bash
# 啟動本地管理伺服器
python admin_server.py
# 自動在隨機端口啟動，僅限 127.0.0.1 訪問
```

**本地管理功能**：
- 🔒 **完全隔離**：僅本機 + 隨機端口 + 管理員驗證
- 👥 **用戶管理**：創建、編輯、啟用/停用、密碼重設
- � **IP 黑名單**：查看、解封、手動封鎖
- � **安全監控**：登入記錄、威脅分析、系統清理
- �️ **系統維護**：資料庫清理、備份還原

#### 3.2 主系統管理：整合到 `web_app.py`（僅顯示功能）
- � **登入系統**：完整的用戶認證與會話管理
- 📊 **管理員儀表板**：統計圖表、系統狀態顯示
- � **無操作權限**：不能創建/刪除用戶、不能管理 IP 黑名單
- � **僅供檢視**：可查看統計資料，但所有管理操作都引導到本地管理

#### 3.3 CLI 工具：`admin_manager.py`（緊急備援）
- � **緊急情況**：系統故障、忘記密碼、IP 被鎖
- 💻 **離線管理**：完全不依賴 Web 介面
- ⚡ **快速操作**：命令行快速執行關鍵任務

### 🌐 Phase 4: Web 介面改造

#### 4.1 路由架構重新設計

**主系統路由**（集成到 web_app.py）:
```
# 使用者認證
/login              # 登入頁面
/logout             # 登出功能
/profile            # 個人資料頁面

# 主要功能（需要登入）
/dashboard          # 管理員統計儀表板（僅顯示，無操作）
/                   # 原有主頁功能保持不變

# 🚫 移除所有管理操作路由
# 不再有 /admin/users, /admin/security 等操作介面
```

**本地管理系統**（admin_server.py，隨機端口）:
```
# 僅限 127.0.0.1 訪問
http://127.0.0.1:[隨機端口]/

# 完整管理功能
/                   # 本地管理儀表板
/login              # 本地管理員認證
/users              # 用戶完整管理
/users/create       # 創建用戶
/users/{id}/edit    # 編輯用戶
/users/{id}/reset   # 重設密碼
/security           # 安全監控
/security/blacklist # IP 黑名單管理
/cleanup            # 系統清理
```

**CLI 工具**（離線管理）:
```bash
python admin_manager.py [command]  # 緊急指令
```

#### 4.2 完全分離架構說明

**主系統 (web_app.py)**：
- ✅ 用戶認證功能（登入/登出）
- ✅ 統一儀表板（admin 和 viewer 看相同內容）
- ✅ 原有文檔功能保持不變
- ❌ **完全移除所有管理操作**

**本地管理系統 (admin_server.py)**：
- 🔒 僅限 127.0.0.1 + 隨機端口
- 🔑 獨立管理員認證
- 👥 完整用戶管理功能
- 🛡️ IP 黑名單管理
- 📊 安全監控統計

**CLI 工具 (admin_manager.py)**：
- ⚡ 緊急離線操作
- 🔧 系統維護功能

#### 4.3 現有功能權限改造
```python
# 裝飾器範例
@require_login
@require_admin
def delete_document(doc_id):
    # 只有 admin 可以刪除

@require_login  
def upload_file():
    # admin 和 viewer 都可以上傳

@require_login
@require_admin
def regenerate_answer(question_id):
    # 只有 admin 可以重新生成
```

---

## 🚀 實作順序

### Week 1: 資料庫與核心安全
1. ✅ 設計並建立用戶相關資料表
2. ✅ 實作 `SecurityManager` 類別
3. ✅ 實作密碼加密與驗證
4. ✅ 實作 IP 黑名單機制

### Week 2: 管理系統建置
1. ✅ 建立 `admin_manager.py` CLI 工具（緊急管理用）
2. ✅ 實作用戶 CRUD 功能
3. ✅ 實作 IP 管理功能
4. ✅ 建立獨立本地管理伺服器 (`admin_server.py`)

### Week 3: Web 介面整合
1. ✅ 建立登入/登出頁面與認證系統
2. ✅ 實作權限裝飾器與中介軟體
3. ✅ 開發本地管理介面（僅限 127.0.0.1 + 隨機端口）
4. ⭕ 改造主系統加入基礎權限控制（無帳號管理功能）

### Week 4: 主系統認證整合與點數系統（完成 ✅）

1. ✅ 整合認證系統到主 Web 應用
   - 將 auth_blueprints 整合進 web_app.py
   - 設置 session 管理和登入保護
   - **確保完全移除所有管理操作**

2. ✅ 實作點數系統（v3.1）
   - **點數機制**：每小時恢復100點，上限100點
   - **消耗標準**：生成考題10-50分、重新生成答案10分、心智圖5分、解題技巧5分
   - **違規懲罰**：非學習內容扣4800分（禁用48小時）
   - **上傳者追蹤**：所有文件顯示提供者資訊

3. ✅ 建立內容驗證系統
   - AI自動檢查上傳內容是否為學習相關
   - 違規內容自動拒絕並處罰
   - 完整的驗證記錄追蹤

4. ✅ 資料庫結構更新
   - 新增 point_transactions 表（點數交易記錄）
   - 新增 content_validations 表（內容驗證記錄）
   - users 表新增點數相關欄位
   - documents 表新增上傳者追蹤
1. ⭕ 整合認證系統到主 Web 應用
2. ⭕ 為現有功能添加權限控制裝飾器
3. ⭕ 創建主系統管理員儀表板（僅顯示統計，無操作功能）
4. ⭕ 測試與優化整體系統

---

## 📚 技術需求

### 新增依賴套件
```requirements
# 安全相關
Flask-Login>=0.6.0          # 會話管理
Flask-WTF>=1.1.0            # CSRF 保護  
bcrypt>=4.0.0               # 密碼加密
PyJWT>=2.8.0                # JWT token
argon2-cffi>=23.0.0         # 更強的密碼加密（可選）

# 指令介面
click>=8.1.0                # CLI 工具
tabulate>=0.9.0             # 表格輸出
colorama>=0.4.0             # 終端顏色
```

### 設定檔更新
```env
# 新增安全設定
LOGIN_RATE_LIMIT=5           # 每分鐘最大登入嘗試次數
SESSION_TIMEOUT=3600         # 會話超時時間（秒）
MAX_FAILED_ATTEMPTS=3        # IP 封鎖前的最大失敗次數
BLACKLIST_DURATION=86400     # IP 封鎖時間（秒）
ADMIN_ONLY_LOCAL=true        # 管理功能僅限本地端
```

---

## 🔮 未來規劃（v3.1+）

### 個人筆記功能準備
- **用戶隔離**：每個用戶的筆記完全隔離
- **筆記分類**：支援標籤與分類
- **知識圖譜個人化**：基於個人筆記的知識關聯

### 高級安全功能
- **雙因素認證 (2FA)**：Google Authenticator 整合
- **API 金鑰管理**：為程式化存取提供 API
- **審計日誌**：完整的操作記錄與稽核

---

## ⚠️ 安全注意事項

1. **密碼安全**：
   - 最少 8 字元，必須包含大小寫字母、數字、特殊符號
   - 使用 bcrypt 或 argon2 加密
   - 定期提醒更換密碼

2. **會話安全**：
   - 使用 HTTPS（生產環境必須）
   - 會話 token 定期刷新
   - 登出時清除所有會話

3. **監控與警告**：
   - 異常登入行為監控
   - 管理員操作記錄
   - 定期安全掃描

---

**注意**：v2.0 的知識圖譜功能將延後到 v3.1，優先完成安全系統建設。
