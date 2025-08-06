from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, Response
from ..notes.note_manager import NoteManager
from ..webapp.auth_middleware import require_admin
from ..core.database import DatabaseManager
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
