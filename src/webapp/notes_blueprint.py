from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..notes.note_manager import NoteManager
from ..webapp.auth_middleware import require_admin

# Define the blueprint for the notes system
notes_bp = Blueprint(
    'notes',
    __name__,
    template_folder='templates',
    static_folder='static'
)

# Instantiate the manager that handles business logic
note_manager = NoteManager()

@notes_bp.before_request
@require_admin
def before_request():
    """
    Protects all routes in this blueprint.
    Ensures the user is logged in and is an admin.
    """
    # The @require_admin decorator handles all the logic.
    # This function is now just a placeholder for the decorator.
    pass

@notes_bp.route('/')
def note_list():
    """Displays the list of all notes for the current user."""
    user_id = g.current_user['id']
    notes = note_manager.get_user_notes_list(user_id)
    return render_template('notes/note_list.html', notes=notes, title="我的筆記")

@notes_bp.route('/new', methods=['GET', 'POST'])
def create_note():
    """Handles the creation of a new note."""
    if request.method == 'POST':
        user_id = g.current_user['id']
        title = request.form.get('title')
        content = request.form.get('content')

        if not title or not content:
            flash("標題和內容不能為空。", "danger")
            return render_template('notes/note_edit.html', title="新增筆記")

        note_id = note_manager.create_new_note(user_id, title, content)
        if note_id:
            flash("筆記已成功建立！", "success")
            return redirect(url_for('.note_detail', note_id=note_id))
        else:
            flash("建立筆記時發生錯誤。", "danger")

    return render_template('notes/note_edit.html', title="新增筆記", note=None)

@notes_bp.route('/<int:note_id>')
def note_detail(note_id):
    """Displays the details of a single note."""
    user_id = g.current_user['id']
    note = note_manager.get_note_details(user_id, note_id)
    if not note:
        flash("找不到指定的筆記。", "danger")
        return redirect(url_for('.note_list'))
    
    # Example of getting suggestions (can be expanded)
    suggestions = note_manager.get_note_suggestions(user_id, note_id)
    
    return render_template('notes/note_detail.html', note=note, suggestions=suggestions, title=note['title'])

@notes_bp.route('/<int:note_id>/edit', methods=['GET', 'POST'])
def edit_note(note_id):
    """Handles the editing of an existing note."""
    user_id = g.current_user['id']
    
    if request.method == 'POST':
        updates = {
            'title': request.form.get('title'),
            'content': request.form.get('content')
        }
        if not updates['title'] or not updates['content']:
            flash("標題和內容不能為空。", "danger")
        elif note_manager.update_existing_note(user_id, note_id, **updates):
            flash("筆記已更新。", "success")
            return redirect(url_for('.note_detail', note_id=note_id))
        else:
            flash("更新筆記失敗。", "danger")
    
    note = note_manager.get_note_details(user_id, note_id)
    if not note:
        flash("找不到要編輯的筆記。", "danger")
        return redirect(url_for('.note_list'))
        
    return render_template('notes/note_edit.html', note=note, title="編輯筆記")

@notes_bp.route('/<int:note_id>/delete', methods=['POST'])
def delete_note(note_id):
    """Handles the deletion of a note."""
    user_id = g.current_user['id']
    if note_manager.delete_note_by_id(user_id, note_id):
        flash("筆記已刪除。", "success")
    else:
        flash("刪除筆記失敗。", "danger")
    return redirect(url_for('.note_list'))

# Placeholder for category management page
@notes_bp.route('/categories')
def category_management():
    """Displays the category management interface."""
    user_id = g.current_user['id']
    categories = note_manager.get_user_categories(user_id)
    return render_template('notes/category_management.html', categories=categories, title="分類管理")
