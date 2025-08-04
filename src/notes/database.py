
import json
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy.exc import SQLAlchemyError

# Import core components from the main application
from ..core.database import (
    Base,
    engine,
    User,
    KnowledgePoint,
    UserNote,
    NoteCategory,
    NoteCategoryLink,
    NoteKnowledgeLink,
    NoteRelationship,
    NoteAIAnalysis,
)

# Use the same session management as the main application
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db_session():
    """Provides a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        # In a real app, you'd want to log this error
        print(f"Database Error: {e}")
        raise
    finally:
        session.close()

class NotesDatabaseManager:
    """
    Handles all database operations related to the personal notes system.
    Ensures that all data access is properly isolated by user_id.
    """

    # === Note CRUD Operations ===

    def create_note(self, user_id: int, title: str, content: str, **kwargs) -> Optional[int]:
        """Creates a new note for a specific user."""
        with get_db_session() as session:
            note = UserNote(
                user_id=user_id,
                title=title,
                content=content,
                content_type=kwargs.get('content_type', 'markdown'),
                tags=json.dumps(kwargs.get('tags', [])),
                ai_summary=kwargs.get('ai_summary'),
                ai_keywords=json.dumps(kwargs.get('ai_keywords', [])),
                is_archived=kwargs.get('is_archived', 0)
            )
            session.add(note)
            session.flush()
            return note.id

    def get_note_by_id(self, user_id: int, note_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a single note by its ID, ensuring it belongs to the user."""
        with get_db_session() as session:
            note = session.query(UserNote).filter(
                UserNote.id == note_id,
                UserNote.user_id == user_id
            ).first()
            if note:
                return self._note_to_dict(note)
        return None

    def get_all_notes_for_user(self, user_id: int, include_archived: bool = False) -> List[Dict[str, Any]]:
        """Retrieves all notes for a specific user."""
        with get_db_session() as session:
            query = session.query(UserNote).filter(UserNote.user_id == user_id)
            if not include_archived:
                query = query.filter(UserNote.is_archived == 0)
            notes = query.order_by(UserNote.updated_at.desc()).all()
            return [self._note_to_dict(n) for n in notes]

    def update_note(self, user_id: int, note_id: int, **updates) -> bool:
        """Updates a note's content and other attributes."""
        with get_db_session() as session:
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

    def delete_note(self, user_id: int, note_id: int) -> bool:
        """Deletes a note, ensuring it belongs to the user."""
        with get_db_session() as session:
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
        with get_db_session() as session:
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
        with get_db_session() as session:
            categories = session.query(NoteCategory).filter(
                NoteCategory.user_id == user_id
            ).order_by(NoteCategory.name).all()
            return [self._category_to_dict(c) for c in categories]

    def link_note_to_category(self, user_id: int, note_id: int, category_id: int) -> bool:
        """Associates a note with a category, verifying ownership."""
        with get_db_session() as session:
            # Verify user owns both the note and the category
            note_exists = session.query(UserNote.id).filter_by(id=note_id, user_id=user_id).first()
            category_exists = session.query(NoteCategory.id).filter_by(id=category_id, user_id=user_id).first()

            if note_exists and category_exists:
                link = NoteCategoryLink(note_id=note_id, category_id=category_id)
                session.merge(link) # Use merge to avoid duplicates
                return True
            return False

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

# This function can be used to initialize the tables if needed,
# but the main app's DatabaseManager.init_database() already handles it.
def initialize_notes_tables():
    """Ensures that all tables related to the notes system are created."""
    Base.metadata.create_all(bind=engine)

