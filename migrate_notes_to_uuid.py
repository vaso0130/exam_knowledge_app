#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
筆記 ID UUID 遷移腳本
將 user_notes 表的 ID 從自動遞增整數改為 UUID 字符串
同時更新所有相關的外鍵引用
"""

import os
import sys
import uuid
import json
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# 添加專案根目錄到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.database import get_db_connection_string

def create_backup_tables(engine):
    """創建備份表"""
    print("📦 創建備份表...")
    
    backup_queries = [
        """
        CREATE TABLE user_notes_backup AS 
        SELECT * FROM user_notes
        """,
        """
        CREATE TABLE note_category_links_backup AS 
        SELECT * FROM note_category_links
        """,
        """
        CREATE TABLE note_knowledge_links_backup AS 
        SELECT * FROM note_knowledge_links
        """,
        """
        CREATE TABLE note_relationships_backup AS 
        SELECT * FROM note_relationships
        """,
        """
        CREATE TABLE note_ai_analysis_backup AS 
        SELECT * FROM note_ai_analysis
        """
    ]
    
    with engine.begin() as conn:
        for query in backup_queries:
            try:
                conn.execute(text(query))
                print(f"  ✅ 備份表創建成功")
            except Exception as e:
                if "already exists" not in str(e):
                    print(f"  ⚠️  備份表可能已存在: {e}")

def get_notes_data(engine):
    """獲取現有筆記數據"""
    print("📊 分析現有筆記數據...")
    
    with engine.begin() as conn:
        # 獲取筆記數據
        notes_result = conn.execute(text("SELECT * FROM user_notes ORDER BY id"))
        notes = notes_result.fetchall()
        
        # 獲取關聯數據
        category_links_result = conn.execute(text("SELECT * FROM note_category_links"))
        category_links = category_links_result.fetchall()
        
        knowledge_links_result = conn.execute(text("SELECT * FROM note_knowledge_links"))
        knowledge_links = knowledge_links_result.fetchall()
        
        relationships_result = conn.execute(text("SELECT * FROM note_relationships"))
        relationships = relationships_result.fetchall()
        
        ai_analysis_result = conn.execute(text("SELECT * FROM note_ai_analysis"))
        ai_analysis = ai_analysis_result.fetchall()
        
        print(f"  📝 找到 {len(notes)} 個筆記")
        print(f"  🔗 找到 {len(category_links)} 個分類關聯")
        print(f"  🧠 找到 {len(knowledge_links)} 個知識點關聯")
        print(f"  🔄 找到 {len(relationships)} 個筆記關係")
        print(f"  🤖 找到 {len(ai_analysis)} 個AI分析記錄")
        
        return notes, category_links, knowledge_links, relationships, ai_analysis

def create_id_mapping(notes):
    """創建舊ID到新UUID的映射"""
    print("🗂️  創建ID映射...")
    
    id_mapping = {}
    for note in notes:
        old_id = note[0]  # 舊的整數ID
        new_id = str(uuid.uuid4())  # 新的UUID
        id_mapping[old_id] = new_id
        
    print(f"  📋 創建了 {len(id_mapping)} 個ID映射")
    return id_mapping

def migrate_notes_table(engine, notes, id_mapping):
    """遷移主表"""
    print("🔄 遷移 user_notes 表...")
    
    with engine.begin() as conn:
        # 清空表
        conn.execute(text("DELETE FROM user_notes"))
        
        # 插入新數據
        for note in notes:
            old_id = note[0]
            new_id = id_mapping[old_id]
            
            # 準備插入數據 (跳過舊ID，使用新UUID)
            conn.execute(text("""
                INSERT INTO user_notes 
                (id, user_id, title, content, content_type, tags, ai_summary, ai_keywords, 
                 created_at, updated_at, is_archived)
                VALUES 
                (:id, :user_id, :title, :content, :content_type, :tags, :ai_summary, 
                 :ai_keywords, :created_at, :updated_at, :is_archived)
            """), {
                'id': new_id,
                'user_id': note[1],
                'title': note[2],
                'content': note[3],
                'content_type': note[4] or 'markdown',
                'tags': note[5],
                'ai_summary': note[6],
                'ai_keywords': note[7],
                'created_at': note[8],
                'updated_at': note[9],
                'is_archived': note[10] or 0
            })
    
    print(f"  ✅ 遷移了 {len(notes)} 個筆記")

def migrate_related_tables(engine, category_links, knowledge_links, relationships, ai_analysis, id_mapping):
    """遷移相關表"""
    print("🔗 遷移相關表...")
    
    with engine.begin() as conn:
        # 遷移分類關聯
        if category_links:
            conn.execute(text("DELETE FROM note_category_links"))
            for link in category_links:
                old_note_id = link[0]
                if old_note_id in id_mapping:
                    conn.execute(text("""
                        INSERT INTO note_category_links (note_id, category_id)
                        VALUES (:note_id, :category_id)
                    """), {
                        'note_id': id_mapping[old_note_id],
                        'category_id': link[1]
                    })
            print(f"  ✅ 遷移了 {len(category_links)} 個分類關聯")
        
        # 遷移知識點關聯
        if knowledge_links:
            conn.execute(text("DELETE FROM note_knowledge_links"))
            for link in knowledge_links:
                old_note_id = link[0]
                if old_note_id in id_mapping:
                    conn.execute(text("""
                        INSERT INTO note_knowledge_links (note_id, knowledge_point_id)
                        VALUES (:note_id, :knowledge_point_id)
                    """), {
                        'note_id': id_mapping[old_note_id],
                        'knowledge_point_id': link[1]
                    })
            print(f"  ✅ 遷移了 {len(knowledge_links)} 個知識點關聯")
        
        # 遷移筆記關係
        if relationships:
            conn.execute(text("DELETE FROM note_relationships"))
            for rel in relationships:
                old_source_id = rel[1]
                old_target_id = rel[2]
                if old_source_id in id_mapping and old_target_id in id_mapping:
                    conn.execute(text("""
                        INSERT INTO note_relationships 
                        (id, source_note_id, target_note_id, relationship_type, created_at)
                        VALUES (:id, :source_note_id, :target_note_id, :relationship_type, :created_at)
                    """), {
                        'id': rel[0],  # 保持原有的關係ID
                        'source_note_id': id_mapping[old_source_id],
                        'target_note_id': id_mapping[old_target_id],
                        'relationship_type': rel[3],
                        'created_at': rel[4]
                    })
            print(f"  ✅ 遷移了 {len(relationships)} 個筆記關係")
        
        # 遷移AI分析
        if ai_analysis:
            conn.execute(text("DELETE FROM note_ai_analysis"))
            for analysis in ai_analysis:
                old_note_id = analysis[1]
                if old_note_id in id_mapping:
                    conn.execute(text("""
                        INSERT INTO note_ai_analysis 
                        (id, note_id, analysis_type, result, created_at)
                        VALUES (:id, :note_id, :analysis_type, :result, :created_at)
                    """), {
                        'id': analysis[0],  # 保持原有的分析ID
                        'note_id': id_mapping[old_note_id],
                        'analysis_type': analysis[2],
                        'result': analysis[3],
                        'created_at': analysis[4]
                    })
            print(f"  ✅ 遷移了 {len(ai_analysis)} 個AI分析記錄")

def verify_migration(engine, original_count, id_mapping):
    """驗證遷移結果"""
    print("🔍 驗證遷移結果...")
    
    with engine.begin() as conn:
        # 檢查筆記數量
        result = conn.execute(text("SELECT COUNT(*) FROM user_notes"))
        new_count = result.scalar()
        
        print(f"  📊 原始筆記數量: {original_count}")
        print(f"  📊 遷移後數量: {new_count}")
        
        if new_count == original_count:
            print("  ✅ 筆記數量匹配")
        else:
            print("  ❌ 筆記數量不匹配!")
            return False
        
        # 檢查UUID格式
        result = conn.execute(text("SELECT id FROM user_notes LIMIT 5"))
        sample_ids = result.fetchall()
        
        print("  🔍 檢查UUID格式:")
        for id_row in sample_ids:
            note_id = id_row[0]
            print(f"    📝 {note_id} (長度: {len(note_id)})")
            
            # 驗證UUID格式
            try:
                uuid.UUID(note_id)
                print(f"    ✅ 有效的UUID格式")
            except ValueError:
                print(f"    ❌ 無效的UUID格式!")
                return False
    
    return True

def save_migration_log(id_mapping):
    """保存遷移日誌"""
    log_data = {
        'migration_type': 'notes_to_uuid',
        'timestamp': datetime.now().isoformat(),
        'id_mapping': id_mapping,
        'total_migrated': len(id_mapping)
    }
    
    log_file = f"notes_uuid_migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)
    
    print(f"📄 遷移日誌已保存: {log_file}")

def main():
    """主函數"""
    print("🚀 開始筆記UUID遷移...")
    print("⚠️  請確保已備份資料庫!")
    
    # 確認執行
    response = input("\n確定要繼續嗎? (yes/no): ").strip().lower()
    if response != 'yes':
        print("❌ 遷移已取消")
        return
    
    try:
        # 連接資料庫
        db_url = get_db_connection_string()
        engine = create_engine(db_url)
        
        # 執行遷移步驟
        create_backup_tables(engine)
        notes, category_links, knowledge_links, relationships, ai_analysis = get_notes_data(engine)
        
        if not notes:
            print("📝 沒有找到筆記數據，跳過遷移")
            return
        
        original_count = len(notes)
        id_mapping = create_id_mapping(notes)
        
        migrate_notes_table(engine, notes, id_mapping)
        migrate_related_tables(engine, category_links, knowledge_links, relationships, ai_analysis, id_mapping)
        
        # 驗證結果
        if verify_migration(engine, original_count, id_mapping):
            save_migration_log(id_mapping)
            print("\n🎉 筆記UUID遷移完成!")
            print("✅ 所有筆記ID已成功轉換為UUID格式")
            print("📋 相關表的外鍵引用已同步更新")
        else:
            print("\n❌ 遷移驗證失敗!")
            print("🔄 建議檢查資料或從備份恢復")
            
    except SQLAlchemyError as e:
        print(f"\n❌ 資料庫錯誤: {e}")
        print("🔄 建議從備份恢復資料")
    except Exception as e:
        print(f"\n❌ 遷移失敗: {e}")
        print("🔄 建議從備份恢復資料")

if __name__ == '__main__':
    main()
