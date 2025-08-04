
import os
import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, joinedload
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv

# --- Initial Setup ---
load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./db.sqlite3")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine_args = {"echo": False}
if IS_SQLITE:
    engine_args.update({
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool
    })
engine = create_engine(DATABASE_URL, **engine_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- SQLAlchemy Models (with specified lengths for VARCHARs) ---

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), index=True)
    content = Column(Text)  # Extracted text, can be long
    original_content = Column(Text, nullable=True) # Deprecated but kept for compatibility
    type = Column(String(50), default="info")
    subject = Column(String(255), index=True)
    file_path = Column(String(1024), nullable=True)
    tags = Column(String(512), nullable=True)
    source = Column(String(2048), nullable=True) # For URLs
    mindmap = Column(Text, nullable=True)
    key_points_summary = Column(Text, nullable=True)
    quick_quiz = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # v3.1 上傳者追蹤
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploader_name = Column(String(50), nullable=True)  # 快照，避免 JOIN
    
    # 關聯
    questions = relationship("Question", back_populates="document", cascade="all, delete-orphan")
    uploader = relationship("User", back_populates="uploads")

import uuid # Import uuid module

class Question(Base):
    __tablename__ = "questions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), unique=True) # Changed to String(36) for UUID
    document_id = Column(Integer, ForeignKey("documents.id"))
    title = Column(String(512))
    question_text = Column(Text)
    answer_text = Column(Text, nullable=True)
    answer_sources = Column(Text, nullable=True)
    subject = Column(String(255), index=True)
    difficulty = Column(String(50), nullable=True)
    guidance_level = Column(String(50), nullable=True)
    mindmap_code = Column(Text, nullable=True)
    question_summary = Column(Text, nullable=True)  # 新增：題目摘要
    solving_tips = Column(Text, nullable=True)      # 新增：解題技巧
    created_at = Column(DateTime, default=datetime.utcnow)
    
    document = relationship("Document", back_populates="questions")
    knowledge_points = relationship(
        "KnowledgePoint",
        secondary="question_knowledge_links",
        back_populates="questions"
    )

class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    subject = Column(String(255), index=True)
    description = Column(Text, nullable=True)
    
    questions = relationship(
        "Question",
        secondary="question_knowledge_links",
        back_populates="knowledge_points"
    )

class QuestionKnowledgeLink(Base):
    __tablename__ = "question_knowledge_links"
    question_id = Column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True) # Changed to String(36)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True)

class AsyncJob(Base):
    __tablename__ = "async_jobs"
    id = Column(String(36), primary_key=True, index=True)  # UUID
    job_type = Column(String(50), nullable=False)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    progress = Column(Integer, default=0)
    message = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)  # JSON 格式的結果
    error_message = Column(Text, nullable=True)
    kwargs_json = Column(Text, nullable=True)  # JSON 格式的參數
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

# === v3.0 安全與權限管理模型 ===

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="viewer")  # admin, viewer
    email = Column(String(100), nullable=True)
    full_name = Column(String(100), nullable=True)  # 完整姓名
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Integer, default=1)  # SQLite 不支援 BOOLEAN，使用 INTEGER
    
    # v3.1 點數系統
    points = Column(Integer, default=100)  # 當前點數
    points_updated_at = Column(DateTime, default=datetime.utcnow)  # 點數最後更新時間
    is_banned = Column(Integer, default=0)  # 是否被禁用（違規上傳）
    ban_until = Column(DateTime, nullable=True)  # 禁用到期時間
    
    # 關聯
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    login_attempts = relationship("LoginAttempt", back_populates="user", cascade="all, delete-orphan")
    uploads = relationship("Document", back_populates="uploader", cascade="all, delete-orphan")
    point_transactions = relationship("PointTransaction", back_populates="user", cascade="all, delete-orphan")

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    username = Column(String(50), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    success = Column(Integer, default=0)  # 0=失敗, 1=成功
    attempt_time = Column(DateTime, default=datetime.utcnow, index=True)
    user_agent = Column(Text, nullable=True)
    
    # 關聯
    user = relationship("User", back_populates="login_attempts")

class IPBlacklist(Base):
    __tablename__ = "ip_blacklist"
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)
    reason = Column(String(255), default="Too many failed login attempts")
    blocked_at = Column(DateTime, default=datetime.utcnow)
    blocked_by = Column(String(50), nullable=True)  # 操作者用戶名
    is_active = Column(Integer, default=1)  # 0=已解除, 1=生效中

