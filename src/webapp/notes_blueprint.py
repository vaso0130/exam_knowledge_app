from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from ..notes.note_manager import NoteManager
from ..webapp.auth_middleware import require_admin
from ..core.database import DatabaseManager


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
        
        # AI 功能選項
        enable_ai_analysis = request.form.get('enable_ai_analysis') == 'on'
        enable_ai_organization = request.form.get('enable_ai_organization') == 'on'
        organization_types = request.form.getlist('organization_types')

        if not title or not content:
            flash("標題和內容不能為空。", "danger")
            return render_template('notes/note_edit.html', title="新增筆記")

        # 建立筆記（包含 AI 分析選項）
        note_id = note_manager.create_new_note(
            user_id, 
            title, 
            content, 
            enable_ai_analysis=enable_ai_analysis
        )
        
        if note_id:
            # 如果選擇了 AI 整理功能，則異步生成整理結果
            if enable_ai_organization and organization_types:
                # 啟動背景任務來生成 AI 整理結果
                from threading import Thread
                import time
                
                def generate_organizations():
                    """背景生成AI整理結果"""
                    success_count = 0
                    error_count = 0
                    
                    print(f"開始為筆記 {note_id} 生成 {len(organization_types)} 種整理方式...")
                    
                    for i, org_type in enumerate(organization_types):
                        try:
                            print(f"生成 {org_type} ({i+1}/{len(organization_types)})...")
                            result = note_manager.organize_note_with_ai(user_id, note_id, org_type)
                            
                            if result.get('success'):
                                success_count += 1
                                print(f"✅ {org_type} 生成成功")
                            else:
                                error_count += 1
                                print(f"❌ {org_type} 生成失敗: {result.get('error', '未知錯誤')}")
                                
                            # 在每個整理類型之間稍作延遲，避免API限制
                            if i < len(organization_types) - 1:
                                time.sleep(2)
                                
                        except Exception as e:
                            error_count += 1
                            print(f"❌ 生成 {org_type} 時發生異常: {e}")
                    
                    print(f"背景任務完成！成功: {success_count}, 失敗: {error_count}")
                
                # 在背景執行 AI 整理
                thread = Thread(target=generate_organizations)
                thread.daemon = True
                thread.start()
                
                if enable_ai_analysis and organization_types:
                    flash(f"筆記已成功建立！AI 智慧助理已啟用，{len(organization_types)} 種整理方式正在背景生成中...", "success")
                else:
                    flash(f"筆記已成功建立！{len(organization_types)} 種整理方式正在背景生成中...", "success")
            else:
                if enable_ai_analysis:
                    flash("筆記已成功建立！AI 智慧助理已啟用。", "success")
                else:
                    flash("筆記已成功建立！", "success")
            
            return redirect(url_for('.note_detail', note_id=note_id))
        else:
            flash("建立筆記時發生錯誤。", "danger")

    return render_template('notes/note_edit.html', title="新增筆記", note=None)


