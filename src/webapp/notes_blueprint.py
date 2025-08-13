from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, Response, current_app
from flask_wtf.csrf import CSRFProtect
from ..notes.note_manager import NoteManager
from ..webapp.auth_middleware import require_admin
from ..core.database import DatabaseManager
from ..notes.ai_client import NoteAIClient
from ..utils.file_processor import FileProcessor
import json
import traceback


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
        action = request.form.get('action')
        
        # 處理智能AI生成請求 (AJAX)
        if action == 'smart_ai_generate':
            try:
                ai_prompt = request.form.get('ai_prompt', '')
                current_content = request.form.get('current_content', '')
                title = request.form.get('title', '')
                
                # 準備生成筆記的資料
                generation_context = {
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
                
        # 處理一般表單提交
        title = request.form.get('title')
        content = request.form.get('content')
        smart_ai_mode = request.form.get('smart_ai_mode') == 'on'
        
        # AI 功能選項
        enable_ai_analysis = request.form.get('enable_ai_analysis') == 'on'
        enable_ai_organization = request.form.get('enable_ai_organization') == 'on'
        organization_types = request.form.getlist('organization_types')

        # 如果啟用智能AI模式且內容為空，則不要求必填
        if not title or (not content and not smart_ai_mode):
            flash("標題和內容不能為空。", "danger")
            return render_template('notes/note_edit.html', title="新增筆記")

        # 如果內容為空但啟用了智能AI模式，先生成內容
        if not content and smart_ai_mode:
            try:
                ai_prompt = request.form.get('ai_prompt', '')
                generation_context = {
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
                    default_title=title,
                    default_content=''
                )

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


@notes_bp.route('/new-wysiwyg', methods=['GET', 'POST'])
def create_note_wysiwyg():
    """Handles the creation of a new note using WYSIWYG editor."""
    if request.method == 'POST':
        user_id = g.current_user['id']
        
        try:
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            tags = request.form.get('tags', '').strip()
            
            if not title:
                flash("請輸入筆記標題。", "danger")
                return render_template('notes/note_edit_wysiwyg.html', title="新增筆記 - WYSIWYG", note=None)
            
            # 處理組織類型（如果是新筆記）
            organization_types = request.form.getlist('organization_types')
            enable_ai_organization = bool(organization_types)
            
            # 建立筆記
            note_id = note_manager.create_new_note(
                user_id, 
                title, 
                content, 
                tags=tags,
                enable_ai_analysis=False
            )
            
            if note_id:
                # 如果選擇了 AI 整理功能，則異步生成整理結果
                if enable_ai_organization and organization_types:
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
                    
                    flash(f"筆記已成功建立！{len(organization_types)} 種整理方式正在背景生成中...", "success")
                else:
                    flash("筆記已成功建立！", "success")
                
                return redirect(url_for('.note_detail', note_id=note_id))
            else:
                flash("建立筆記時發生錯誤。", "danger")
                
        except Exception as e:
            flash(f"建立筆記時發生錯誤：{str(e)}", "danger")
            print(f"建立筆記錯誤：{e}")
            traceback.print_exc()

    return render_template('notes/note_edit_wysiwyg.html', title="新增筆記 - WYSIWYG", note=None)


@notes_bp.route('/edit-wysiwyg/<int:note_id>', methods=['GET', 'POST'])
def edit_note_wysiwyg(note_id):
    """Handles editing a note using WYSIWYG editor."""
    user_id = g.current_user['id']
    note = note_manager.get_user_note(user_id, note_id)
    
    if not note:
        flash("找不到指定的筆記。", "danger")
        return redirect(url_for('.note_list'))
    
    if request.method == 'POST':
        try:
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            tags = request.form.get('tags', '').strip()
            
            if not title:
                flash("請輸入筆記標題。", "danger")
                return render_template('notes/note_edit_wysiwyg.html', 
                                     title="編輯筆記 - WYSIWYG", note=note)
            
            # 更新筆記
            success = note_manager.update_note(user_id, note_id, title, content, tags)
            
            if success:
                flash("筆記已成功更新！", "success")
                return redirect(url_for('.note_detail', note_id=note_id))
            else:
                flash("更新筆記時發生錯誤。", "danger")
                
        except Exception as e:
            flash(f"更新筆記時發生錯誤：{str(e)}", "danger")
            print(f"更新筆記錯誤：{e}")
            traceback.print_exc()

    return render_template('notes/note_edit_wysiwyg.html', 
                         title="編輯筆記 - WYSIWYG", note=note)


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
    
    # 查詢從此筆記生成的模擬題
    from ..core.database import DatabaseManager
    db = DatabaseManager()
    mock_questions = db.get_questions_by_note_id(note_id)
    
    return render_template('notes/note_detail.html', note=note, organization_types=organization_types, 
                         mock_questions=mock_questions, title=note['title'])

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

@notes_bp.route('/<string:note_id>/generate-mock-questions', methods=['POST'])
def generate_mock_questions(note_id):
    """API endpoint to generate mock exam questions from note content and add them to the question database."""
    user_id = g.current_user['id']
    
    try:
        # 獲取筆記內容
        note = note_manager.get_note_details(user_id, note_id)
        if not note:
            return jsonify({
                'success': False,
                'error': '找不到指定的筆記'
            }), 404
        
        note_content = note.get('content', '')
        note_title = note.get('title', '')
        
        if not note_content:
            return jsonify({
                'success': False,
                'error': '筆記內容為空'
            }), 400
        
        # 從請求中獲取主題（如果有的話）
        subject = request.form.get('subject', '')
        if not subject and note.get('ai_keywords'):
            # 如果未提供主題，嘗試從筆記關鍵字中推斷
            if len(note['ai_keywords']) > 0:
                subject = note['ai_keywords'][0]  # 使用第一個關鍵字作為主題
        
        # 使用 GeminiClient 和 ContentFlow 生成模擬題
        from ..core.database import DatabaseManager
        from ..core.gemini_client import GeminiClient
        from ..flows.content_flow import ContentFlow
        import asyncio
        import concurrent.futures
        
        gemini_client = GeminiClient()
        db = DatabaseManager()
        content_flow = ContentFlow(gemini_client, db)
        
        # 使用 asyncio 執行非同步任務
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 生成模擬題
            questions = loop.run_until_complete(gemini_client.generate_questions_from_text(note_content, subject))
            
            if not questions:
                return jsonify({
                    'success': False,
                    'error': '生成模擬題失敗'
                }), 500
            
            # 將模擬題添加到題庫
            added_questions = []
            
            # 創建一個臨時文檔來關聯這些問題 (使用筆記ID作為文檔ID)
            doc_id = None
            
            print(f"開始處理 {len(questions)} 道模擬題，從筆記 '{note_title}' (ID: {note_id}) 生成")
            
            # 準備所有問題數據並去重知識點
            question_data_list = []
            for i, question in enumerate(questions):
                # 準備問題數據
                question_data = {
                    'title': question.get('title', f'模擬題 {i+1}'),
                    'question': question.get('question', ''),  # 注意這裡用 'question' 而不是 'question_text'
                    'answer': question.get('answer', ''),
                    'subject': subject,
                    'difficulty': question.get('difficulty', ''),
                    'knowledge_points': question.get('knowledge_points', []),
                    'source_type': 'note',
                    'source_note_id': note_id,
                    'source_note_title': note_title
                }
                
                # 對問題數據進行預處理，去除可能的重複知識點
                if 'knowledge_points' in question_data and question_data['knowledge_points']:
                    # 使用集合去重，保持順序，並確保清理空白和特殊字符
                    unique_kps = []
                    kp_set = set()
                    for kp in question_data['knowledge_points']:
                        if kp:  # 確保不是 None 或空值
                            kp_clean = str(kp).strip()
                            if kp_clean and kp_clean.lower() not in kp_set:
                                unique_kps.append(kp_clean)
                                kp_set.add(kp_clean.lower())
                    
                    question_data['knowledge_points'] = unique_kps
                    print(f"  📝 題目 {i+1}: 原始知識點 {len(question.get('knowledge_points', []))} 個，去重後 {len(unique_kps)} 個")
                else:
                    question_data['knowledge_points'] = []
                
                question_data_list.append((question_data, i+1))
            
            # 使用並行處理來處理所有問題
            async def process_all_questions():
                """並行處理所有模擬題"""
                tasks = []
                for question_data, question_index in question_data_list:
                    task = content_flow._process_single_question_concurrently(
                        question_data=question_data,
                        doc_id=doc_id,
                        subject=subject,
                        question_index=question_index,
                        is_generated_question=True
                    )
                    tasks.append(task)
                
                # 等待所有任務完成
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return results
            
            # 執行並行處理
            results = loop.run_until_complete(process_all_questions())
            
            # 處理結果
            for i, result in enumerate(results):
                try:
                    if isinstance(result, Exception):
                        error_msg = str(result)
                        print(f"處理模擬題 {i+1} 時發生錯誤: {result}")
                        
                        # 如果是知識點重複錯誤，嘗試記錄更多詳情
                        if "Duplicate entry" in error_msg and "knowledge_point" in error_msg:
                            original_kps = question_data_list[i][0].get('knowledge_points', [])
                            print(f"  📋 題目 {i+1} 的知識點: {original_kps}")
                        continue
                        
                    if result and result.get('success') and result.get('id'):
                        # 記錄答案來源為筆記
                        db.edit_question(
                            result['id'], 
                            subject, 
                            result['stem'], 
                            result['answer'], 
                            None, 
                            f"筆記：{note_title} (ID: {note_id})"
                        )
                        
                        # 記錄成功添加的問題
                        added_questions.append({
                            'id': result['id'],
                            'title': question_data_list[i][0]['title']
                        })
                    else:
                        print(f"處理模擬題 {i+1} 失敗: 結果無效或缺少必要欄位")
                        
                except Exception as e:
                    print(f"處理模擬題 {i+1} 結果時發生錯誤: {e}")
                    continue
            
            return jsonify({
                'success': True,
                'message': f'成功生成並添加了 {len(added_questions)} 道模擬題到題庫',
                'questions': added_questions
            })
            
        finally:
            loop.close()
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'生成模擬題時發生錯誤: {str(e)}'
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

@notes_bp.route('/<string:note_id>/apply-formatted-content', methods=['POST'])
def apply_formatted_content(note_id):
    """API endpoint to apply formatted content to the original note."""
    user_id = g.current_user['id']
    analysis_id = request.json.get('analysis_id')
    
    if not analysis_id:
        return jsonify({
            'success': False,
            'error': '必須提供 analysis_id 參數'
        }), 400
        
    try:
        result = note_manager.apply_formatted_content(user_id, note_id, analysis_id)
        return jsonify(result)
    except Exception as e:
        print(f"應用格式化內容時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'應用格式化內容時發生錯誤: {str(e)}'
        }), 500