class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(String(255), primary_key=True)  # session ID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), nullable=True, index=True)  # 會話 token
    ip_address = Column(String(45), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, nullable=True)  # 最後訪問時間
    is_active = Column(Integer, default=1)  # 0=已失效, 1=活躍中
    user_agent = Column(Text, nullable=True)  # 用戶代理字串
    
    # 關聯
    user = relationship("User", back_populates="sessions")


# v3.1 點數系統相關模型

class PointTransaction(Base):
    """點數交易記錄"""
    __tablename__ = "point_transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(String(50), nullable=False)  # upload, generate_quiz, regenerate_answer, mindmap, etc.
    points_change = Column(Integer, nullable=False)  # 正數=獲得，負數=消耗
    points_before = Column(Integer, nullable=False)
    points_after = Column(Integer, nullable=False)
    description = Column(String(255), nullable=True)
    related_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 關聯
    user = relationship("User", back_populates="point_transactions")
    related_document = relationship("Document")


class ContentValidation(Base):
    """內容驗證記錄"""
    __tablename__ = "content_validations"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_valid_content = Column(Integer, nullable=False)  # 1=合法內容, 0=違規內容
    confidence_score = Column(Float, nullable=True)  # AI 信心分數
    validation_details = Column(Text, nullable=True)  # AI 回傳的詳細說明
    penalty_applied = Column(Integer, default=0)  # 是否已處罰
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 關聯
    document = relationship("Document")
    user = relationship("User")


class InviteCodeAttempt(Base):
    """邀請碼嘗試記錄"""
    __tablename__ = "invite_code_attempts"
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    invite_code = Column(String(255), nullable=False)
    success = Column(Integer, default=0)  # 0=失敗, 1=成功
    attempt_time = Column(DateTime, default=datetime.utcnow, index=True)
    user_agent = Column(Text, nullable=True)
    username_attempted = Column(String(50), nullable=True)  # 嘗試註冊的用戶名


# --- Database Manager ---

