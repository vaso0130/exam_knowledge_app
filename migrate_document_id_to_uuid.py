#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文檔與筆記 UUID 遷移腳本
將 documents 和 user_notes 表的 ID 從自動遞增整數改為 UUID 字符串
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

def check_existing_data(engine):
    """檢查現有數據狀況"""
    print("🔍 檢查現有數據...")
    
    with engine.begin() as conn:
        # 檢查文檔
        doc_result = conn.execute(text("SELECT COUNT(*) FROM documents"))
        doc_count = doc_result.scalar()
        
        # 檢查文檔ID格式
        if doc_count > 0:
            sample_doc = conn.execute(text("SELECT id FROM documents LIMIT 1")).fetchone()
            doc_id_sample = sample_doc[0] if sample_doc else None
            doc_is_uuid = len(str(doc_id_sample)) == 36 if doc_id_sample else False
        else:
            doc_is_uuid = True  # 沒有數據視為已遷移
        
        # 檢查筆記
        note_result = conn.execute(text("SELECT COUNT(*) FROM user_notes"))
        note_count = note_result.scalar()
        
        # 檢查筆記ID格式
        if note_count > 0:
            sample_note = conn.execute(text("SELECT id FROM user_notes LIMIT 1")).fetchone()
            note_id_sample = sample_note[0] if sample_note else None
            note_is_uuid = len(str(note_id_sample)) == 36 if note_id_sample else False
        else:
            note_is_uuid = True  # 沒有數據視為已遷移
        
        print(f"  📄 文檔數量: {doc_count} ({'已是UUID' if doc_is_uuid else '需要遷移'})")
        print(f"  📝 筆記數量: {note_count} ({'已是UUID' if note_is_uuid else '需要遷移'})")
        
        return doc_count, doc_is_uuid, note_count, note_is_uuid

def migrate_documents_to_uuid(engine):
    """遷移文檔ID到UUID"""
    print("\n📄 開始遷移文檔...")
    
    # 檢查是否需要遷移
    with engine.begin() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM documents"))
        count = result.scalar()
        
        if count == 0:
            print("  📄 沒有文檔需要遷移")
            return {}
        
        # 檢查是否已經是UUID格式
        sample = conn.execute(text("SELECT id FROM documents LIMIT 1")).fetchone()
        if sample and len(str(sample[0])) == 36:
            print("  📄 文檔ID已經是UUID格式，跳過遷移")
            return {}
    
    # 創建備份
    print("  📦 創建文檔備份表...")
    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE TABLE documents_backup AS SELECT * FROM documents"))
            conn.execute(text("CREATE TABLE questions_backup AS SELECT * FROM questions"))
        except Exception as e:
            if "already exists" not in str(e):
                print(f"    ⚠️  備份表可能已存在: {e}")
    
    # 獲取現有數據
    with engine.begin() as conn:
        docs_result = conn.execute(text("SELECT * FROM documents ORDER BY id"))
        documents = docs_result.fetchall()
        
        questions_result = conn.execute(text("SELECT * FROM questions"))
        questions = questions_result.fetchall()
    
    # 創建ID映射
    doc_id_mapping = {}
    for doc in documents:
        old_id = doc[0]
        new_id = str(uuid.uuid4())
        doc_id_mapping[old_id] = new_id
    
    print(f"  📋 創建了 {len(doc_id_mapping)} 個文檔ID映射")
    
    # 遷移文檔表
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM documents"))
        
        for doc in documents:
            old_id = doc[0]
            new_id = doc_id_mapping[old_id]
            
            conn.execute(text("""
                INSERT INTO documents 
                (id, user_id, title, file_path, original_filename, processed_content, 
                 ai_summary, ai_keywords, upload_time, file_size, file_type, is_processed)
                VALUES 
                (:id, :user_id, :title, :file_path, :original_filename, :processed_content,
                 :ai_summary, :ai_keywords, :upload_time, :file_size, :file_type, :is_processed)
            """), {
                'id': new_id,
                'user_id': doc[1],
                'title': doc[2],
                'file_path': doc[3],
                'original_filename': doc[4],
                'processed_content': doc[5],
                'ai_summary': doc[6],
                'ai_keywords': doc[7],
                'upload_time': doc[8],
                'file_size': doc[9],
                'file_type': doc[10],
                'is_processed': doc[11]
            })
    
    # 遷移問題表
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM questions"))
        
        for q in questions:
            old_doc_id = q[1]
            if old_doc_id in doc_id_mapping:
                conn.execute(text("""
                    INSERT INTO questions 
                    (id, document_id, question_text, answer_text, question_type, 
                     difficulty, ai_generated, created_at)
                    VALUES 
                    (:id, :document_id, :question_text, :answer_text, :question_type,
                     :difficulty, :ai_generated, :created_at)
                """), {
                    'id': q[0],  # 問題ID保持原樣
                    'document_id': doc_id_mapping[old_doc_id],
                    'question_text': q[2],
                    'answer_text': q[3],
                    'question_type': q[4],
                    'difficulty': q[5],
                    'ai_generated': q[6],
                    'created_at': q[7]
                })
    
    print(f"  ✅ 文檔遷移完成: {len(documents)} 個文檔, {len(questions)} 個問題")
    return doc_id_mapping

