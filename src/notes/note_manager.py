
import json
from .database import NotesDatabaseManager
from .ai_client import NoteAIClient
from typing import List, Dict, Any, Optional

class NoteManager:
    """
    Core logic for managing notes. It acts as a bridge between the web layer (blueprint)
    and the data/AI layers (database, ai_client).
    """
    def __init__(self):
        self.db_manager = NotesDatabaseManager()
        self.ai_client = NoteAIClient()

    def create_new_note(self, user_id: int, title: str, content: str, **kwargs) -> Optional[int]:
        """
        Creates a new note, performs initial AI analysis, and saves it.
        """
        # Perform AI analysis first to enrich the note data
        analysis_results = self.ai_client.analyze_note_content(content)

        # Prepare data for database insertion
        note_data = {
            'title': title,
            'content': content,
            'content_type': kwargs.get('content_type', 'markdown'),
            'tags': analysis_results.get('suggested_tags', []) + kwargs.get('custom_tags', []),
            'ai_summary': analysis_results.get('summary'),
            'ai_keywords': analysis_results.get('keywords', []),
        }

        # Create the note in the database
        note_id = self.db_manager.create_note(user_id, **note_data)
        return note_id

    def get_note_details(self, user_id: int, note_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single note and its details for a user.
        """
        return self.db_manager.get_note_by_id(user_id, note_id)

    def get_user_notes_list(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves a list of all notes for a user.
        """
        return self.db_manager.get_all_notes_for_user(user_id)

    def update_existing_note(self, user_id: int, note_id: int, **updates) -> bool:
        """
        Updates an existing note. If content is updated, it can re-run AI analysis.
        """
        if 'content' in updates:
            # If the main content changes, re-run the analysis
            analysis_results = self.ai_client.analyze_note_content(updates['content'])
            updates['ai_summary'] = analysis_results.get('summary')
            updates['ai_keywords'] = analysis_results.get('keywords', [])
            # Potentially merge new suggested tags with existing ones
            # For simplicity, we'll just use the new ones here.
            updates['tags'] = analysis_results.get('suggested_tags', [])

        return self.db_manager.update_note(user_id, note_id, **updates)

    def delete_note_by_id(self, user_id: int, note_id: int) -> bool:
        """
        Deletes a note for a user.
        """
        return self.db_manager.delete_note(user_id, note_id)

    def get_note_suggestions(self, user_id: int, note_id: int) -> Dict[str, List]:
        """
        Generates suggestions for related content based on a note.
        """
        note = self.db_manager.get_note_by_id(user_id, note_id)
        if not note:
            return {}

        # In a real app, you would fetch these from the database
        # For now, we'll use placeholders.
        all_other_note_titles = [n['title'] for n in self.db_manager.get_all_notes_for_user(user_id) if n['id'] != note_id]
        # This should come from the main app's database manager
        all_knowledge_points = ["Example Knowledge Point 1", "Example Knowledge Point 2"]

        return self.ai_client.suggest_related_content(
            note_content=note['content'],
            existing_notes=all_other_note_titles,
            all_knowledge_points=all_knowledge_points
        )

    # Category management can also be routed through here if needed
    def create_category_for_user(self, user_id: int, name: str, **kwargs) -> Optional[int]:
        return self.db_manager.create_category(user_id, name, **kwargs)

    def get_user_categories(self, user_id: int) -> List[Dict[str, Any]]:
        return self.db_manager.get_all_categories_for_user(user_id)

    def add_note_to_category(self, user_id: int, note_id: int, category_id: int) -> bool:
        return self.db_manager.link_note_to_category(user_id, note_id, category_id)