class DatabaseManager:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
        self.init_database()

    def init_database(self):
        Base.metadata.create_all(bind=self.engine)

    @contextmanager
    def _session_scope(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def add_document(self, title: str, content: str, subject: str = None, 
                     tags: str = None, file_path: str = None, source: str = None, 
                     key_points_summary: str = None, 
                     quick_quiz: str = None, doc_type: str = "info",
                     uploader_id: int = None, uploader_name: str = None) -> int:
        with self._session_scope() as session:
            new_doc = Document(
                title=title,
                content=content,
                original_content=None, # Deprecated
                subject=subject,
                tags=tags,
                file_path=file_path,
                source=source,
                key_points_summary=key_points_summary,
                quick_quiz=quick_quiz,
                type=doc_type,
                uploader_id=uploader_id,
                uploader_name=uploader_name
            )
            session.add(new_doc)
            session.flush()
            return new_doc.id

    def update_document_content(self, doc_id: int, cleaned_content: str, original_content: str = None):
        """
        更新文件內容，可選擇保存原始內容備份
        
        Args:
            doc_id: 文件ID
            cleaned_content: AI清理後的內容
            original_content: 原始內容（可選，用於備份）
        """
        with self._session_scope() as session:
            document = session.query(Document).filter_by(id=doc_id).first()
            if document:
                # 如果提供了原始內容且文件中還沒有備份，則保存備份
                if original_content and not document.original_content:
                    document.original_content = original_content
                # 更新為清理後的內容
                document.content = cleaned_content
                session.commit()
                return True
            return False

    def insert_question(self, document_id: int, title: str, question_text: str, answer_text: str = None,
                        subject: str = None, answer_sources: str = None,
                        difficulty: str = None, guidance_level: str = None, mindmap_code: str = None) -> str:
        with self._session_scope() as session:
            new_q = Question(
                document_id=document_id,
                title=title,
                question_text=question_text,
                answer_text=answer_text,
                answer_sources=answer_sources,
                subject=subject,
                difficulty=difficulty,
                guidance_level=guidance_level,
                mindmap_code=mindmap_code
            )
            session.add(new_q)
            session.flush()
            return new_q.id

    def get_all_subjects(self) -> List[str]:
        with self._session_scope() as session:
            subjects = session.query(Document.subject).distinct().order_by(Document.subject).all()
            return [s[0] for s in subjects if s[0]]

    def get_all_questions_with_source(self) -> List[Dict[str, Any]]:
        with self._session_scope() as session:
            results = session.query(Question, Document.title).join(Document).order_by(Question.created_at.desc()).all()
            return [
                {
                    "id": q.id, "subject": q.subject, "title": q.title,
                    "question_text": q.question_text, "answer_text": q.answer_text,
                    "difficulty": q.difficulty, "guidance_level": q.guidance_level,
                    "doc_title": doc_title, "created_at": q.created_at
                } for q, doc_title in results
            ]

    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        with self._session_scope() as session:
            result = session.query(Question).options(joinedload(Question.document), joinedload(Question.knowledge_points)).filter(Question.id == question_id).first()
            if not result:
                return None
            
            q = result
            question_data = {
                "id": q.id, "document_id": q.document_id, "title": q.title,
                "question_text": q.question_text, "answer_text": q.answer_text,
                "answer_sources": q.answer_sources, "subject": q.subject,
                "difficulty": q.difficulty, "guidance_level": q.guidance_level,
                "created_at": q.created_at, "mindmap_code": q.mindmap_code,
                "question_summary": q.question_summary, "solving_tips": q.solving_tips,
                "doc_title": q.document.title if q.document else None,
                "knowledge_points": [{"id": kp.id, "name": kp.name, "subject": kp.subject} for kp in q.knowledge_points]
            }
            return question_data

    def get_document_by_id(self, document_id: int) -> Optional[Dict[str, Any]]:
        with self._session_scope() as session:
            doc = session.query(Document).filter(Document.id == document_id).first()
            if not doc:
                return None
            return {c.name: getattr(doc, c.name) for c in doc.__table__.columns}

    def add_or_get_knowledge_point(self, name: str, subject: str, description: str = "") -> int:
        with self._session_scope() as session:
            kp = session.query(KnowledgePoint).filter_by(name=name).first()
            if kp:
                return kp.id
            else:
                new_kp = KnowledgePoint(name=name, subject=subject, description=description)
                session.add(new_kp)
                session.flush()
                return new_kp.id

    def link_question_to_knowledge_point(self, question_id: str, knowledge_point_id: int):
        with self._session_scope() as session:
            link = session.query(QuestionKnowledgeLink).filter_by(
                question_id=question_id, 
                knowledge_point_id=knowledge_point_id
            ).first()
            if not link:
                new_link = QuestionKnowledgeLink(question_id=question_id, knowledge_point_id=knowledge_point_id)
                session.add(new_link)

    def update_question_mindmap(self, question_id: str, mindmap_code: str):
        with self._session_scope() as session:
            session.query(Question).filter(Question.id == question_id).update({"mindmap_code": mindmap_code})

    def update_question_solving_tips(self, question_id: str, summary: str, solving_tips: str):
        """更新題目的摘要與解題技巧"""
        with self._session_scope() as session:
            session.query(Question).filter(Question.id == question_id).update({
                "question_summary": summary,
                "solving_tips": solving_tips
            })

    def update_document_summary_and_quiz(self, document_id: int, summary: str, quiz: str):
        with self._session_scope() as session:
            session.query(Document).filter(Document.id == document_id).update({
                "key_points_summary": summary,
                "quick_quiz": quiz
            })
            
    def get_all_documents(self) -> List[Dict[str, Any]]:
        with self._session_scope() as session:
            docs = session.query(Document).order_by(Document.created_at.desc()).all()
            return [{c.name: getattr(doc, c.name) for c in doc.__table__.columns} for doc in docs]

    def get_questions_by_subject(self, subject: str) -> List[Dict[str, Any]]:
        with self._session_scope() as session:
            results = session.query(Question, Document.title).join(Document).filter(Question.subject == subject).order_by(Question.created_at.desc()).all()
            return [
                {
                    "id": q.id, "subject": q.subject, "title": q.title,
                    "question_text": q.question_text, "answer_text": q.answer_text,
                    "difficulty": q.difficulty, "guidance_level": q.guidance_level,
                    "doc_title": doc_title, "created_at": q.created_at
                } for q, doc_title in results
            ]

    def get_all_knowledge_points_with_stats(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._session_scope() as session:
            kps = session.query(KnowledgePoint).options(joinedload(KnowledgePoint.questions)).all()
            subject_map = {}
            for kp in kps:
                if kp.subject not in subject_map:
                    subject_map[kp.subject] = []
                subject_map[kp.subject].append({
                    "id": kp.id,
                    "name": kp.name,
                    "question_count": len(kp.questions)
                })
            return subject_map
            
    def get_knowledge_point_by_id(self, knowledge_point_id: int) -> Optional[Dict[str, Any]]:
        with self._session_scope() as session:
            kp = session.query(KnowledgePoint).filter(KnowledgePoint.id == knowledge_point_id).first()
            if not kp:
                return None
            return {c.name: getattr(kp, c.name) for c in kp.__table__.columns}

    def get_questions_for_knowledge_point(self, knowledge_point_id: int) -> List[Dict[str, Any]]:
        with self._session_scope() as session:
            kp = session.query(KnowledgePoint).options(joinedload(KnowledgePoint.questions)).filter(KnowledgePoint.id == knowledge_point_id).first()
            if not kp:
                return []
            
            questions = []
            for q in kp.questions:
                questions.append({
                    'id': q.id,
                    'subject': q.subject,
                    'text': q.question_text,
                    'answer_text': q.answer_text,
                    'doc_title': q.document.title,
                    'created_at': q.created_at,
                    'document_id': q.document_id,
                    'doc_id': q.document_id
                })
            return questions

    def get_documents_with_summaries(self) -> List[Dict[str, Any]]:
        with self._session_scope() as session:
            docs = session.query(Document).filter(
                (Document.key_points_summary != None) & (Document.key_points_summary != '') |
                (Document.quick_quiz != None) & (Document.quick_quiz != '')
            ).order_by(Document.created_at.desc()).all()
            
            results = []
            for doc in docs:
                results.append({
                    'id': doc.id,
                    'title': doc.title,
                    'subject': doc.subject or '未分類',
                    'created_at': doc.created_at,
                    'has_summary': bool(doc.key_points_summary),
                    'has_quiz': bool(doc.quick_quiz)
                })
            return results
            
    def get_questions_by_document_id(self, document_id: int) -> List[Dict[str, Any]]:
        with self._session_scope() as session:
            questions = session.query(Question).filter(Question.document_id == document_id).order_by(Question.created_at.desc()).all()
            return [
                {
                    "id": q.id, "subject": q.subject, "title": q.title,
                    "question_text": q.question_text, "answer_text": q.answer_text,
                    "difficulty": q.difficulty, "guidance_level": q.guidance_level,
                    "created_at": q.created_at
                } for q in questions
            ]
    
    def get_all_knowledge_points(self) -> List[Dict[str, Any]]:
        with self._session_scope() as session:
            kps = session.query(KnowledgePoint).order_by(KnowledgePoint.subject, KnowledgePoint.name).all()
            return [{c.name: getattr(kp, c.name) for c in kp.__table__.columns} for kp in kps]

    def clean_orphaned_knowledge_points(self) -> int:
        """清理沒有關聯問題的孤立知識點"""
        with self._session_scope() as session:
            # 查找所有沒有關聯問題的知識點
            orphaned_kps = session.query(KnowledgePoint).filter(
                ~KnowledgePoint.id.in_(
                    session.query(QuestionKnowledgeLink.knowledge_point_id).distinct()
                )
            ).all()
            
            deleted_count = len(orphaned_kps)
            for kp in orphaned_kps:
                session.delete(kp)
            
            return deleted_count

    def delete_question(self, q_id: str):
        with self._session_scope() as session:
            q = session.query(Question).filter(Question.id == q_id).first()
            if q:
                session.delete(q)
                session.flush()  # 確保刪除操作完成
                # 自動清理孤立的知識點
                self.clean_orphaned_knowledge_points()

    def batch_delete_questions(self, question_ids: List[str]):
        with self._session_scope() as session:
            session.query(Question).filter(Question.id.in_(question_ids)).delete(synchronize_session=False)
            session.flush()  # 確保刪除操作完成
            # 自動清理孤立的知識點
            self.clean_orphaned_knowledge_points()

    def delete_document(self, doc_id: int):
        with self._session_scope() as session:
            doc = session.query(Document).filter(Document.id == doc_id).first()
            if doc:
                session.delete(doc)
                session.flush()  # 確保刪除操作完成
                # 自動清理孤立的知識點
                self.clean_orphaned_knowledge_points()

    def edit_question(self, q_id: str, new_subject: str, new_question: str, new_answer: str, 
                     new_mindmap: str = None, new_knowledge_points: List[str] = None):
        with self._session_scope() as session:
            # 更新題目基本資訊
            update_data = {
                "subject": new_subject,
                "question_text": new_question,
                "answer_text": new_answer
            }
            
            # 如果提供了心智圖，則更新
            if new_mindmap is not None:
                update_data["mindmap_code"] = new_mindmap
            
            session.query(Question).filter(Question.id == q_id).update(update_data)
            
            # 如果提供了知識點列表，則更新知識點關聯
            if new_knowledge_points is not None:
                # 先刪除現有的知識點關聯
                session.query(QuestionKnowledgeLink).filter(
                    QuestionKnowledgeLink.question_id == q_id
                ).delete()
                
                # 添加新的知識點關聯
                for kp_name in new_knowledge_points:
                    if kp_name.strip():  # 確保不是空字串
                        # 查找或創建知識點
                        kp = session.query(KnowledgePoint).filter(
                            KnowledgePoint.name == kp_name.strip(),
                            KnowledgePoint.subject == new_subject
                        ).first()
                        
                        if not kp:
                            # 創建新的知識點
                            kp = KnowledgePoint(name=kp_name.strip(), subject=new_subject)
                            session.add(kp)
                            session.flush()  # 確保獲得 ID
                        
                        # 創建關聯
                        link = QuestionKnowledgeLink(
                            question_id=q_id,
                            knowledge_point_id=kp.id
                        )
                        session.add(link)

    # === AsyncJob 相關方法 ===
    
    def create_async_job(self, job_id: str, job_type: str, kwargs_dict: Dict[str, Any]) -> None:
        """創建新的非同步工作記錄"""
        with self._session_scope() as session:
            job = AsyncJob(
                id=job_id,
                job_type=job_type,
                status="pending",
                progress=0,
                message="等待處理中...",
                kwargs_json=json.dumps(kwargs_dict, ensure_ascii=False)
            )
            session.add(job)
    
    def update_async_job_status(self, job_id: str, status: str, progress: int, 
                               message: str, result: Any = None, error: str = None) -> None:
        """更新非同步工作狀態"""
        with self._session_scope() as session:
            job = session.query(AsyncJob).filter(AsyncJob.id == job_id).first()
            if job:
                job.status = status
                job.progress = progress
                job.message = message
                job.updated_at = datetime.utcnow()
                
                if result is not None:
                    job.result_json = json.dumps(result, ensure_ascii=False)
                if error is not None:
                    job.error_message = error
    
    def get_async_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """取得非同步工作狀態"""
        with self._session_scope() as session:
            job = session.query(AsyncJob).filter(AsyncJob.id == job_id).first()
            if job:
                result = {
                    'id': job.id,
                    'type': job.job_type,
                    'status': job.status,
                    'progress': job.progress,
                    'message': job.message,
                    'created_at': job.created_at.isoformat(),
                    'updated_at': job.updated_at.isoformat()
                }
                
                if job.result_json:
                    try:
                        result['result'] = json.loads(job.result_json)
                    except json.JSONDecodeError:
                        result['result'] = None
                
                if job.error_message:
                    result['error'] = job.error_message
                
                if job.kwargs_json:
                    try:
                        result['kwargs'] = json.loads(job.kwargs_json)
                    except json.JSONDecodeError:
                        result['kwargs'] = {}
                
                return result
        return None
    
    def cleanup_old_async_jobs(self, days: int = 7) -> int:
        """清理舊的非同步工作記錄"""
        with self._session_scope() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            deleted_count = session.query(AsyncJob).filter(
                AsyncJob.created_at < cutoff_date
            ).delete()
            return deleted_count

    # === v3.0 安全與權限管理方法 ===
    
    def create_user(self, username: str, password_hash: str, role: str = "viewer", email: str = None) -> int:
        """創建新用戶"""
        with self._session_scope() as session:
            user = User(
                username=username,
                password_hash=password_hash,
                role=role,
                email=email
            )
            session.add(user)
            session.flush()
            return user.id
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根據用戶名獲取用戶資訊"""
        with self._session_scope() as session:
            user = session.query(User).filter(User.username == username, User.is_active == 1).first()
            if user:
                return {
                    'id': user.id,
                    'username': user.username,
                    'password_hash': user.password_hash,
                    'role': user.role,
                    'email': user.email,
                    'created_at': user.created_at.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'is_active': bool(user.is_active)
                }
            return None
    
    def get_user_by_id(self, user_id: int, include_inactive: bool = False) -> Optional[Dict[str, Any]]:
        """根據 ID 獲取用戶資訊"""
        with self._session_scope() as session:
            query = session.query(User).filter(User.id == user_id)
            if not include_inactive:
                query = query.filter(User.is_active == 1)
            user = query.first()
            if user:
                return {
                    'id': user.id,
                    'username': user.username,
                    'role': user.role,
                    'email': user.email,
                    'created_at': user.created_at.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'is_active': bool(user.is_active)
                }
            return None
    
    def update_user_last_login(self, user_id: int) -> None:
        """更新用戶最後登入時間"""
        with self._session_scope() as session:
            session.query(User).filter(User.id == user_id).update({
                'last_login': datetime.utcnow()
            })
    
    def update_user_password(self, user_id: int, new_password_hash: str) -> None:
        """更新用戶密碼"""
        with self._session_scope() as session:
            session.query(User).filter(User.id == user_id).update({
                'password_hash': new_password_hash
            })
    
    def disable_user(self, user_id: int) -> None:
        """停用用戶"""
        with self._session_scope() as session:
            session.query(User).filter(User.id == user_id).update({
                'is_active': 0
            })
    
    def enable_user(self, user_id: int) -> None:
        """啟用用戶"""
        with self._session_scope() as session:
            session.query(User).filter(User.id == user_id).update({
                'is_active': 1
            })
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """獲取所有用戶列表"""
        with self._session_scope() as session:
            users = session.query(User).all()
            return [{
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'email': user.email,
                'created_at': user.created_at.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'is_active': bool(user.is_active)
            } for user in users]
    
    def delete_user(self, user_id: int) -> bool:
        """刪除用戶"""
        with self._session_scope() as session:
            try:
                user = session.query(User).filter(User.id == user_id).first()
                if not user:
                    return False
                
                # MySQL 需要按正確順序刪除，避免外鍵約束問題
                
                # 1. 先刪除相關的會話記錄
                session.query(UserSession).filter(UserSession.user_id == user_id).delete(synchronize_session=False)
                
                # 2. 刪除登入記錄
                session.query(LoginAttempt).filter(LoginAttempt.user_id == user_id).delete(synchronize_session=False)
                
                # 3. 刪除點數交易記錄
                session.query(PointTransaction).filter(PointTransaction.user_id == user_id).delete(synchronize_session=False)
                
                # 4. 刪除內容驗證記錄
                session.query(ContentValidation).filter(ContentValidation.user_id == user_id).delete(synchronize_session=False)
                
                # 5. 對於 Documents 表中的 uploader_id，設為 NULL 而不是刪除文件
                # 因為文件內容可能對系統有價值，只是失去上傳者追蹤
                session.query(Document).filter(Document.uploader_id == user_id).update({
                    'uploader_id': None,
                    'uploader_name': None
                }, synchronize_session=False)
                
                # 6. 最後刪除用戶
                session.delete(user)
                session.flush()  # 確保所有操作在提交前執行
                
                return True
            except Exception as e:
                session.rollback()
                print(f"刪除用戶失敗: {e}")
                raise e
    
    def update_user_info(self, user_id: int, username: str, role: str, email: str = None) -> bool:
        """更新用戶資訊"""
        with self._session_scope() as session:
            result = session.query(User).filter(User.id == user_id).update({
                'username': username,
                'role': role,
                'email': email
            })
            return result > 0
    
    # === 登入記錄管理 ===
    
    def record_login_attempt(self, ip_address: str, username: str = None, user_id: int = None, 
                           success: bool = False, user_agent: str = None) -> None:
        """記錄登入嘗試"""
        with self._session_scope() as session:
            attempt = LoginAttempt(
                ip_address=ip_address,
                username=username,
                user_id=user_id,
                success=1 if success else 0,
                user_agent=user_agent
            )
            session.add(attempt)
    
    def get_failed_attempts_count(self, ip_address: str, time_window_minutes: int = 60) -> int:
        """獲取指定 IP 在時間窗口內的失敗嘗試次數"""
        with self._session_scope() as session:
            cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
            count = session.query(LoginAttempt).filter(
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.success == 0,
                LoginAttempt.attempt_time >= cutoff_time
            ).count()
            return count
    
    def get_login_attempts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """獲取登入記錄"""
        with self._session_scope() as session:
            attempts = session.query(LoginAttempt).order_by(
                LoginAttempt.attempt_time.desc()
            ).limit(limit).all()
            
            return [{
                'id': attempt.id,
                'ip_address': attempt.ip_address,
                'username': attempt.username,
                'success': bool(attempt.success),
                'attempt_time': attempt.attempt_time.isoformat(),
                'user_agent': attempt.user_agent
            } for attempt in attempts]
    
    # === IP 黑名單管理 ===
    
    def add_ip_to_blacklist(self, ip_address: str, reason: str = "Too many failed login attempts", 
                          blocked_by: str = None) -> None:
        """將 IP 加入黑名單"""
        with self._session_scope() as session:
            # 檢查是否已存在
            existing = session.query(IPBlacklist).filter(
                IPBlacklist.ip_address == ip_address
            ).first()
            
            if existing:
                # 更新現有記錄
                existing.reason = reason
                existing.blocked_at = datetime.utcnow()
                existing.blocked_by = blocked_by
                existing.is_active = 1
            else:
                # 創建新記錄
                blacklist_entry = IPBlacklist(
                    ip_address=ip_address,
                    reason=reason,
                    blocked_by=blocked_by
                )
                session.add(blacklist_entry)
    
    def remove_ip_from_blacklist(self, ip_address: str) -> bool:
        """從黑名單移除 IP"""
        with self._session_scope() as session:
            result = session.query(IPBlacklist).filter(
                IPBlacklist.ip_address == ip_address,
                IPBlacklist.is_active == 1
            ).update({'is_active': 0})
            return result > 0
    
    def is_ip_blacklisted(self, ip_address: str) -> bool:
        """檢查 IP 是否在黑名單中"""
        with self._session_scope() as session:
            count = session.query(IPBlacklist).filter(
                IPBlacklist.ip_address == ip_address,
                IPBlacklist.is_active == 1
            ).count()
            return count > 0
    
    def get_blacklisted_ips(self) -> List[Dict[str, Any]]:
        """獲取黑名單 IP 列表"""
        with self._session_scope() as session:
            blacklist = session.query(IPBlacklist).filter(
                IPBlacklist.is_active == 1
            ).order_by(IPBlacklist.blocked_at.desc()).all()
            
            return [{
                'id': entry.id,
                'ip_address': entry.ip_address,
                'reason': entry.reason,
                'blocked_at': entry.blocked_at.isoformat(),
                'blocked_by': entry.blocked_by
            } for entry in blacklist]
    
    # === 用戶會話管理 ===
    
    def create_user_session(self, user_id: int, session_token: str, ip_address: str = None, 
                          user_agent: str = None) -> str:
        """創建用戶會話"""
        from datetime import timedelta
        with self._session_scope() as session:
            # 設定會話過期時間（預設 24 小時）
            expires_at = datetime.utcnow() + timedelta(hours=24)
            
            user_session = UserSession(
                id=session_token,  # 使用 session_token 作為主鍵
                user_id=user_id,
                session_token=session_token,
                ip_address=ip_address or '127.0.0.1',
                expires_at=expires_at,
                user_agent=user_agent,
                is_active=1
            )
            session.add(user_session)
            return session_token
    
    def get_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """根據 token 獲取會話資訊"""
        with self._session_scope() as session:
            user_session = session.query(UserSession).filter(
                UserSession.session_token == session_token,
                UserSession.is_active == 1
            ).first()
            
            if user_session:
                return {
                    'id': user_session.id,
                    'user_id': user_session.user_id,
                    'session_token': user_session.session_token,
                    'ip_address': user_session.ip_address,
                    'created_at': user_session.created_at.isoformat(),
                    'last_accessed': user_session.last_accessed.isoformat() if user_session.last_accessed else None,
                    'user_agent': user_session.user_agent
                }
            return None
    
    def update_session_access(self, session_token: str) -> None:
        """更新會話最後訪問時間"""
        with self._session_scope() as session:
            session.query(UserSession).filter(
                UserSession.session_token == session_token
            ).update({'last_accessed': datetime.utcnow()})
    
    def invalidate_session(self, session_token: str) -> bool:
        """使會話失效"""
        with self._session_scope() as session:
            result = session.query(UserSession).filter(
                UserSession.session_token == session_token
            ).update({'is_active': 0})
            return result > 0
    
    def invalidate_user_sessions(self, user_id: int) -> int:
        """使用戶所有會話失效"""
        with self._session_scope() as session:
            result = session.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.is_active == 1
            ).update({'is_active': 0})
            return result
    
    def cleanup_expired_sessions(self, hours: int = 24) -> int:
        """清理過期會話"""
        with self._session_scope() as session:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            # 清理過期會話：基於 last_accessed 或 created_at（如果 last_accessed 為 NULL）
            result = session.query(UserSession).filter(
                UserSession.is_active == 1
            ).filter(
                # 如果 last_accessed 不為空則使用它，否則使用 created_at
                (UserSession.last_accessed != None) & (UserSession.last_accessed < cutoff_time) |
                (UserSession.last_accessed == None) & (UserSession.created_at < cutoff_time)
            ).update({'is_active': 0})
            return result
    
    def get_active_sessions(self, user_id: int = None) -> List[Dict[str, Any]]:
        """獲取活躍會話列表"""
        with self._session_scope() as session:
            query = session.query(UserSession).filter(UserSession.is_active == 1)
            if user_id:
                query = query.filter(UserSession.user_id == user_id)
            
            sessions = query.order_by(UserSession.created_at.desc()).all()
            
            return [{
                'id': s.id,
                'user_id': s.user_id,
                'ip_address': s.ip_address,
                'created_at': s.created_at.isoformat(),
                'last_accessed': s.last_accessed.isoformat() if s.last_accessed else None,
                'user_agent': s.user_agent
            } for s in sessions]

    # === 邀請碼嘗試管理 ===
    
    def record_invite_code_attempt(self, ip_address: str, invite_code: str, success: bool = False, 
                                 user_agent: str = None, username_attempted: str = None) -> None:
        """記錄邀請碼嘗試"""
        with self._session_scope() as session:
            attempt = InviteCodeAttempt(
                ip_address=ip_address,
                invite_code=invite_code,
                success=1 if success else 0,
                user_agent=user_agent,
                username_attempted=username_attempted
            )
            session.add(attempt)
    
    def get_failed_invite_attempts(self, ip_address: str, time_window_minutes: int = 60) -> int:
        """獲取指定時間窗口內的邀請碼失敗次數"""
        with self._session_scope() as session:
            cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
            
            count = session.query(InviteCodeAttempt).filter(
                InviteCodeAttempt.ip_address == ip_address,
                InviteCodeAttempt.success == 0,
                InviteCodeAttempt.attempt_time >= cutoff_time
            ).count()
            
            return count
    
    def get_invite_code_attempts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """獲取邀請碼嘗試記錄"""
        with self._session_scope() as session:
            attempts = session.query(InviteCodeAttempt).order_by(
                InviteCodeAttempt.attempt_time.desc()
            ).limit(limit).all()
            
            return [{
                'id': attempt.id,
                'ip_address': attempt.ip_address,
                'invite_code': attempt.invite_code[:10] + "..." if len(attempt.invite_code) > 10 else attempt.invite_code,  # 隱藏完整邀請碼
                'success': bool(attempt.success),
                'attempt_time': attempt.attempt_time.isoformat(),
                'user_agent': attempt.user_agent,
                'username_attempted': attempt.username_attempted
            } for attempt in attempts]