def migrate_notes_to_uuid(engine):
    """遷移筆記ID到UUID"""
    print("\n📝 開始遷移筆記...")
    
    # 檢查是否需要遷移
    with engine.begin() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM user_notes"))
        count = result.scalar()
        
        if count == 0:
            print("  📝 沒有筆記需要遷移")
            return {}
        
        # 檢查是否已經是UUID格式
        sample = conn.execute(text("SELECT id FROM user_notes LIMIT 1")).fetchone()
        if sample and len(str(sample[0])) == 36:
            print("  📝 筆記ID已經是UUID格式，跳過遷移")
            return {}
    
    # 創建備份
    print("  📦 創建筆記備份表...")
    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE TABLE user_notes_backup AS SELECT * FROM user_notes"))
            conn.execute(text("CREATE TABLE note_category_links_backup AS SELECT * FROM note_category_links"))
            conn.execute(text("CREATE TABLE note_knowledge_links_backup AS SELECT * FROM note_knowledge_links"))
            conn.execute(text("CREATE TABLE note_relationships_backup AS SELECT * FROM note_relationships"))
            conn.execute(text("CREATE TABLE note_ai_analysis_backup AS SELECT * FROM note_ai_analysis"))
        except Exception as e:
            if "already exists" not in str(e):
                print(f"    ⚠️  備份表可能已存在: {e}")
    
    # 獲取現有數據
    with engine.begin() as conn:
        notes_result = conn.execute(text("SELECT * FROM user_notes ORDER BY id"))
        notes = notes_result.fetchall()
        
        category_links_result = conn.execute(text("SELECT * FROM note_category_links"))
        category_links = category_links_result.fetchall()
        
        knowledge_links_result = conn.execute(text("SELECT * FROM note_knowledge_links"))
        knowledge_links = knowledge_links_result.fetchall()
        
        relationships_result = conn.execute(text("SELECT * FROM note_relationships"))
        relationships = relationships_result.fetchall()
        
        ai_analysis_result = conn.execute(text("SELECT * FROM note_ai_analysis"))
        ai_analysis = ai_analysis_result.fetchall()
    
    # 創建ID映射
    note_id_mapping = {}
    for note in notes:
        old_id = note[0]
        new_id = str(uuid.uuid4())
        note_id_mapping[old_id] = new_id
    
    print(f"  📋 創建了 {len(note_id_mapping)} 個筆記ID映射")
    
    # 遷移筆記表
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM user_notes"))
        
        for note in notes:
            old_id = note[0]
            new_id = note_id_mapping[old_id]
            
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
    
    # 遷移相關表
    with engine.begin() as conn:
        # 分類關聯
        if category_links:
            conn.execute(text("DELETE FROM note_category_links"))
            for link in category_links:
                old_note_id = link[0]
                if old_note_id in note_id_mapping:
                    conn.execute(text("""
                        INSERT INTO note_category_links (note_id, category_id)
                        VALUES (:note_id, :category_id)
                    """), {
                        'note_id': note_id_mapping[old_note_id],
                        'category_id': link[1]
                    })
        
        # 知識點關聯
        if knowledge_links:
            conn.execute(text("DELETE FROM note_knowledge_links"))
            for link in knowledge_links:
                old_note_id = link[0]
                if old_note_id in note_id_mapping:
                    conn.execute(text("""
                        INSERT INTO note_knowledge_links (note_id, knowledge_point_id)
                        VALUES (:note_id, :knowledge_point_id)
                    """), {
                        'note_id': note_id_mapping[old_note_id],
                        'knowledge_point_id': link[1]
                    })
        
        # 筆記關係
        if relationships:
            conn.execute(text("DELETE FROM note_relationships"))
            for rel in relationships:
                old_source_id = rel[1]
                old_target_id = rel[2]
                if old_source_id in note_id_mapping and old_target_id in note_id_mapping:
                    conn.execute(text("""
                        INSERT INTO note_relationships 
                        (id, source_note_id, target_note_id, relationship_type, created_at)
                        VALUES (:id, :source_note_id, :target_note_id, :relationship_type, :created_at)
                    """), {
                        'id': rel[0],
                        'source_note_id': note_id_mapping[old_source_id],
                        'target_note_id': note_id_mapping[old_target_id],
                        'relationship_type': rel[3],
                        'created_at': rel[4]
                    })
        
        # AI分析
        if ai_analysis:
            conn.execute(text("DELETE FROM note_ai_analysis"))
            for analysis in ai_analysis:
                old_note_id = analysis[1]
                if old_note_id in note_id_mapping:
                    conn.execute(text("""
                        INSERT INTO note_ai_analysis 
                        (id, note_id, analysis_type, result, created_at)
                        VALUES (:id, :note_id, :analysis_type, :result, :created_at)
                    """), {
                        'id': analysis[0],
                        'note_id': note_id_mapping[old_note_id],
                        'analysis_type': analysis[2],
                        'result': analysis[3],
                        'created_at': analysis[4]
                    })
    
    print(f"  ✅ 筆記遷移完成: {len(notes)} 個筆記")
    return note_id_mapping

