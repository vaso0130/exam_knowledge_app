
import json
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, func
from sqlalchemy.orm import sessionmaker, joinedload, relationship
from sqlalchemy.exc import SQLAlchemyError

# Import shared components from the main application
from ..core.database import (
    Base, engine, User, KnowledgePoint,
    UserNote, NoteCategory, NoteCategoryLink, 
    NoteKnowledgeLink, NoteRelationship, NoteAIAnalysis
)

# === Notes System Database Manager ===

# Use the same session management as the main application
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class NotesDatabaseManager:
    """
    Handles all database operations related to the personal notes system.
    Ensures that all data access is properly isolated by user_id.
    """

    def __init__(self):
        # Ensure notes tables are created
        self.init_notes_tables()

    def init_notes_tables(self):
        """Initialize notes-related tables"""
        Base.metadata.create_all(bind=engine)

    @contextmanager
    def get_db_session(self):
        """Provides a transactional scope around a series of operations."""
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Notes Database Error: {e}")
            raise
        finally:
            session.close()

    # === Note CRUD Operations ===

    def create_note(self, user_id: int, title: str, content: str, **kwargs) -> Optional[str]:
        """Creates a new note for a specific user."""
        with self.get_db_session() as session:
            note = UserNote(
                user_id=user_id,
                title=title,
                content=content,
                content_type=kwargs.get('content_type', 'markdown'),
                tags=json.dumps(kwargs.get('tags', []), ensure_ascii=False),
                ai_summary=kwargs.get('ai_summary'),
                ai_keywords=json.dumps(kwargs.get('ai_keywords', []), ensure_ascii=False),
                is_archived=kwargs.get('is_archived', 0)
            )
            session.add(note)
            session.flush()
            return note.id

    def get_note_by_id(self, user_id: int, note_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single note by its ID, ensuring it belongs to the user."""
        with self.get_db_session() as session:
            note = session.query(UserNote).filter(
                UserNote.id == note_id,
                UserNote.user_id == user_id
            ).first()
            if note:
                return self._note_to_dict(note)
        return None

    def get_note_with_all_relations(self, user_id: int, note_id: str) -> Optional[Dict[str, Any]]:
        """通過一次查詢獲取筆記及其相關信息"""
        with self.get_db_session() as session:
            # 主查詢獲取筆記
            note = session.query(UserNote).filter(
                UserNote.id == note_id,
                UserNote.user_id == user_id
            ).first()
            
            if not note:
                return None
            
            note_data = self._note_to_dict(note)
            
            # ?��??��??�?�相?��???
            try:
                # ?��??��?�?
                knowledge_points = session.query(KnowledgePoint, NoteKnowledgeLink.relevance_score).join(
                    NoteKnowledgeLink, KnowledgePoint.id == NoteKnowledgeLink.knowledge_point_id
                ).filter(NoteKnowledgeLink.note_id == note_id).all()
                
                note_data['related_knowledge_points'] = [{
                    'id': kp.id,
                    'name': kp.name,
                    'subject': kp.subject,
                    'description': kp.description,
                    'relevance_score': score
                } for kp, score in knowledge_points]
                
                # AI ?��?結�?
                ai_analyses = session.query(NoteAIAnalysis).filter(
                    NoteAIAnalysis.note_id == note_id
                ).order_by(NoteAIAnalysis.created_at.desc()).all()
                
                note_data['ai_analyses'] = [{
                    'id': analysis.id,
                    'analysis_type': analysis.analysis_type,
                    'result': json.loads(analysis.result) if analysis.result else {},
                    'created_at': analysis.created_at.isoformat()
                } for analysis in ai_analyses]
                
                # 相關筆記（暫時保持空白，這個查詢比較複雜）
                note_data['related_notes'] = []
                
            except Exception as e:
                print(f"Warning: Failed to load relations for note {note_id}: {e}")
                note_data['related_knowledge_points'] = []
                note_data['related_notes'] = []
                note_data['ai_analyses'] = []
            
            return note_data

    def get_all_notes_for_user(self, user_id: int, include_archived: bool = False) -> List[Dict[str, Any]]:
        """Retrieves all notes for a specific user."""
        with self.get_db_session() as session:
            query = session.query(UserNote).filter(UserNote.user_id == user_id)
            if not include_archived:
                query = query.filter(UserNote.is_archived == 0)
            notes = query.order_by(UserNote.updated_at.desc()).all()
            return [self._note_to_dict(n) for n in notes]

    def update_note(self, user_id: int, note_id: str, **updates) -> bool:
        """Updates a note's content and other attributes."""
        with self.get_db_session() as session:
            note = session.query(UserNote).filter(
                UserNote.id == note_id,
                UserNote.user_id == user_id
            ).first()

            if not note:
                return False

            for key, value in updates.items():
                if hasattr(note, key):
                    # Handle JSON fields
                    if key in ['tags', 'ai_keywords'] and isinstance(value, (list, dict)):
                        setattr(note, key, json.dumps(value, ensure_ascii=False))
                    else:
                        setattr(note, key, value)
            
            note.updated_at = datetime.utcnow()
            session.flush()
            return True

    def delete_note(self, user_id: int, note_id: str) -> bool:
        """Deletes a note, ensuring it belongs to the user."""
        with self.get_db_session() as session:
            note = session.query(UserNote).filter(
                UserNote.id == note_id,
                UserNote.user_id == user_id
            ).first()
            if note:
                session.delete(note)
                session.flush()
                return True
            return False

    # === Category Management ===

    def create_category(self, user_id: int, name: str, **kwargs) -> Optional[int]:
        """Creates a new category for a user."""
        with self.get_db_session() as session:
            category = NoteCategory(
                user_id=user_id,
                name=name,
                description=kwargs.get('description'),
                color=kwargs.get('color'),
                icon=kwargs.get('icon'),
                parent_id=kwargs.get('parent_id')
            )
            session.add(category)
            session.flush()
            return category.id

    def get_all_categories_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        """Retrieves all categories for a specific user."""
        with self.get_db_session() as session:
            categories = session.query(NoteCategory).filter(
                NoteCategory.user_id == user_id
            ).order_by(NoteCategory.name).all()
            return [self._category_to_dict(c) for c in categories]

    def link_note_to_category(self, user_id: int, note_id: str, category_id: int) -> bool:
        """Associates a note with a category, verifying ownership."""
        with self.get_db_session() as session:
            # Verify user owns both the note and the category
            note_exists = session.query(UserNote.id).filter_by(id=note_id, user_id=user_id).first()
            category_exists = session.query(NoteCategory.id).filter_by(id=category_id, user_id=user_id).first()

            if note_exists and category_exists:
                link = NoteCategoryLink(note_id=note_id, category_id=category_id)
                session.merge(link)  # Use merge to avoid duplicates
                return True
            return False

    # === Knowledge Point Integration ===

    def link_note_to_knowledge_point(self, user_id: int, note_id: str, knowledge_point_id: int, relevance_score: float = 0.8) -> bool:
        """Links a note to a knowledge point with relevance score."""
        with self.get_db_session() as session:
            # Verify user owns the note
            note_exists = session.query(UserNote.id).filter_by(id=note_id, user_id=user_id).first()
            # Verify knowledge point exists
            kp_exists = session.query(KnowledgePoint.id).filter_by(id=knowledge_point_id).first()

            if note_exists and kp_exists:
                link = NoteKnowledgeLink(
                    note_id=note_id, 
                    knowledge_point_id=knowledge_point_id,
                    relevance_score=relevance_score
                )
                session.merge(link)
                return True
            return False

    def get_related_knowledge_points(self, user_id: int, note_id: str) -> List[Dict[str, Any]]:
        """Get knowledge points related to a specific note."""
        with self.get_db_session() as session:
            results = session.query(KnowledgePoint, NoteKnowledgeLink.relevance_score).join(
                NoteKnowledgeLink, KnowledgePoint.id == NoteKnowledgeLink.knowledge_point_id
            ).join(
                UserNote, NoteKnowledgeLink.note_id == UserNote.id
            ).filter(
                UserNote.id == note_id,
                UserNote.user_id == user_id
            ).all()

            return [{
                'id': kp.id,
                'name': kp.name,
                'subject': kp.subject,
                'description': kp.description,
                'relevance_score': score
            } for kp, score in results]

    # === AI Analysis Storage ===

    def save_ai_analysis(self, user_id: int, note_id: str, analysis_type: str, result: dict) -> Optional[int]:
        """Save AI analysis result for a note."""
        with self.get_db_session() as session:
            # Verify user owns the note
            note_exists = session.query(UserNote.id).filter_by(id=note_id, user_id=user_id).first()
            
            if note_exists:
                analysis = NoteAIAnalysis(
                    note_id=note_id,
                    analysis_type=analysis_type,
                    result=json.dumps(result, ensure_ascii=False)
                )
                session.add(analysis)
                session.flush()
                return analysis.id
            return None

    def update_ai_analysis(self, user_id: int, note_id: str, analysis_id: int, result: dict) -> bool:
        """Update an existing AI analysis result."""
        with self.get_db_session() as session:
            # Verify user owns the note and analysis
            analysis = session.query(NoteAIAnalysis).join(
                UserNote, NoteAIAnalysis.note_id == UserNote.id
            ).filter(
                NoteAIAnalysis.id == analysis_id,
                UserNote.id == note_id,
                UserNote.user_id == user_id
            ).first()
            
            if analysis:
                analysis.result = json.dumps(result, ensure_ascii=False)
                analysis.created_at = datetime.utcnow()  # Update timestamp
                session.flush()
                return True
            return False

    def delete_ai_analysis(self, user_id: int, note_id: str, analysis_id: int) -> bool:
        """Delete an AI analysis result."""
        with self.get_db_session() as session:
            # Verify user owns the note and analysis
            analysis = session.query(NoteAIAnalysis).join(
                UserNote, NoteAIAnalysis.note_id == UserNote.id
            ).filter(
                NoteAIAnalysis.id == analysis_id,
                UserNote.id == note_id,
                UserNote.user_id == user_id
            ).first()
            
            if analysis:
                session.delete(analysis)
                session.flush()
                return True
            return False

    def get_ai_analysis_by_id(self, user_id: int, note_id: str, analysis_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific AI analysis result by ID."""
        with self.get_db_session() as session:
            analysis = session.query(NoteAIAnalysis).join(
                UserNote, NoteAIAnalysis.note_id == UserNote.id
            ).filter(
                NoteAIAnalysis.id == analysis_id,
                UserNote.id == note_id,
                UserNote.user_id == user_id
            ).first()
            
            if analysis:
                return {
                    'id': analysis.id,
                    'analysis_type': analysis.analysis_type,
                    'result': json.loads(analysis.result) if analysis.result else {},
                    'created_at': analysis.created_at.isoformat()
                }
            return None

    def get_ai_analysis_by_type(self, user_id: int, note_id: str, analysis_type: str) -> List[Dict[str, Any]]:
        """Get all AI analysis results of a specific type for a note."""
        with self.get_db_session() as session:
            analyses = session.query(NoteAIAnalysis).join(
                UserNote, NoteAIAnalysis.note_id == UserNote.id
            ).filter(
                UserNote.id == note_id,
                UserNote.user_id == user_id,
                NoteAIAnalysis.analysis_type == analysis_type
            ).order_by(NoteAIAnalysis.created_at.desc()).all()
            
            return [{
                'id': analysis.id,
                'analysis_type': analysis.analysis_type,
                'result': json.loads(analysis.result) if analysis.result else {},
                'created_at': analysis.created_at.isoformat()
            } for analysis in analyses]

    def count_ai_analyses(self, user_id: int, note_id: str) -> Dict[str, int]:
        """Count AI analyses by type for a note."""
        with self.get_db_session() as session:
            result = session.query(
                NoteAIAnalysis.analysis_type,
                func.count(NoteAIAnalysis.id).label('count')
            ).join(
                UserNote, NoteAIAnalysis.note_id == UserNote.id
            ).filter(
                UserNote.id == note_id,
                UserNote.user_id == user_id
            ).group_by(NoteAIAnalysis.analysis_type).all()
            
            return {analysis_type: count for analysis_type, count in result}

    def get_ai_analysis(self, user_id: int, note_id: str, analysis_type: str = None) -> List[Dict[str, Any]]:
        """Get AI analysis results for a note."""
        with self.get_db_session() as session:
            query = session.query(NoteAIAnalysis).join(
                UserNote, NoteAIAnalysis.note_id == UserNote.id
            ).filter(
                UserNote.id == note_id,
                UserNote.user_id == user_id
            )
            
            if analysis_type:
                query = query.filter(NoteAIAnalysis.analysis_type == analysis_type)
            
            # 確�?一?��??��?：�??��??��?類�?，然後�??�建?��??��?
            analyses = query.order_by(
                NoteAIAnalysis.analysis_type,
                NoteAIAnalysis.created_at.desc()
            ).all()
            
            results = []
            for analysis in analyses:
                try:
                    # 安全?�解?�JSON結�?
                    result_data = {}
                    if analysis.result:
                        result_data = json.loads(analysis.result)
                        
                    # 驗�?結�??��??��??��?
                    if isinstance(result_data, dict):
                        # 確�??�organized_content欄�?
                        if not result_data.get('organized_content'):
                            # ?�試從其他�?位�???
                            for field in ['formatted_content', 'content', 'summary', 'text']:
                                if result_data.get(field):
                                    result_data['organized_content'] = result_data[field]
                                    break
                            else:
                                result_data['organized_content'] = '無結構化資料'
                    
                    results.append({
                        'id': analysis.id,
                        'analysis_type': analysis.analysis_type,
                        'result': result_data,
                        'created_at': analysis.created_at.isoformat()
                    })
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing analysis result for ID {analysis.id}: {e}")
                    # 添�??�誤記�?但�?中斷?��?
                    results.append({
                        'id': analysis.id,
                        'analysis_type': analysis.analysis_type,
                        'result': {'error': f'資�?�???�誤: {str(e)}', 'organized_content': '資�?�??失�?'},
                        'created_at': analysis.created_at.isoformat()
                    })
            
            return results

    # === Note Relationships ===

    def create_note_relationship(self, user_id: int, source_note_id: str, target_note_id: str, 
                                relationship_type: str = 'related') -> bool:
        """Create a relationship between two notes."""
        with self.get_db_session() as session:
            # Verify user owns both notes
            source_exists = session.query(UserNote.id).filter_by(id=source_note_id, user_id=user_id).first()
            target_exists = session.query(UserNote.id).filter_by(id=target_note_id, user_id=user_id).first()

            if source_exists and target_exists:
                relationship = NoteRelationship(
                    source_note_id=source_note_id,
                    target_note_id=target_note_id,
                    relationship_type=relationship_type
                )
                session.add(relationship)
                session.flush()
                return True
            return False

    def get_related_notes(self, user_id: int, note_id: str) -> List[Dict[str, Any]]:
        """Get notes related to a specific note."""
        with self.get_db_session() as session:
            # Get relationships where this note is the source
            outgoing = session.query(UserNote, NoteRelationship.relationship_type).join(
                NoteRelationship, UserNote.id == NoteRelationship.target_note_id
            ).filter(
                NoteRelationship.source_note_id == note_id,
                UserNote.user_id == user_id
            ).all()

            # Get relationships where this note is the target
            incoming = session.query(UserNote, NoteRelationship.relationship_type).join(
                NoteRelationship, UserNote.id == NoteRelationship.source_note_id
            ).filter(
                NoteRelationship.target_note_id == note_id,
                UserNote.user_id == user_id
            ).all()

            related_notes = []
            for note, rel_type in outgoing + incoming:
                note_dict = self._note_to_dict(note)
                note_dict['relationship_type'] = rel_type
                related_notes.append(note_dict)

            return related_notes

    # === Search and Filter ===

    def search_notes(self, user_id: int, query: str, tags: List[str] = None, 
                    category_id: int = None) -> List[Dict[str, Any]]:
        """Search notes by content, title, tags, or category."""
        with self.get_db_session() as session:
            db_query = session.query(UserNote).filter(UserNote.user_id == user_id)

            # Text search in title and content
            if query:
                search_pattern = f"%{query}%"
                db_query = db_query.filter(
                    (UserNote.title.like(search_pattern)) |
                    (UserNote.content.like(search_pattern))
                )

            # Tag filter
            if tags:
                for tag in tags:
                    tag_pattern = f'%"{tag}"%'
                    db_query = db_query.filter(UserNote.tags.like(tag_pattern))

            # Category filter
            if category_id:
                db_query = db_query.join(NoteCategoryLink).filter(
                    NoteCategoryLink.category_id == category_id
                )

            notes = db_query.order_by(UserNote.updated_at.desc()).all()
            return [self._note_to_dict(n) for n in notes]

    # === Helper Methods ===

    def _note_to_dict(self, note: UserNote) -> Dict[str, Any]:
        """Converts a UserNote object to a dictionary."""
        return {
            "id": note.id,
            "user_id": note.user_id,
            "title": note.title,
            "content": note.content,
            "content_type": note.content_type,
            "tags": json.loads(note.tags) if note.tags else [],
            "ai_summary": note.ai_summary,
            "ai_keywords": json.loads(note.ai_keywords) if note.ai_keywords else [],
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
            "is_archived": bool(note.is_archived)
        }

    def _category_to_dict(self, category: NoteCategory) -> Dict[str, Any]:
        """Converts a NoteCategory object to a dictionary."""
        return {
            "id": category.id,
            "user_id": category.user_id,
            "name": category.name,
            "description": category.description,
            "color": category.color,
            "icon": category.icon,
            "parent_id": category.parent_id,
            "created_at": category.created_at.isoformat()
        }