@notes_bp.route('/from-question/<string:question_id>', methods=['GET', 'POST'])
def create_note_from_question(question_id):
    """Create a note referencing a question."""
    user_id = g.current_user['id']
    main_db = DatabaseManager()
    question = main_db.get_question_by_id(question_id)
    if not question:
        flash("找不到指定的題目。", "danger")
        return redirect(url_for('main.questions'))

    if request.method == 'POST':
        action = request.form.get('action')
        
        # 處理智能AI生成請求 (AJAX)
        if action == 'smart_ai_generate':
            try:
                ai_prompt = request.form.get('ai_prompt', '')
                current_content = request.form.get('current_content', '')
                title = request.form.get('title', '')
                
                # 準備生成筆記的資料
                generation_context = {
                    'question_text': question.get('question_text', ''),
                    'answer_text': question.get('answer_text', ''),
                    'user_content': current_content,
                    'user_prompt': ai_prompt,
                    'title': title
                }
                
                # 呼叫智能筆記生成方法
                generated_content = note_manager.generate_smart_note_content(
                    user_id=user_id,
                    context=generation_context
                )
                
                return jsonify({
                    'success': True,
                    'generated_content': generated_content
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # 處理一般的保存和智能AI生成
        else:
            title = request.form.get('title')
            content = request.form.get('content')
            smart_ai_mode = request.form.get('smart_ai_mode') == 'on'

            enable_ai_analysis = request.form.get('enable_ai_analysis') == 'on'
            enable_ai_organization = request.form.get('enable_ai_organization') == 'on'
            organization_types = request.form.getlist('organization_types')

            # 如果啟用智能AI模式且內容為空，則不要求必填
            if not title or (not content and not smart_ai_mode):
                flash("標題和內容不能為空。", "danger")
            else:
                # 如果內容為空但啟用了智能AI模式，先生成內容
                if not content and smart_ai_mode:
                    try:
                        ai_prompt = request.form.get('ai_prompt', '')
                        generation_context = {
                            'question_text': question.get('question_text', ''),
                            'answer_text': question.get('answer_text', ''),
                            'user_content': '',
                            'user_prompt': ai_prompt,
                            'title': title
                        }
                        content = note_manager.generate_smart_note_content(user_id=user_id, context=generation_context)
                    except Exception as e:
                        flash(f"AI生成內容失敗：{str(e)}", "danger")
                        return render_template(
                            'notes/note_edit.html',
                            title="新增筆記",
                            note=None,
                            default_title=default_title,
                            default_content=request.form.get('content', ''),
                            source_question=question
                        )
                
                note_id = note_manager.create_new_note(
                    user_id,
                    title,
                    content,
                    enable_ai_analysis=enable_ai_analysis
                )
                if note_id:
                    note_manager.db_manager.save_ai_analysis(user_id, note_id, 'source_question', {
                        'id': question['id'],
                        'question_text': question.get('question_text', ''),
                        'answer_text': question.get('answer_text', '')
                    })

                    if enable_ai_organization and organization_types:
                        from threading import Thread

                        def generate_organizations():
                            for org_type in organization_types:
                                try:
                                    note_manager.organize_note_with_ai(user_id, note_id, org_type)
                                except Exception as e:
                                    print(f"Warning: Failed to generate {org_type} organization: {e}")

                        thread = Thread(target=generate_organizations)
                        thread.daemon = True
                        thread.start()

                        if enable_ai_analysis and organization_types:
                            flash(
                                f"筆記已成功建立！AI 智慧助理已啟用，{len(organization_types)} 種整理方式正在背景生成中...",
                                "success"
                            )
                        else:
                            flash(
                                f"筆記已成功建立！{len(organization_types)} 種整理方式正在背景生成中...",
                                "success"
                            )
                    else:
                        if enable_ai_analysis:
                            flash("筆記已成功建立！AI 智慧助理已啟用。", "success")
                        else:
                            flash("筆記已成功建立！", "success")

                    return redirect(url_for('.note_detail', note_id=note_id))
                else:
                    flash("建立筆記時發生錯誤。", "danger")

        default_title = f"筆記：{question.get('question_text', '')[:30]}" + ("..." if len(question.get('question_text', '')) > 30 else "")
        return render_template(
            'notes/note_edit.html',
            title="新增筆記",
            note=None,
            default_title=default_title,
            default_content=request.form.get('content', ''),
            source_question=question
        )

    default_title = f"筆記：{question.get('question_text', '')[:30]}" + ("..." if len(question.get('question_text', '')) > 30 else "")
    return render_template(
        'notes/note_edit.html',
        title="新增筆記",
        note=None,
        default_title=default_title,
        default_content='',
        source_question=question
    )

@notes_bp.route('/<string:note_id>')
def note_detail(note_id):
    """Displays the details of a specific note."""
    user_id = g.current_user['id']
    
    # 使用新的智慧快取機制
    note = note_manager.get_note_details(user_id, note_id)
    
    if not note:
        flash("找不到指定的筆記。", "danger")
        return redirect(url_for('.note_list'))
    
    # 獲取可用的 AI 整理方式
    organization_types = note_manager.get_available_organization_types()
    
    return render_template('notes/note_detail.html', note=note, organization_types=organization_types, title=note['title'])

@notes_bp.route('/<string:note_id>/suggestions')
def get_note_suggestions_api(note_id):
    """API endpoint to get AI suggestions for a note (on-demand)."""
    user_id = g.current_user['id']
    
    try:
        # 調用 AI API 獲取建議（較慢）
        suggestions = note_manager.get_note_suggestions(user_id, note_id)
        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notes_bp.route('/<string:note_id>/pre-generated-results')
def get_pre_generated_results(note_id):
    """API endpoint to get pre-generated AI organization results."""
    user_id = g.current_user['id']
    
    try:
        # 使用新的方法獲取所有保存的整理結果
        all_organizations = note_manager.get_all_saved_organizations(user_id, note_id)
        
        # 轉換為前端需要的格式（只返回最新的結果）
        organization_results = {}
        for org_type, analyses in all_organizations.items():
            if analyses:
                # 取最新的結果
                latest_analysis = analyses[0]
                organization_results[org_type] = {
                    'result': latest_analysis['result'],
                    'analysis_id': latest_analysis['id'],
                    'created_at': latest_analysis['created_at']
                }
        
        return jsonify({
            'success': True,
            'results': organization_results,
            'total_types': len(organization_results)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notes_bp.route('/<string:note_id>/organizations')
def get_all_organizations(note_id):
    """API endpoint to get all AI organization results (including history)."""
    user_id = g.current_user['id']
    
    try:
        all_organizations = note_manager.get_all_saved_organizations(user_id, note_id)
        
        return jsonify({
            'success': True,
            'organizations': all_organizations,
            'summary': {
                'total_types': len(all_organizations),
                'total_analyses': sum(len(analyses) for analyses in all_organizations.values())
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notes_bp.route('/<string:note_id>/organizations/<int:analysis_id>', methods=['DELETE'])
def delete_organization(note_id, analysis_id):
    """API endpoint to delete a specific AI organization result."""
    user_id = g.current_user['id']
    
    try:
        success = note_manager.delete_organization(user_id, note_id, analysis_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '整理結果已刪除'
            })
        else:
            return jsonify({
                'success': False,
                'error': '刪除失敗，可能是權限不足或記錄不存在'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notes_bp.route('/<string:note_id>/organize', methods=['POST'])
def organize_note_with_ai(note_id):
    """API endpoint to organize note with AI."""
    user_id = g.current_user['id']
    organization_type = request.json.get('organization_type')

    if not organization_type:
        return jsonify({
            'success': False,
            'error': '請選擇整理方式'
        }), 400

    try:
        result = note_manager.organize_note_with_ai(user_id, note_id, organization_type)

        # For qa_learning, manually serialize to ensure clean JSON, as it sometimes contains control characters.
        if organization_type == 'qa_learning' and result.get('success'):
            try:
                # Manually serialize to a UTF-8 encoded string.
                response_data = json.dumps(result, ensure_ascii=False)
                
                # Create a Flask Response object to correctly set the content type and charset.
                return Response(response_data, content_type='application/json; charset=utf-8')

            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f"Error serializing qa_learning result: {e}"
                }), 500

        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notes_bp.route('/<string:note_id>/quiz', methods=['POST'])
def generate_quiz(note_id):
    """API endpoint to generate interactive quiz for a note."""
    user_id = g.current_user['id']
    
    try:
        result = note_manager.generate_quiz_for_note(user_id, note_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notes_bp.route('/<string:note_id>/quiz')
def get_saved_quiz(note_id):
    """API endpoint to get saved quiz for a note."""
    user_id = g.current_user['id']
    
    try:
        quiz = note_manager.get_saved_quiz(user_id, note_id)
        if quiz:
            return jsonify({
                'success': True,
                'quiz': quiz
            })
        else:
            return jsonify({
                'success': False,
                'error': '沒有找到保存的測驗'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@notes_bp.route('/<string:note_id>/edit', methods=['GET', 'POST'])
def edit_note(note_id):
    """Handles the editing of an existing note."""
    user_id = g.current_user['id']
    
    if request.method == 'POST':
        updates = {
            'title': request.form.get('title'),
            'content': request.form.get('content')
        }
        
        # 檢查是否需要重新分析
        enable_ai_reanalysis = request.form.get('enable_ai_reanalysis') == 'on'
        
        if not updates['title'] or not updates['content']:
            flash("標題和內容不能為空。", "danger")
        elif note_manager.update_existing_note(user_id, note_id, enable_ai_reanalysis=enable_ai_reanalysis, **updates):
            if enable_ai_reanalysis:
                flash("筆記已更新並重新分析AI智慧助理內容。", "success")
            else:
                flash("筆記已更新。", "success")
            return redirect(url_for('.note_detail', note_id=note_id))
        else:
            flash("更新筆記失敗。", "danger")
    
    note = note_manager.get_note_details(user_id, note_id)
    if not note:
        flash("找不到要編輯的筆記。", "danger")
        return redirect(url_for('.note_list'))
        
    return render_template('notes/note_edit.html', note=note, title="編輯筆記")

@notes_bp.route('/<string:note_id>/delete', methods=['POST'])
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
