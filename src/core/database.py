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
                type TEXT,
                subject TEXT,
                file_path TEXT,
                tags TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 建立 questions 表格  
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                question_text TEXT,
                answer_text TEXT,
                subject TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                mindmap_code TEXT,
                FOREIGN KEY (document_id) REFERENCES documents (id)
            )
        ''')
        
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
    
    def close(self):
        """關閉資料庫連接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def insert_document(self, title: str, content: str, doc_type: str = "info", 
                       subject: str = None, file_path: str = None) -> int:
        """插入文件記錄"""
        self.cursor.execute('''
            INSERT INTO documents (title, content, type, subject, file_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, content, doc_type, subject, file_path))
        
        self.conn.commit()
        return self.cursor.lastrowid
    
    def insert_question(self, document_id: int, question_text: str, answer_text: str = None,
                       subject: str = None) -> int:
        """插入題目記錄"""
        self.cursor.execute('''
            INSERT INTO questions (document_id, question_text, answer_text, subject)
            VALUES (?, ?, ?, ?)
        ''', (document_id, question_text, answer_text, subject))
        
        self.conn.commit()
        return self.cursor.lastrowid
    
    def add_document(self, title: str, content: str, subject: str = None, 
                    tags: str = None, file_path: str = None, source: str = None) -> int:
        """添加文件記錄（支援 tags 和 source）"""
        self.cursor.execute('''
            INSERT INTO documents (title, content, type, subject, file_path, tags, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, content, "info", subject, file_path, tags, source))
        
        self.conn.commit()
        return self.cursor.lastrowid
    
    def add_question(self, document_id: int, question_text: str, answer_text: str = None,
                    subject: str = None) -> int:
        """添加題目記錄"""
        return self.insert_question(document_id, question_text, answer_text, subject)
    
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
            SELECT id, title, content, type, subject, file_path, created_at 
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
            SELECT q.id, q.subject, q.question_text, q.answer_text, d.title, q.created_at
            FROM questions q
            JOIN documents d ON q.document_id = d.id
            ORDER BY q.created_at DESC
        ''')
        
        return self.cursor.fetchall()
    
    def get_questions_by_subject(self, subject: str) -> List[Tuple]:
        """根據科目取得所有題目"""
        self.cursor.execute('''
            SELECT q.id, q.subject, q.question_text, q.answer_text, d.title, q.created_at
            FROM questions q
            JOIN documents d ON q.document_id = d.id
            WHERE d.subject = ?
            ORDER BY q.created_at DESC
        ''', (subject,))
        
        return self.cursor.fetchall()
    
    def search_questions(self, query: str, subject: str = None) -> List[Tuple]:
        """搜尋題目"""
        if subject:
            self.cursor.execute('''
                SELECT q.id, q.subject, q.question_text, q.answer_text, d.title, q.created_at
                FROM questions q
                JOIN documents d ON q.document_id = d.id
                WHERE d.subject = ? AND (q.question_text LIKE ? OR q.answer_text LIKE ?)
                ORDER BY q.created_at DESC
            ''', (subject, f'%{query}%', f'%{query}%'))
        else:
            self.cursor.execute('''
                SELECT q.id, q.subject, q.question_text, q.answer_text, d.title, q.created_at
                FROM questions q
                JOIN documents d ON q.document_id = d.id
                WHERE q.question_text LIKE ? OR q.answer_text LIKE ?
                ORDER BY q.created_at DESC
            ''', (f'%{query}%', f'%{query}%'))
        
        return self.cursor.fetchall()
    
    def get_document_by_id(self, document_id: int) -> Optional[Dict[str, Any]]:
        """根據ID取得單一文件"""
        self.cursor.execute('''
            SELECT id, title, content, type, subject, file_path, created_at 
            FROM documents WHERE id = ?
        ''', (document_id,))
        
        row = self.cursor.fetchone()
        if row:
            keys = ["id", "title", "content", "type", "subject", "file_path", "created_at"]
            return dict(zip(keys, row))
        return None



    def get_question_by_id(self, question_id: int) -> Optional[Dict[str, Any]]:
        """根據ID取得單一問題"""
        self.cursor.execute('''
            SELECT q.id, q.document_id, q.question_text, q.answer_text, q.subject, q.created_at, q.mindmap_code, d.title
            FROM questions q
            LEFT JOIN documents d ON q.document_id = d.id
            WHERE q.id = ?
        ''', (question_id,))
        
        row = self.cursor.fetchone()
        if row:
            keys = ["id", "document_id", "question_text", "answer_text", "subject", "created_at", "mindmap_code", "doc_title"]
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

    # --- 新增知識點相關方法 ---

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

    def get_questions_for_knowledge_point(self, knowledge_point_id: int) -> List[Tuple]:
        """獲取與某個知識點關聯的所有問題"""
        self.cursor.execute('''
            SELECT q.id, q.subject, q.question_text, q.answer_text, d.title, q.created_at
            FROM questions q
            JOIN question_knowledge_links qkl ON q.id = qkl.question_id
            JOIN documents d ON q.document_id = d.id
            WHERE qkl.knowledge_point_id = ?
            ORDER BY q.created_at DESC
        ''', (knowledge_point_id,))
        return self.cursor.fetchall()

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
