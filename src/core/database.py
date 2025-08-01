
import os
import json
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
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
    questions = relationship("Question", back_populates="document", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    title = Column(String(512))
    question_text = Column(Text)
    answer_text = Column(Text, nullable=True)
    answer_sources = Column(Text, nullable=True)
    subject = Column(String(255), index=True)
    difficulty = Column(String(50), nullable=True)
    guidance_level = Column(String(50), nullable=True)
    mindmap_code = Column(Text, nullable=True)
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
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id", ondelete="CASCADE"), primary_key=True)


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
                     quick_quiz: str = None, doc_type: str = "info") -> int:
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
                type=doc_type
            )
            session.add(new_doc)
            session.flush()
            return new_doc.id

    def insert_question(self, document_id: int, title: str, question_text: str, answer_text: str = None,
                        subject: str = None, answer_sources: str = None,
                        difficulty: str = None, guidance_level: str = None, mindmap_code: str = None) -> int:
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

    def get_question_by_id(self, question_id: int) -> Optional[Dict[str, Any]]:
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

    def link_question_to_knowledge_point(self, question_id: int, knowledge_point_id: int):
        with self._session_scope() as session:
            link = session.query(QuestionKnowledgeLink).filter_by(
                question_id=question_id, 
                knowledge_point_id=knowledge_point_id
            ).first()
            if not link:
                new_link = QuestionKnowledgeLink(question_id=question_id, knowledge_point_id=knowledge_point_id)
                session.add(new_link)

    def update_question_mindmap(self, question_id: int, mindmap_code: str):
        with self._session_scope() as session:
            session.query(Question).filter(Question.id == question_id).update({"mindmap_code": mindmap_code})

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
            kps = session.query(KnowledgePoint).options(relationship("questions")).all()
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
            kp = session.query(KnowledgePoint).options(relationship('questions')).filter(KnowledgePoint.id == knowledge_point_id).first()
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

    def delete_question(self, q_id: int):
        with self._session_scope() as session:
            q = session.query(Question).filter(Question.id == q_id).first()
            if q:
                session.delete(q)

    def batch_delete_questions(self, question_ids: List[int]):
        with self._session_scope() as session:
            session.query(Question).filter(Question.id.in_(question_ids)).delete(synchronize_session=False)

    def edit_question(self, q_id: int, new_subject: str, new_question: str, new_answer: str):
        with self._session_scope() as session:
            session.query(Question).filter(Question.id == q_id).update({
                "subject": new_subject,
                "question_text": new_question,
                "answer_text": new_answer
            })