def save_migration_log(doc_mapping, note_mapping):
    """保存遷移日誌"""
    log_data = {
        'migration_type': 'documents_and_notes_to_uuid',
        'timestamp': datetime.now().isoformat(),
        'document_id_mapping': doc_mapping,
        'note_id_mapping': note_mapping,
        'total_documents_migrated': len(doc_mapping),
        'total_notes_migrated': len(note_mapping)
    }
    
    log_file = f"uuid_migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)
    
    print(f"📄 遷移日誌已保存: {log_file}")

def main():
    """主函數"""
    print("🚀 開始文檔與筆記UUID遷移...")
    print("⚠️  請確保已備份資料庫!")
    
    try:
        # 連接資料庫
        db_url = get_db_connection_string()
        engine = create_engine(db_url)
        
        # 檢查現有數據
        doc_count, doc_is_uuid, note_count, note_is_uuid = check_existing_data(engine)
        
        # 確認執行
        if doc_is_uuid and note_is_uuid:
            print("\n✅ 所有數據已經是UUID格式，無需遷移")
            return
        
        need_migration = []
        if not doc_is_uuid and doc_count > 0:
            need_migration.append(f"文檔 ({doc_count} 個)")
        if not note_is_uuid and note_count > 0:
            need_migration.append(f"筆記 ({note_count} 個)")
        
        if need_migration:
            print(f"\n需要遷移: {', '.join(need_migration)}")
            response = input("確定要繼續嗎? (yes/no): ").strip().lower()
            if response != 'yes':
                print("❌ 遷移已取消")
                return
        
        # 執行遷移
        doc_mapping = {}
        note_mapping = {}
        
        if not doc_is_uuid and doc_count > 0:
            doc_mapping = migrate_documents_to_uuid(engine)
        
        if not note_is_uuid and note_count > 0:
            note_mapping = migrate_notes_to_uuid(engine)
        
        # 保存日誌
        if doc_mapping or note_mapping:
            save_migration_log(doc_mapping, note_mapping)
            print(f"\n🎉 UUID遷移完成!")
            print(f"📄 文檔遷移: {len(doc_mapping)} 個")
            print(f"📝 筆記遷移: {len(note_mapping)} 個")
        else:
            print("\n✅ 沒有需要遷移的數據")
            
    except SQLAlchemyError as e:
        print(f"\n❌ 資料庫錯誤: {e}")
        print("🔄 建議從備份恢復資料")
    except Exception as e:
        print(f"\n❌ 遷移失敗: {e}")
        print("🔄 建議從備份恢復資料")

if __name__ == '__main__':
    main()