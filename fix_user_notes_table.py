#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修復 user_notes 表結構腳本
將 user_notes 表的 id 欄位從 INT 改為 VARCHAR(36) 以支持 UUID
"""

import os
import sys
import uuid
import mysql.connector
from datetime import datetime
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

def get_mysql_connection():
    """獲取 MySQL 連接"""
    db_url = os.environ.get('DATABASE_URL', '')
    print(f'DATABASE_URL: {db_url}')
    
    if 'mysql' not in db_url:
        print("❌ 這個腳本只支持 MySQL 資料庫")
        return None
    
    # 解析 MySQL 連接字串
    db_url = db_url.replace('mysql+mysqlconnector://', '')
    auth_part, host_db_part = db_url.split('@')
    username, password = auth_part.split(':')
    host_port, database = host_db_part.split('/')
    host, port = host_port.split(':')
    
    # 解碼密碼中的特殊字符
    password = password.replace('%40', '@').replace('%23', '#').replace('%21', '!')
    
    print(f'連接到: {host}:{port}, 資料庫: {database}')
    
    try:
        conn = mysql.connector.connect(
            host=host,
            port=int(port),
            user=username,
            password=password,
            database=database
        )
        return conn
    except Exception as e:
        print(f"❌ 連接資料庫失敗: {e}")
        return None

def check_table_structure(conn):
    """檢查當前表結構"""
    print("🔍 檢查當前 user_notes 表結構...")
    
    cursor = conn.cursor()
    
    # 檢查表是否存在
    cursor.execute("SHOW TABLES LIKE 'user_notes'")
    if not cursor.fetchone():
        print("📝 user_notes 表不存在，無需修改")
        cursor.close()
        return False
    
    # 檢查當前結構
    cursor.execute("DESCRIBE user_notes")
    columns = cursor.fetchall()
    
    id_column = None
    for col in columns:
        if col[0] == 'id':
            id_column = col
            break
    
    if id_column:
        print(f"  當前 id 欄位類型: {id_column[1]}")
        if 'varchar' in id_column[1].lower() or 'char' in id_column[1].lower():
            print("✅ id 欄位已經是字符串類型，無需修改")
            cursor.close()
            return False
    
    cursor.close()
    return True

def backup_existing_data(conn):
    """備份現有數據"""
    print("💾 備份現有數據...")
    
    cursor = conn.cursor()
    
    # 檢查是否有數據
    cursor.execute("SELECT COUNT(*) FROM user_notes")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("  📄 表中無數據，跳過備份")
        cursor.close()
        return []
    
    print(f"  📄 發現 {count} 筆記錄，正在備份...")
    
    # 獲取所有數據
    cursor.execute("""
        SELECT id, user_id, title, content, content_type, tags, 
               ai_summary, ai_keywords, created_at, updated_at, is_archived
        FROM user_notes
    """)
    
    data = cursor.fetchall()
    cursor.close()
    
    print(f"  ✅ 成功備份 {len(data)} 筆記錄")
    return data

def modify_table_structure(conn):
    """修改表結構"""
    print("🔧 修改表結構...")
    
    cursor = conn.cursor()
    
    try:
        # 1. 禁用外鍵檢查
        print("  1. 禁用外鍵檢查...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # 2. 檢查並刪除依賴的表（如果存在）
        dependent_tables = [
            'note_category_links',
            'note_knowledge_links', 
            'note_relationships',
            'note_ai_analysis'
        ]
        
        for table in dependent_tables:
            print(f"  2. 檢查表 {table}...")
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            if cursor.fetchone():
                print(f"     刪除表 {table}...")
                cursor.execute(f"DROP TABLE {table}")
        
        # 3. 創建新的 user_notes 表 (用 UUID 作為主鍵)
        print("  3. 創建新的 user_notes 表結構...")
        cursor.execute("DROP TABLE IF EXISTS user_notes")
        cursor.execute("""
            CREATE TABLE user_notes (
                id VARCHAR(36) PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                content_type VARCHAR(20) DEFAULT 'markdown',
                tags TEXT,
                ai_summary TEXT,
                ai_keywords TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                is_archived INT DEFAULT 0,
                INDEX idx_user_id (user_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        print("  ✅ 新表創建成功")
        
        # 4. 重新創建依賴的表（如果需要）
        print("  4. 重新創建依賴表...")
        
        # 創建 note_category_links 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS note_categories (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT NOT NULL,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                color VARCHAR(7),
                icon VARCHAR(50),
                parent_id INT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_id (user_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (parent_id) REFERENCES note_categories(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE note_category_links (
                note_id VARCHAR(36),
                category_id INT,
                PRIMARY KEY (note_id, category_id),
                FOREIGN KEY (note_id) REFERENCES user_notes(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES note_categories(id) ON DELETE CASCADE
            )
        """)
        
        # 創建 note_knowledge_links 表
        cursor.execute("""
            CREATE TABLE note_knowledge_links (
                note_id VARCHAR(36),
                knowledge_point_id INT,
                relevance_score FLOAT DEFAULT 0.8,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (note_id, knowledge_point_id),
                FOREIGN KEY (note_id) REFERENCES user_notes(id) ON DELETE CASCADE,
                FOREIGN KEY (knowledge_point_id) REFERENCES knowledge_points(id) ON DELETE CASCADE
            )
        """)
        
        # 創建 note_relationships 表
        cursor.execute("""
            CREATE TABLE note_relationships (
                id INT PRIMARY KEY AUTO_INCREMENT,
                source_note_id VARCHAR(36) NOT NULL,
                target_note_id VARCHAR(36) NOT NULL,
                relationship_type VARCHAR(50) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_note_id) REFERENCES user_notes(id) ON DELETE CASCADE,
                FOREIGN KEY (target_note_id) REFERENCES user_notes(id) ON DELETE CASCADE
            )
        """)
        
        # 創建 note_ai_analysis 表
        cursor.execute("""
            CREATE TABLE note_ai_analysis (
                id INT PRIMARY KEY AUTO_INCREMENT,
                note_id VARCHAR(36) NOT NULL,
                analysis_type VARCHAR(50) NOT NULL,
                result TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (note_id) REFERENCES user_notes(id) ON DELETE CASCADE
            )
        """)
        
        print("  ✅ 依賴表重新創建完成")
        
        # 5. 重新啟用外鍵檢查
        print("  5. 重新啟用外鍵檢查...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        print("  ✅ 表結構修改完成")
        
        conn.commit()
        cursor.close()
        return True
        
    except Exception as e:
        print(f"  ❌ 修改表結構失敗: {e}")
        # 確保重新啟用外鍵檢查
        try:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        except:
            pass
        conn.rollback()
        cursor.close()
        return False

def restore_data_with_uuid(conn, backup_data):
    """用 UUID 恢復數據"""
    if not backup_data:
        print("📝 無數據需要恢復")
        return True
    
    print(f"🔄 恢復數據（轉換為 UUID）...")
    
    cursor = conn.cursor()
    
    try:
        # 為每筆記錄生成新的 UUID
        for i, row in enumerate(backup_data):
            old_id, user_id, title, content, content_type, tags, ai_summary, ai_keywords, created_at, updated_at, is_archived = row
            
            # 生成新的 UUID
            new_id = str(uuid.uuid4())
            
            # 插入數據
            cursor.execute("""
                INSERT INTO user_notes 
                (id, user_id, title, content, content_type, tags, ai_summary, ai_keywords, created_at, updated_at, is_archived)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (new_id, user_id, title, content, content_type, tags, ai_summary, ai_keywords, created_at, updated_at, is_archived))
            
            print(f"  📄 記錄 {i+1}/{len(backup_data)}: {old_id} -> {new_id}")
        
        conn.commit()
        cursor.close()
        
        print(f"  ✅ 成功恢復 {len(backup_data)} 筆記錄")
        return True
        
    except Exception as e:
        print(f"  ❌ 恢復數據失敗: {e}")
        conn.rollback()
        cursor.close()
        return False

def verify_result(conn):
    """驗證結果"""
    print("🔍 驗證修改結果...")
    
    cursor = conn.cursor()
    
    # 檢查表結構
    cursor.execute("DESCRIBE user_notes")
    columns = cursor.fetchall()
    
    id_column = None
    for col in columns:
        if col[0] == 'id':
            id_column = col
            break
    
    if id_column and 'varchar(36)' in id_column[1].lower():
        print("  ✅ id 欄位類型正確: VARCHAR(36)")
    else:
        print(f"  ❌ id 欄位類型錯誤: {id_column[1] if id_column else 'NOT FOUND'}")
        cursor.close()
        return False
    
    # 檢查數據
    cursor.execute("SELECT COUNT(*) FROM user_notes")
    count = cursor.fetchone()[0]
    print(f"  📄 表中記錄數: {count}")
    
    # 檢查 UUID 格式
    if count > 0:
        cursor.execute("SELECT id FROM user_notes LIMIT 1")
        sample_id = cursor.fetchone()[0]
        print(f"  🆔 樣本 ID: {sample_id}")
        
        # 驗證 UUID 格式
        try:
            uuid.UUID(sample_id)
            print("  ✅ UUID 格式正確")
        except ValueError:
            print("  ❌ UUID 格式錯誤")
            cursor.close()
            return False
    
    cursor.close()
    return True

def main():
    print("🚀 開始修復 user_notes 表結構...")
    print("⚠️  這個操作會修改資料庫結構，請確保已備份資料庫!")
    
    # 確認操作
    confirmation = input("是否繼續? (y/N): ").strip().lower()
    if confirmation != 'y':
        print("❌ 操作已取消")
        return
    
    # 連接資料庫
    conn = get_mysql_connection()
    if not conn:
        return
    
    try:
        # 檢查表結構
        if not check_table_structure(conn):
            print("✅ 無需修改")
            return
        
        # 備份數據
        backup_data = backup_existing_data(conn)
        
        # 修改表結構
        if not modify_table_structure(conn):
            print("❌ 修改表結構失敗")
            return
        
        # 恢復數據
        if not restore_data_with_uuid(conn, backup_data):
            print("❌ 恢復數據失敗")
            return
        
        # 驗證結果
        if verify_result(conn):
            print("🎉 user_notes 表結構修復完成!")
        else:
            print("❌ 驗證失敗，請檢查結果")
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()