@notes_bp.route('/<string:note_id>/update-content', methods=['POST'])
def update_note_content(note_id):
    """API endpoint to directly update note content."""
    user_id = g.current_user['id']
    new_content = request.json.get('content')
    
    if not new_content:
        return jsonify({
            'success': False,
            'error': '必須提供 content 參數'
        }), 400
        
    try:
        result = note_manager.update_note_content_directly(user_id, note_id, new_content)
        return jsonify(result)
    except Exception as e:
        print(f"直接更新筆記內容時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'更新筆記內容時發生錯誤: {str(e)}'
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
        action = request.form.get('action')
        
        # 處理智能AI生成請求 (AJAX)
        if action == 'smart_ai_generate':
            try:
                ai_prompt = request.form.get('ai_prompt', '')
                current_content = request.form.get('current_content', '')
                title = request.form.get('title', '')
                
                # 獲取當前筆記內容
                note = note_manager.get_note_details(user_id, note_id)
                
                # 準備生成筆記的資料
                generation_context = {
                    'user_content': current_content,
                    'user_prompt': ai_prompt,
                    'title': title,
                    'original_note': note
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
        
        # 處理一般保存請求
        updates = {
            'title': request.form.get('title'),
            'content': request.form.get('content')
        }
        
        # 檢查是否需要重新分析
        enable_ai_reanalysis = request.form.get('enable_ai_reanalysis') == 'on'
        smart_ai_mode = request.form.get('smart_ai_mode') == 'on'
        
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

@notes_bp.route('/<string:note_id>/revisions')
def get_note_revisions(note_id):
    """Return revision snapshots for a note."""
    user_id = g.current_user['id']
    try:
        analyses = note_manager.db_manager.get_ai_analysis(user_id, note_id, 'revision_snapshot')
        # 簡化輸出
        revisions = [
            {
                'id': a['id'],
                'created_at': a['created_at'],
                'length': a['result'].get('length'),
                'title': a['result'].get('previous_title')
            }
            for a in analyses
        ]
        return jsonify({'success': True, 'revisions': revisions})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@notes_bp.route('/<string:note_id>/revisions/<int:rev_id>')
def get_note_revision_detail(note_id, rev_id):
    """Return specific revision snapshot"""
    user_id = g.current_user['id']
    try:
        data = note_manager.db_manager.get_ai_analysis_by_id(user_id, note_id, rev_id)
        if not data or data['analysis_type'] != 'revision_snapshot':
            return jsonify({'success': False, 'error': '找不到版本或類型不匹配'}), 404
        return jsonify({'success': True, 'revision': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@notes_bp.route('/<string:note_id>/revisions/<int:rev_id>/restore', methods=['POST'])
def restore_note_revision(note_id, rev_id):
    """Restore note content/title from a revision_snapshot."""
    user_id = g.current_user['id']
    try:
        data = note_manager.db_manager.get_ai_analysis_by_id(user_id, note_id, rev_id)
        if not data or data['analysis_type'] != 'revision_snapshot':
            return jsonify({'success': False, 'error': '找不到版本或類型不匹配'}), 404

        result = data.get('result') or {}
        prev_title = result.get('previous_title')
        prev_content = result.get('previous_content')
        if prev_title is None and prev_content is None:
            return jsonify({'success': False, 'error': '版本資料不完整'}), 400

        updates = {}
        if prev_title is not None:
            updates['title'] = prev_title
        if prev_content is not None:
            updates['content'] = prev_content

        ok = note_manager.update_existing_note(user_id, note_id, enable_ai_reanalysis=False, **updates)
        if not ok:
            return jsonify({'success': False, 'error': '還原失敗'}), 500
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# 重複定義的 restore 路由已移除，保留單一實作避免 endpoint 衝突

@notes_bp.route('/detect-text', methods=['POST'])
def detect_text():
    """處理AI文字偵測請求 - 即時分析用戶輸入並提供建議，或生成增強內容"""
    try:
        user_id = g.current_user['id']
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少請求數據'
            }), 400
        
        # 檢查是否為內容增強生成請求
        if data.get('action') == 'generate_enhancement':
            enhancement_request = data.get('enhancement_request', '')
            current_content = data.get('current_content', '')
            title = data.get('title', '')
            context = data.get('context', {})
            
            if not enhancement_request:
                return jsonify({
                    'success': False,
                    'error': '缺少增強請求參數'
                }), 400
            
            # 調用AI生成增強內容
            enhancement_result = note_manager.generate_enhancement_content(
                user_id=user_id,
                enhancement_request=enhancement_request,
                current_content=current_content,
                title=title,
                context=context
            )
            
            return jsonify({
                'success': True,
                'generated_content': enhancement_result.get('generated_content', ''),
                **enhancement_result
            })
        
        # 原有的文字偵測功能
        content = data.get('content')
        if not content:
            return jsonify({
                'success': False,
                'error': '缺少內容參數'
            }), 400
        
        context = data.get('context', {})
        
        # 調用AI文字偵測功能
        detection_result = note_manager.detect_and_suggest_text(
            user_id=user_id,
            content=content,
            context=context
        )
        
        return jsonify({
            'success': True,
            'has_suggestions': detection_result.get('has_suggestions', False),
            **detection_result
        })
        
    except Exception as e:
        print(f"AI處理錯誤: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'has_suggestions': False
        }), 500

# === New: Import files into note (pdf, docx, md, images) ===
@notes_bp.route('/import', methods=['POST'])
def import_note_content():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '缺少檔案'}), 400
        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'success': False, 'message': '檔案為空'}), 400

        # Persist to a temp file and let FileProcessor handle by path
        import os, tempfile, shutil
        suffix = ''
        if '.' in (file.filename or ''):
            suffix = '.' + file.filename.rsplit('.', 1)[-1].lower()
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(tmp_fd)
        try:
            with open(tmp_path, 'wb') as f:
                shutil.copyfileobj(file.stream, f)

            fp = FileProcessor()
            raw_text, content_type = fp.process_input(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        # Strict format-only via auxiliary model
        ai = NoteAIClient()
        result = ai.format_markdown_strict(raw_text)
        return jsonify({
            'success': True,
            'markdown': result.get('markdown', ''),
            'type': content_type,
            'guard': result.get('guard'),
            'model_used': result.get('model_used')
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# === New: Handwriting canvas image import (PNG/JPEG) ===
@notes_bp.route('/upload-image', methods=['POST'])
def upload_image():
    """Handle image upload for WYSIWYG editor."""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': '沒有選擇檔案'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'error': '沒有選擇檔案'}), 400
        
        # 檢查檔案類型
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({'success': False, 'error': '不支援的檔案格式'}), 400
        
        # 從 .env 獲取上傳路徑
        upload_folder = current_app.config.get('FILE_STORAGE_PATH')
        if not upload_folder:
            upload_folder = os.path.join(current_app.root_path, '..', '..', 'uploads')
        
        # 確保目錄存在
        import os, tempfile, shutil
        os.makedirs(upload_folder, exist_ok=True)
        
        # 生成安全的檔案名
        import uuid
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        filename = f"upload_{timestamp}_{uuid.uuid4().hex[:8]}.{file_extension}"
        file_path = os.path.join(upload_folder, filename)
        
        # 保存檔案
        file.save(file_path)
        
        # 生成URL (相對於static路徑)
        image_url = f"/uploads/{filename}"
        
        return jsonify({
            'success': True,
            'url': image_url,
            'filename': filename,
            'path': file_path
        })
        
    except Exception as e:
        print(f"圖片上傳錯誤：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@notes_bp.route('/upload-image-dataurl', methods=['POST'])
def upload_image_dataurl():
    """Handle image upload from data URL (for handwriting canvas)."""
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'success': False, 'error': '沒有圖片資料'}), 400
        
        image_data = data['image']
        
        # 解析data URL
        import base64
        import io
        from datetime import datetime
        
        if not image_data.startswith('data:image'):
            return jsonify({'success': False, 'error': '無效的圖片格式'}), 400
        
        # 提取base64資料
        header, encoded = image_data.split(',', 1)
        image_bytes = base64.b64decode(encoded)
        
        # 從 .env 獲取上傳路徑
        upload_folder = current_app.config.get('FILE_STORAGE_PATH')
        if not upload_folder:
            upload_folder = os.path.join(current_app.root_path, '..', '..', 'uploads')
        
        # 確保目錄存在
        os.makedirs(upload_folder, exist_ok=True)
        
        # 生成檔案名
        import uuid
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"handwriting_{timestamp}_{uuid.uuid4().hex[:8]}.png"
        file_path = os.path.join(upload_folder, filename)
        
        # 保存檔案
        with open(file_path, 'wb') as f:
            f.write(image_bytes)
        
        # 生成URL (相對於static路徑)
        image_url = f"/uploads/{filename}"
        
        return jsonify({
            'success': True,
            'url': image_url,
            'filename': filename,
            'path': file_path
        })
        
    except Exception as e:
        print(f"DataURL圖片上傳錯誤：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@notes_bp.route('/handwriting-to-text', methods=['POST'])
def handwriting_to_text():
    """Convert handwriting image to text using FileProcessor OCR."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '沒有請求資料'}), 400
        
        # 支援兩種輸入方式：
        # 1. 直接傳檔案路徑 (推薦)
        # 2. 傳 base64 圖片資料 (會先上傳保存後再處理)
        
        file_path = data.get('file_path')
        image_data = data.get('image')
        
        if file_path:
            # 方式1：直接使用檔案路徑
            if not os.path.exists(file_path):
                return jsonify({'success': False, 'error': '檔案不存在'}), 400
            target_file_path = file_path
            
        elif image_data:
            # 方式2：base64 圖片資料，先透過 upload_image_dataurl 保存
            # 這樣可以重用現有的檔案保存邏輯
            try:
                # 模擬內部調用 upload_image_dataurl 的邏輯
                if not image_data.startswith('data:image'):
                    return jsonify({'success': False, 'error': '無效的圖片格式'}), 400
                
                # 提取base64資料並保存檔案
                header, encoded = image_data.split(',', 1)
                image_bytes = base64.b64decode(encoded)
                
                # 從 .env 獲取上傳路徑
                upload_folder = current_app.config.get('FILE_STORAGE_PATH')
                if not upload_folder:
                    upload_folder = os.path.join(current_app.root_path, '..', '..', 'uploads')
                
                # 確保目錄存在
                os.makedirs(upload_folder, exist_ok=True)
                
                # 生成檔案名
                import uuid
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"handwriting_ocr_{timestamp}_{uuid.uuid4().hex[:8]}.png"
                target_file_path = os.path.join(upload_folder, filename)
                
                # 保存檔案
                with open(target_file_path, 'wb') as f:
                    f.write(image_bytes)
                    
            except Exception as e:
                return jsonify({'success': False, 'error': f'檔案保存失敗: {str(e)}'}), 500
            
        else:
            return jsonify({'success': False, 'error': '缺少 file_path 或 image 資料'}), 400
        
        try:
            # 使用 FileProcessor 進行 OCR
            from src.utils.file_processor import FileProcessor
            file_processor = FileProcessor()
            detected_text = file_processor.read_image_file(target_file_path)
            
            return jsonify({
                'success': True,
                'text': detected_text.strip() if detected_text else '[無法識別文字內容]'
            })
            
        except Exception as ocr_error:
            return jsonify({
                'success': False, 
                'error': f'OCR 處理失敗: {str(ocr_error)}'
            }), 500
        
    except Exception as e:
        print(f"手寫辨識錯誤：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@notes_bp.route('/ai/ghost-suggestion', methods=['POST'])
def ghost_suggestion():
    """Provide AI ghost text suggestions."""
    try:
        data = request.get_json()
        if not data or 'context' not in data:
            return jsonify({'success': False, 'error': '沒有上下文資料'}), 400
        
        context = data['context']
        mode = data.get('mode', 'supplement')
        user_id = g.current_user['id']
        
        # 檢查上下文是否有意義的內容
        if not context.strip() or len(context.strip()) < 10:
            return jsonify({
                'success': True,
                'suggestion': '請輸入更多內容以獲得更好的建議...'
            })
        
        # 使用GhostAIClient生成建議
        from ..notes.ghost_ai_client import GhostAIClient
        ghost_client = GhostAIClient()
        
        # 根據模式構建prompt
        mode_prompts = {
            'supplement': '根據上下文，自然地延續寫作內容，保持風格一致：',
            'summary': '為以下內容生成簡潔摘要：',
            'outline': '為以下內容生成清晰大綱：',
            'qa': '從以下內容提取重要問答對：',
        }
        
        prompt = mode_prompts.get(mode, mode_prompts['supplement'])
        full_prompt = f"{prompt}\n\n{context}"
        
        try:
            # 使用GhostAIClient的generate_content_enhancement方法
            response = ghost_client.generate_content_enhancement(
                enhancement_request=prompt,
                current_content=context,
                title="Ghost建議",
                context={'mode': mode, 'user_id': user_id}
            )
            
            suggestion = response.get('generated_content', '') if isinstance(response, dict) else str(response)
            
            # 檢查是否被安全過濾器攔截
            if not suggestion or suggestion.strip() == '':
                # 提供友善的回覆而不是錯誤
                return jsonify({
                    'success': True,
                    'suggestion': '請嘗試不同的內容或表達方式...'
                })
            
            return jsonify({
                'success': True,
                'suggestion': suggestion.strip()
            })
            
        except Exception as ai_error:
            error_msg = str(ai_error)
            # 只在非安全過濾器錯誤時打印
            if not any(keyword in error_msg.lower() for keyword in ['安全過濾器', 'safety', 'blocked', 'filtered', 'inappropriate']):
                print(f"AI生成建議錯誤：{error_msg}")
            
            # 檢查是否是安全過濾器問題
            if any(keyword in error_msg.lower() for keyword in ['安全過濾器', 'safety', 'blocked', 'filtered', 'inappropriate']):
                return jsonify({
                    'success': True,
                    'suggestion': '請嘗試其他表達方式，或繼續您的想法...'
                })
            
            # 其他錯誤時返回備用建議
            fallback_suggestions = {
                'supplement': '繼續您的想法...',
                'summary': '總結重點：',
                'outline': '主要概念：\n- 要點一\n- 要點二',
                'qa': 'Q: 主要問題是什麼？\nA: 根據內容分析...'
            }
            
            return jsonify({
                'success': True, 
                'suggestion': fallback_suggestions.get(mode, '繼續寫作...')
            })
        
    except Exception as e:
        print(f"Ghost建議錯誤：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@notes_bp.route('/ai/completion', methods=['POST'])
def ai_completion():
    """Provide AI content completion."""
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({'success': False, 'error': '沒有內容資料'}), 400
        
        content = data['content']
        command = data.get('command', 'supplement')
        user_id = g.current_user['id']
        
        # 使用現有的AI客戶端生成補完
        ai_client = NoteAIClient()
        
        # 根據命令構建prompt
        command_prompts = {
            'summary': '請以條列重點摘要以下內容，限5-8點：',
            'outline': '根據以下內容生成清晰的Markdown大綱：',
            'bullets': '將以下內容整理為條列要點：',
            'qa': '從以下內容萃取5-8組問答對（Q/A）：',
            'supplement': '根據以下內容延續撰寫1-3段補充：',
            'rewrite-formal': '將以下內容改寫為更正式、客觀的表述：',
            'format-note': '將以下筆記格式化為清晰的Markdown結構：'
        }
        
        prompt = command_prompts.get(command, command_prompts['supplement'])
        full_prompt = f"{prompt}\n\n{content}"
        
        try:
            # 使用AI客戶端的正確方法
            response = ai_client.generate_content_enhancement(
                enhancement_request=prompt,
                current_content=content,
                title="AI內容增強",
                context={'command': command, 'user_id': user_id}
            )
            
            completion = response.get('enhanced_content', '') if isinstance(response, dict) else str(response)
            
            return jsonify({
                'success': True,
                'completion': completion.strip()
            })
            
        except Exception as ai_error:
            print(f"AI補完錯誤：{ai_error}")
            return jsonify({
                'success': False, 
                'error': 'AI服務暫時不可用'
            }), 503
        
    except Exception as e:
        print(f"AI補完錯誤：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@notes_bp.route('/handwriting', methods=['POST'])
def import_handwriting_content():
    try:
        # Accept either multipart file 'image' or base64 in JSON {'image_base64': 'data:image/png;base64,...'}
        image_bytes = None
        filename = None
        if 'image' in request.files:
            f = request.files['image']
            image_bytes = f.read()
            filename = f.filename or 'canvas.png'
        elif request.is_json:
            data = request.get_json(silent=True) or {}
            b64 = data.get('image_base64') or ''
            import re, base64
            m = re.match(r"^data:image/(png|jpeg|jpg);base64,(.+)", b64, re.IGNORECASE)
            if m:
                filename = f"canvas.{m.group(1).lower()}"
                image_bytes = base64.b64decode(m.group(2))
        if not image_bytes:
            return jsonify({'success': False, 'message': '缺少手寫影像'}), 400

        # Save to temp image file and OCR
        import os, tempfile
        suffix = '.png'
        if filename and '.' in filename:
            suffix = '.' + filename.rsplit('.', 1)[-1].lower()
        fd, tmp_img = tempfile.mkstemp(suffix=suffix)
        try:
            os.close(fd)
            with open(tmp_img, 'wb') as out:
                out.write(image_bytes)
            fp = FileProcessor()
            raw_text = fp.read_image_file(tmp_img)
            content_type = 'image'
        finally:
            try:
                os.unlink(tmp_img)
            except Exception:
                pass
        ai = NoteAIClient()
        result = ai.format_markdown_strict(raw_text)
        return jsonify({
            'success': True,
            'markdown': result.get('markdown', ''),
            'type': content_type or 'image-handwriting',
            'guard': result.get('guard'),
            'model_used': result.get('model_used')
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

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

# AI相關API端點
@notes_bp.route('/ai/command', methods=['POST'])
def ai_command():
    """處理AI命令請求"""
    try:
        data = request.get_json()
        command = data.get('command')
        content = data.get('content')
        format_type = data.get('format', 'html')
        
        if not command or not content:
            return jsonify({'success': False, 'error': '缺少必要參數'})
        
        # 使用AI客戶端處理命令
        ai_client = NoteAIClient()
        
        command_prompts = {
            'summary': '請以條列重點摘要以下內容，限5-8點：',
            'outline': '根據以下內容生成清晰的Markdown大綱：',
            'bullets': '將以下內容整理為條列要點：',
            'qa': '從以下內容萃取5-8組問答對（Q/A）：',
            'supplement': '根據以下內容延續撰寫1-3段補充：',
            'rewrite-formal': '將以下內容改寫為更正式、客觀的表述：',
            'rewrite-brief': '將以下內容改寫為更精簡版本：',
            'abbr-explain': '列出文中出現的縮寫詞的全名與解釋：'
        }
        
        prompt = command_prompts.get(command, '請處理以下內容：')
        full_prompt = f"{prompt}\n\n{content}"
        
        try:
            # 使用AI客戶端生成結果
            response = ai_client.generate_content_enhancement(
                enhancement_request=prompt,
                current_content=content,
                title="AI命令處理",
                context={'command': command, 'user_id': g.current_user['id']}
            )
            
            if isinstance(response, dict) and response.get('generated_content'):
                result = response['generated_content']
            else:
                result = str(response) if response else '處理失敗'
            
            return jsonify({'success': True, 'result': result})
            
        except Exception as e:
            print(f"AI命令處理錯誤：{e}")
            # 返回備用結果
            fallback_results = {
                'summary': '## 摘要\n\n- 請手動補充重點摘要\n- 包含主要概念和要點',
                'outline': '## 大綱\n\n1. 主要概念\n2. 重點說明\n3. 總結要點',
                'bullets': '## 條列要點\n\n- 要點一\n- 要點二\n- 要點三',
                'qa': '## 問答\n\n**Q:** 主要問題是什麼？\n**A:** 請根據內容補充答案。',
                'supplement': '## 補充內容\n\n請根據上述內容繼續補充相關資訊...',
                'rewrite-formal': '## 正式表述\n\n（請手動改寫為正式文體）',
                'rewrite-brief': '## 精簡版本\n\n（請手動改寫為精簡版本）',
                'abbr-explain': '## 縮寫詞解釋\n\n- 請補充縮寫詞的全名與解釋'
            }
            
            return jsonify({
                'success': True,
                'result': fallback_results.get(command, '處理過程中發生錯誤，請重試。')
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@notes_bp.route('/ai/generate', methods=['POST'])
def ai_generate():
    """處理AI內容生成請求"""
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        current_content = data.get('current_content', '')
        format_type = data.get('format', 'html')
        
        if not prompt:
            return jsonify({'success': False, 'error': '缺少提示內容'})
        
        # 使用AI客戶端生成內容
        ai_client = NoteAIClient()
        response = ai_client.generate_content_enhancement(
            enhancement_request=prompt,
            current_content=current_content,
            title="AI Prompt生成",
            context={'format': format_type, 'user_id': g.current_user['id']}
        )
        
        generated_content = response.get('enhanced_content', '') if isinstance(response, dict) else str(response)
        
        return jsonify({
            'success': True,
            'generated_content': generated_content
        })
        
    except Exception as e:
        print(f"AI生成錯誤：{e}")
        # 提供備用內容
        fallback_content = f"""
        <h3>AI生成內容</h3>
        <p>根據您的提示：<em>"{data.get('prompt', '')}"</em></p>
        <p>AI服務暫時不可用，這是一個示例內容。</p>
        """
        
        return jsonify({
            'success': True,
            'generated_content': fallback_content,
            'fallback': True
        })

@notes_bp.route('/api/gateway-info', methods=['GET'])
def get_gateway_info():
    """獲取AI Gateway的連接信息"""
    try:
        from ..ai_gateway import get_gateway_port
        gateway_port = get_gateway_port()
        
        return jsonify({
            'success': True,
            'gateway_port': gateway_port,
            'lsp_websocket_url': f"ws://localhost:{gateway_port}/lsp/markdown"
        })
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': str(e),
            'gateway_port': 8002,  # fallback
            'lsp_websocket_url': "ws://localhost:8002/lsp/markdown"
        })
