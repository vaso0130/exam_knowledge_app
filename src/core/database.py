import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import os

class DatabaseManager:
    def __init__(self, db_path: str = "./db.sqlite3"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.init_database()
    
    def init_database(self):
        """初始化資料庫表格"""
        # 建立持久連接
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # 建立 documents 表格
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                original_content TEXT,
                type TEXT,
                subject TEXT,
                file_path TEXT,
                tags TEXT,
                source TEXT,
                mindmap TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 建立 questions 表格  
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                title TEXT,
                question_text TEXT,
                answer_text TEXT,
                answer_sources TEXT,
                subject TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                mindmap_code TEXT,
                FOREIGN KEY (document_id) REFERENCES documents (id)
            )
        ''')
        
        # 為現有表新增 answer_sources 欄位（如果不存在）
        try:
            self.cursor.execute('ALTER TABLE questions ADD COLUMN answer_sources TEXT')
            self.conn.commit()
        except sqlite3.OperationalError:
            # 欄位已存在，忽略錯誤
            pass
        
        # 建立 knowledge_points 表格
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                subject TEXT,
                description TEXT
            )
        ''')

        # 建立 question_knowledge_links 表格
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS question_knowledge_links (
                question_id INTEGER,
                knowledge_point_id INTEGER,
                PRIMARY KEY (question_id, knowledge_point_id),
                FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE,
                FOREIGN KEY (knowledge_point_id) REFERENCES knowledge_points (id) ON DELETE CASCADE
            )
        ''')

        self.conn.commit()
        
        # 確保表格欄位存在（向後相容性）
        self._ensure_columns_exist()
    
    def _ensure_columns_exist(self):
        """確保所有必要的欄位都存在"""
        # 為現有表新增 title 欄位（如果不存在）
        try:
            self.cursor.execute('ALTER TABLE questions ADD COLUMN title TEXT')
            self.conn.commit()
        except sqlite3.OperationalError:
            # 欄位已存在，忽略錯誤
            pass
        
        # 為現有表新增 mindmap_code 欄位（如果不存在）
        try:
            self.cursor.execute('ALTER TABLE questions ADD COLUMN mindmap_code TEXT')
            self.conn.commit()
        except sqlite3.OperationalError:
            # 欄位已存在，忽略錯誤
            pass
        
        # 為現有表新增 original_content 欄位（如果不存在）
        try:
            self.cursor.execute('ALTER TABLE documents ADD COLUMN original_content TEXT')
            self.conn.commit()
        except sqlite3.OperationalError:
            # 欄位已存在，忽略錯誤
            pass
        
        # 為現有表新增 key_points_summary 欄位（如果不存在）
        try:
            self.cursor.execute('ALTER TABLE documents ADD COLUMN key_points_summary TEXT')
            self.conn.commit()
        except sqlite3.OperationalError:
            # 欄位已存在，忽略錯誤
            pass
        
        # 為現有表新增 quick_quiz 欄位（如果不存在）
        try:
            self.cursor.execute('ALTER TABLE documents ADD COLUMN quick_quiz TEXT')
            self.conn.commit()
        except sqlite3.OperationalError:
            # 欄位已存在，忽略錯誤
            pass
    
    def close(self):
        """關閉資料庫連接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def insert_document(self, title: str, content: str, doc_type: str = "info", 
                       subject: str = None, file_path: str = None, original_content: str = None) -> int:
        """插入文件記錄"""
        self.cursor.execute('''
            INSERT INTO documents (title, content, original_content, type, subject, file_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, content, original_content, doc_type, subject, file_path))
        
        self.conn.commit()
        return self.cursor.lastrowid
    
    def insert_question(self, document_id: int, title: str, question_text: str, answer_text: str = None,
                       subject: str = None, answer_sources: str = None) -> int:
        """插入題目記錄"""
        self.cursor.execute('''
            INSERT INTO questions (document_id, title, question_text, answer_text, subject, answer_sources)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (document_id, title, question_text, answer_text, subject, answer_sources))
        
        self.conn.commit()
        return self.cursor.lastrowid
    
    def add_document(self, title: str, content: str, subject: str = None, 
                    tags: str = None, file_path: str = None, source: str = None, 
                    original_content: str = None, key_points_summary: str = None, 
                    quick_quiz: str = None) -> int:
        """添加文件記錄（支援完整欄位）"""
        self.cursor.execute('''
            INSERT INTO documents (title, content, original_content, type, subject, file_path, tags, source, key_points_summary, quick_quiz)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, content, original_content, "info", subject, file_path, tags, source, key_points_summary, quick_quiz))
        
        self.conn.commit()
        return self.cursor.lastrowid
    
    def add_question(self, document_id: int, question_text: str, answer_text: str = None,
                    subject: str = None, answer_sources: str = None) -> int:
        """添加題目記錄"""
        return self.insert_question(document_id, question_text, answer_text, subject, answer_sources)
    
    def get_documents_by_subject(self, subject: str) -> List[Tuple]:
        """根據科目取得文件"""
        self.cursor.execute('''
            SELECT id, title, content, type, subject, file_path, created_at 
            FROM documents WHERE subject = ? ORDER BY created_at DESC
        ''', (subject,))
        
        return self.cursor.fetchall()
    
    def get_questions_by_document(self, document_id: int) -> List[Tuple]:
        """根據文件ID取得題目"""
        self.cursor.execute('''
            SELECT id, document_id, question_text, answer_text, subject, created_at 
            FROM questions WHERE document_id = ? ORDER BY created_at DESC
        ''', (document_id,))
        
        return self.cursor.fetchall()
    
    def get_questions_by_document_id(self, document_id: int) -> List[Tuple]:
        """根據文件ID取得題目（包含標題）"""
        self.cursor.execute('''
            SELECT id, subject, title, question_text, answer_text, created_at
            FROM questions WHERE document_id = ? ORDER BY created_at DESC
        ''', (document_id,))
        
        return self.cursor.fetchall()
    
    def search_documents(self, query: str, subject: str = None) -> List[Tuple]:
        """搜尋文件"""
        if subject:
            self.cursor.execute('''
                SELECT id, title, content, type, subject, file_path, created_at 
                FROM documents 
                WHERE subject = ? AND (content LIKE ? OR title LIKE ?)
                ORDER BY created_at DESC
            ''', (subject, f'%{query}%', f'%{query}%'))
        else:
            self.cursor.execute('''
                SELECT id, title, content, type, subject, file_path, created_at 
                FROM documents 
                WHERE content LIKE ? OR title LIKE ?
                ORDER BY created_at DESC
            ''', (f'%{query}%', f'%{query}%'))
        
        return self.cursor.fetchall()
    
    def get_all_subjects(self) -> List[str]:
        """取得所有科目"""
        self.cursor.execute('SELECT DISTINCT subject FROM documents ORDER BY subject')
        return [row[0] for row in self.cursor.fetchall()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """取得統計資料"""
        # 文件統計
        self.cursor.execute('SELECT COUNT(*) FROM documents')
        total_docs = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT COUNT(*) FROM documents WHERE type = "exam"')
        exam_docs = self.cursor.fetchone()[0]
        
        self.cursor.execute('SELECT COUNT(*) FROM questions')
        total_questions = self.cursor.fetchone()[0]
        
        # 各科目統計
        self.cursor.execute('''
            SELECT subject, COUNT(*) FROM documents GROUP BY subject ORDER BY subject
        ''')
        subject_stats = dict(self.cursor.fetchall())
        
        return {
            'total_documents': total_docs,
            'exam_documents': exam_docs,
            'info_documents': total_docs - exam_docs,
            'total_questions': total_questions,
            'subject_statistics': subject_stats
        }
    
    def get_all_documents(self):
        """獲取所有文件"""
        self.cursor.execute('''
            SELECT id, title, content, type, subject, file_path, source, created_at 
            FROM documents 
            ORDER BY created_at DESC
        ''')
        return self.cursor.fetchall()

    def delete_document_and_questions(self, document_id):
        """刪除文件及其所有關聯的題目"""
        try:
            # 先刪除關聯的題目
            self.cursor.execute('DELETE FROM questions WHERE document_id = ?', (document_id,))
            
            # 再刪除文件本身
            self.cursor.execute('DELETE FROM documents WHERE id = ?', (document_id,))
            
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"刪除文件時發生資料庫錯誤: {e}")
            self.conn.rollback()
            return False
    
    def get_all_questions_with_source(self) -> List[Tuple]:
        """取得所有題目及其來源文件資訊"""
        self.cursor.execute('''
            SELECT q.id, q.subject, q.title, q.question_text, q.answer_text, d.title, q.created_at
            FROM questions q
            JOIN documents d ON q.document_id = d.id
            ORDER BY q.created_at DESC
        ''')
        
        return self.cursor.fetchall()
    
    def get_questions_by_subject(self, subject: str) -> List[Tuple]:
        """根據科目取得所有題目"""
        self.cursor.execute('''
            SELECT q.id, q.subject, q.title, q.question_text, q.answer_text, d.title, q.created_at
            FROM questions q
            JOIN documents d ON q.document_id = d.id
            WHERE q.subject = ?
            ORDER BY q.created_at DESC
        ''', (subject,))
        
        return self.cursor.fetchall()
    
    def search_questions(self, query: str, subject: str = None) -> List[Tuple]:
        """搜尋題目"""
        if subject:
            self.cursor.execute('''
                SELECT q.id, q.subject, q.title, q.question_text, q.answer_text, d.title, q.created_at
                FROM questions q
                JOIN documents d ON q.document_id = d.id
                WHERE q.subject = ? AND (q.question_text LIKE ? OR q.answer_text LIKE ?)
                ORDER BY q.created_at DESC
            ''', (subject, f'%{query}%', f'%{query}%'))
        else:
            self.cursor.execute('''
                SELECT q.id, q.subject, q.title, q.question_text, q.answer_text, d.title, q.created_at
                FROM questions q
                JOIN documents d ON q.document_id = d.id
                WHERE q.question_text LIKE ? OR q.answer_text LIKE ?
                ORDER BY q.created_at DESC
            ''', (f'%{query}%', f'%{query}%'))
        
        return self.cursor.fetchall()
    
    def get_document_by_id(self, document_id: int) -> Optional[Dict[str, Any]]:
        """根據ID取得單一文件"""
        self.cursor.execute('''
            SELECT id, title, content, original_content, type, subject, file_path, tags, source, mindmap, created_at, key_points_summary, quick_quiz
            FROM documents WHERE id = ?
        ''', (document_id,))
        
        row = self.cursor.fetchone()
        if row:
            keys = ["id", "title", "content", "original_content", "type", "subject", "file_path", "tags", "source", "mindmap", "created_at", "key_points_summary", "quick_quiz"]
            return dict(zip(keys, row))
        return None



    def get_question_by_id(self, question_id: int) -> Optional[Dict[str, Any]]:
        """根據ID取得單一問題"""
        self.cursor.execute('''
            SELECT q.id, q.document_id, q.title, q.question_text, q.answer_text, q.answer_sources, q.subject, q.created_at, q.mindmap_code, d.title
            FROM questions q
            LEFT JOIN documents d ON q.document_id = d.id
            WHERE q.id = ?
        ''', (question_id,))
        
        row = self.cursor.fetchone()
        if row:
            keys = ["id", "document_id", "title", "question_text", "answer_text", "answer_sources", "subject", "created_at", "mindmap_code", "doc_title"]
            question_data = dict(zip(keys, row))
            
            # 獲取關聯的知識點
            question_data['knowledge_points'] = self.get_knowledge_points_for_question(question_id)
            return question_data
            
        return None
    
    def update_question_mindmap(self, question_id: int, mindmap_code: str):
        """更新問題的心智圖程式碼"""
        self.cursor.execute('''
            UPDATE questions
            SET mindmap_code = ?
            WHERE id = ?
        ''', (mindmap_code, question_id))
        self.conn.commit()

    def update_document_mindmap(self, document_id: int, mindmap_data: str):
        """更新文檔的心智圖資料"""
        self.cursor.execute('''
            UPDATE documents
            SET mindmap = ?
            WHERE id = ?
        ''', (mindmap_data, document_id))
        self.conn.commit()

    # --- 新增知識點相關方法 ---

    def add_knowledge_point(self, name: str, subject: str, description: str = "") -> int:
        """新增知識點，返回其ID（如果已存在則返回現有ID）"""
        return self.add_or_get_knowledge_point(name, subject, description)

    def add_or_get_knowledge_point(self, name: str, subject: str, description: str = "") -> int:
        """新增或取得知識點，返回其ID"""
        self.cursor.execute('SELECT id FROM knowledge_points WHERE name = ?', (name,))
        result = self.cursor.fetchone()
        if result:
            return result[0]
        else:
            self.cursor.execute(
                'INSERT INTO knowledge_points (name, subject, description) VALUES (?, ?, ?)',
                (name, subject, description)
            )
            self.conn.commit()
            return self.cursor.lastrowid

    def link_question_to_knowledge_point(self, question_id: int, knowledge_point_id: int):
        """將問題與知識點關聯"""
        self.cursor.execute(
            'INSERT OR IGNORE INTO question_knowledge_links (question_id, knowledge_point_id) VALUES (?, ?)',
            (question_id, knowledge_point_id)
        )
        self.conn.commit()

    def get_knowledge_points_for_question(self, question_id: int) -> List[Dict[str, Any]]:
        """獲取單一問題的所有關聯知識點"""
        self.cursor.execute('''
            SELECT kp.id, kp.name, kp.subject
            FROM knowledge_points kp
            JOIN question_knowledge_links qkl ON kp.id = qkl.knowledge_point_id
            WHERE qkl.question_id = ?
        ''', (question_id,))
        
        points = []
        for row in self.cursor.fetchall():
            points.append({"id": row[0], "name": row[1], "subject": row[2]})
        return points

    def get_questions_for_knowledge_point(self, knowledge_point_id: int) -> List[Dict[str, Any]]:
        """獲取與某個知識點關聯的所有問題"""
        self.cursor.execute('''
            SELECT q.id, q.subject, q.question_text, q.answer_text, d.title, q.created_at, q.document_id
            FROM questions q
            JOIN question_knowledge_links qkl ON q.id = qkl.question_id
            JOIN documents d ON q.document_id = d.id
            WHERE qkl.knowledge_point_id = ?
            ORDER BY q.created_at DESC
        ''', (knowledge_point_id,))
        
        results = self.cursor.fetchall()
        questions = []
        for row in results:
            questions.append({
                'id': row[0],
                'subject': row[1],
                'text': row[2],
                'answer_text': row[3],
                'doc_title': row[4],
                'created_at': row[5],
                'document_id': row[6],
                'doc_id': row[6]  # 為了與模板兼容
            })
        return questions

    def get_all_knowledge_points_by_subject(self) -> Dict[str, List[Dict[str, Any]]]:
        """按科目獲取所有知識點"""
        self.cursor.execute('SELECT id, name, subject FROM knowledge_points ORDER BY subject, name')
        
        subject_map = {}
        for row in self.cursor.fetchall():
            point_id, name, subject = row
            if subject not in subject_map:
                subject_map[subject] = []
            subject_map[subject].append({"id": point_id, "name": name})
        return subject_map

    def get_knowledge_point_by_id(self, knowledge_point_id: int) -> Optional[Dict[str, Any]]:
        """根據ID取得單一知識點"""
        self.cursor.execute('''
            SELECT id, name, subject, description
            FROM knowledge_points WHERE id = ?
        ''', (knowledge_point_id,))
        
        row = self.cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "name": row[1], 
                "subject": row[2],
                "description": row[3]
            }
        return None

    def get_all_knowledge_points_with_stats(self) -> Dict[str, List[Dict[str, Any]]]:
        """按科目獲取所有知識點，並包含關聯問題數量"""
        self.cursor.execute('''
            SELECT 
                kp.id, 
                kp.name, 
                kp.subject, 
                COUNT(qkl.question_id) as question_count
            FROM knowledge_points kp
            LEFT JOIN question_knowledge_links qkl ON kp.id = qkl.knowledge_point_id
            GROUP BY kp.id, kp.name, kp.subject
            ORDER BY kp.subject, kp.name
        ''')
        
        subject_map = {}
        for row in self.cursor.fetchall():
            point_id, name, subject, count = row
            if subject not in subject_map:
                subject_map[subject] = []
            subject_map[subject].append({"id": point_id, "name": name, "question_count": count})
        return subject_map

    def get_all_knowledge_points(self) -> List[tuple]:
        """取得所有知識點（簡單格式，用於相容性）"""
        self.cursor.execute('''
            SELECT id, name, subject, description
            FROM knowledge_points
            ORDER BY subject, name
        ''')
        return self.cursor.fetchall()

    def get_questions_by_knowledge_point(self, knowledge_point_id: int) -> List[tuple]:
        """取得某個知識點相關的所有題目"""
        self.cursor.execute('''
            SELECT q.id, q.subject, q.title, q.question_text, q.answer, q.explanation
            FROM questions q
            JOIN question_knowledge_links qkl ON q.id = qkl.question_id
            WHERE qkl.knowledge_point_id = ?
            ORDER BY q.id
        ''', (knowledge_point_id,))
        return self.cursor.fetchall()

    def get_documents_with_summaries(self) -> List[Dict[str, Any]]:
        """取得所有包含學習摘要或快速測驗的文件"""
        self.cursor.execute('''
            SELECT id, title, subject, created_at, key_points_summary, quick_quiz
            FROM documents 
            WHERE (key_points_summary IS NOT NULL AND key_points_summary != '') 
               OR (quick_quiz IS NOT NULL AND quick_quiz != '')
            ORDER BY created_at DESC
        ''')
        
        results = []
        for row in self.cursor.fetchall():
            results.append({
                'id': row[0],
                'title': row[1],
                'subject': row[2] or '未分類',
                'created_at': row[3],
                'has_summary': bool(row[4]),
                'has_quiz': bool(row[5])
            })
        return results
