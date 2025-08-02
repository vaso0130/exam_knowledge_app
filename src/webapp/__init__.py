

import os
import json
import tempfile
import asyncio
import markdown
import re
from ..utils.markdown_utils import format_answer_text

def fix_markdown_numbering(text: str) -> str:
    """Normalize ordered list formatting so markdown renders correctly.

    This function adds missing blank lines before list blocks and fixes
    numbering so that sequences like ``1.`` ``2.`` render as an ordered
    list in HTML. Other content is returned unchanged.
    """
    if not text:
        return text

    lines = text.splitlines()
    result: list[str] = []
    counters: dict[int, int] = {}
    prev_is_list = False
    prev_indent = 0

    for line in lines:
        match = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
        if match:
            indent_str, _num, content = match.groups()
            indent = len(indent_str)

            # reset deeper indent counters when indentation decreases
            counters = {k: v for k, v in counters.items() if k <= indent}

            if not prev_is_list or indent != prev_indent:
                if result and result[-1].strip():
                    result.append("")
                counters[indent] = 0

            counters[indent] = counters.get(indent, 0) + 1
            result.append(f"{indent_str}{counters[indent]}. {content}")
            prev_is_list = True
            prev_indent = indent
        else:
            prev_is_list = False
            prev_indent = 0
            result.append(line)

    return "\n".join(result)
import uuid
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, abort, redirect, url_for, flash, jsonify, Response

from ..core.database import DatabaseManager
from ..core.gemini_client import GeminiClient
from ..flows.flow_manager import FlowManager
from .async_processor import AsyncProcessor

def create_app():
    # --- App Initialization ---
    app = Flask(__name__)
    
    # --- Security Configuration ---
    secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not secret_key:
        import secrets
        # 生產環境必須設定 FLASK_SECRET_KEY 環境變數
        print("⚠️  警告：未設定 FLASK_SECRET_KEY 環境變數，使用臨時金鑰")
        print("🔧 請執行：python -c \"import secrets; print('FLASK_SECRET_KEY=' + secrets.token_hex(32))\"")
        secret_key = secrets.token_hex(32)  # 臨時生成安全金鑰
    
    app.secret_key = secret_key

    # --- Database and Services Initialization ---
    db = DatabaseManager()
    gemini_client = GeminiClient()
    flow_manager = FlowManager(gemini_client, db)
    async_processor = AsyncProcessor(flow_manager)  # 新增非同步處理器

    # --- File Upload Settings ---
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'html', 'htm', 'md', 'jpg', 'jpeg', 'png', 'bmp', 'webp', 'gif'}
    # Use an absolute path for storage, default to a folder in the project root
    STORAGE_PATH = Path(os.environ.get("FILE_STORAGE_PATH", Path(app.root_path).parent.parent / "uploads"))
    
    # Ensure the storage directory exists
    STORAGE_PATH.mkdir(parents=True, exist_ok=True)

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    # --- Custom Template Filters ---
    @app.template_filter('fromjson')
    def fromjson_filter(value):
        if not value:
            return []
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError) as e:
            app.logger.error(f"JSON parsing error: {e} for value: {value}")
            return []

    # --- Routes ---

    @app.route('/')
    def index():
        subjects = db.get_all_subjects()
        return render_template('index.html', subjects=subjects)

    @app.route('/upload', methods=['GET', 'POST'])
    def upload_file():
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('請選擇檔案')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('請選擇檔案')
                return redirect(request.url)
            
            if file and allowed_file(file.filename):
                original_filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}{Path(original_filename).suffix}"
                file_path = STORAGE_PATH / unique_filename
                
                try:
                    file.save(file_path)
                    suggested_subject = request.form.get('subject')
                    use_async = request.form.get('async_processing') == 'on'  # 檢查是否使用非同步
                    
                    if use_async:
                        # 非同步處理
                        job_id = async_processor.submit_job(
                            'content_processing',
                            file_path=str(file_path),
                            filename=original_filename,
                            subject=suggested_subject or ''
                        )
                        flash('檔案已提交處理，請稍候查看結果')
                        return redirect(url_for('job_status', job_id=job_id))
                    else:
                        # 同步處理（原來的方式）
                        result = flow_manager.content_flow.process_file(str(file_path), original_filename, suggested_subject)
                        
                        if result.get('success'):
                            flash(result.get('message', '檔案處理完成！'))
                        else:
                            flash(f'檔案處理失敗: {result.get("error", "未知錯誤")}')
                        
                        return redirect(url_for('questions'))
                    
                except Exception as e:
                    app.logger.error(f"File processing failed: {e}", exc_info=True)
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                    flash(f'檔案處理失敗: {str(e)}')
                    return redirect(request.url)
            else:
                flash('不支援的檔案格式')
                return redirect(request.url)
        
        subjects = db.get_all_subjects()
        return render_template('upload.html', subjects=subjects)

    @app.route('/process_text', methods=['POST'])
    def process_text():
        try:
            text_content = request.form.get('text_content', '').strip()
            suggested_subject = request.form.get('subject', '').strip()
            
            if not text_content:
                return jsonify({'error': '請輸入文字內容'}), 400

            result = flow_manager.content_flow.complete_ai_processing(
                text_content, 'user_input.txt', suggested_subject
            )
            
            if result.get('success'):
                return jsonify({
                    'success': True,
                    'message': result.get('message', '處理完成！'),
                    'questions_count': len(result.get("questions", []))
                })
            else:
                return jsonify({'error': f'處理失敗: {result.get("error", "未知錯誤")}'}), 500
                
        except Exception as e:
            app.logger.error(f"Text processing failed: {e}", exc_info=True)
            return jsonify({'error': f'系統錯誤: {str(e)}'}), 500

    @app.route('/process_url', methods=['POST'])
    def process_url():
        try:
            url_content = request.form.get('url_content', '').strip()
            suggested_subject = request.form.get('subject', '').strip()
            
            if not url_content:
                return jsonify({'error': '請輸入網址'}), 400
            
            if not (url_content.startswith('http://') or url_content.startswith('https://')):
                url_content = 'https://' + url_content
            
            # 使用異步處理器來處理網路擷取
            title = url_content.split('//')[-1].split('/')[0]
            job_id = async_processor.start_url_processing_job(url_content, title, suggested_subject)
            
            return jsonify({
                'success': True,
                'job_id': job_id,
                'message': '網路擷取工作已開始，請稍候...'
            })
                
        except Exception as e:
            app.logger.error(f"URL processing failed: {e}", exc_info=True)
            return jsonify({'error': f'啟動網路擷取失敗: {str(e)}'}), 500

    @app.route('/questions')
    def questions():
        subject = request.args.get('subject')
        if subject:
            questions_data = db.get_questions_by_subject(subject)
        else:
            questions_data = db.get_all_questions_with_source()
        
        # Ensure the key is 'question_text' for the template
        for q in questions_data:
            if 'question_text' not in q:
                q['question_text'] = q.get('text', '') # Fallback for old data if 'text' exists

        return render_template('questions.html', questions=questions_data, subject=subject)

    @app.route('/delete_question/<q_id>', methods=['POST'])
    def delete_question(q_id):
        try:
            db.delete_question(q_id)
            flash('題目已刪除')
        except Exception as e:
            app.logger.error(f"Deleting question {q_id} failed: {e}", exc_info=True)
            flash(f'刪除失敗: {str(e)}')
        return redirect(url_for('questions'))

    @app.route('/batch_delete', methods=['POST'])
    def batch_delete():
        try:
            question_ids_str = request.form.getlist('question_ids')
            if question_ids_str:
                # question_ids = [int(id_str) for id_str in question_ids_str] # Removed int() conversion
                db.batch_delete_questions(question_ids_str)
                flash(f'已刪除 {len(question_ids_str)} 個題目')
            else:
                flash('請選擇要刪除的題目')
        except Exception as e:
            app.logger.error(f"Batch deleting questions failed: {e}", exc_info=True)
            flash(f'批次刪除失敗: {str(e)}')
        return redirect(url_for('questions'))

    @app.route('/edit_question/<q_id>', methods=['GET', 'POST'])
    def edit_question(q_id):
        if request.method == 'POST':
            try:
                new_subject = request.form.get('subject')
                new_question = request.form.get('question_text')
                new_answer = request.form.get('answer_text')
                new_mindmap = request.form.get('mindmap_code')
                
                # 處理知識點標籤
                knowledge_points_str = request.form.get('knowledge_points', '')
                new_knowledge_points = [kp.strip() for kp in knowledge_points_str.split(',') if kp.strip()]
                
                db.edit_question(q_id, new_subject, new_question, new_answer, new_mindmap, new_knowledge_points)
                flash('題目已更新')
                return redirect(url_for('question_detail', q_id=q_id))
            except Exception as e:
                app.logger.error(f"Editing question {q_id} failed: {e}", exc_info=True)
                flash(f'更新失敗: {str(e)}')
        
        q = db.get_question_by_id(q_id)
        if not q:
            abort(404)
        
        subjects = db.get_all_subjects()
        return render_template('edit_question.html', question=q, subjects=subjects)

    @app.route('/question/<q_id>')
    def question_detail(q_id):
        q = db.get_question_by_id(q_id)
        if not q:
            abort(404)
        
        md = markdown.Markdown(extensions=['sane_lists', 'codehilite', 'fenced_code', 'tables'])
        
        # 直接從資料庫獲取完美格式的文字並渲染
        question_text = q.get('question_text', '')
        question_html = md.convert(question_text)

        # 同樣，直接渲染答案
        answer_text = q.get('answer_text', '')
        md.reset()
        answer_html = md.convert(answer_text)
        
        return render_template('question_detail.html', 
                             question=q, 
                             question_html=question_html,
                             answer_html=answer_html,
                             mindmap_code=q.get('mindmap_code'),
                             question_summary=q.get('question_summary'),
                             solving_tips=q.get('solving_tips'))

    # === 非同步處理相關路由 ===
    
    @app.route('/job/<job_id>')
    def job_status(job_id):
        """查看工作狀態頁面"""
        job_info = async_processor.get_job_status(job_id)
        if not job_info:
            flash('找不到指定的處理工作')
            return redirect(url_for('index'))
        
        return render_template('job_status.html', job=job_info)
    
    @app.route('/api/job/<job_id>/status')
    def api_job_status(job_id):
        """API: 取得工作狀態"""
        job_info = async_processor.get_job_status(job_id)
        if not job_info:
            return jsonify({'error': '找不到指定的工作'}), 404
        
        return jsonify(job_info)
    
    @app.route('/api/job/<job_id>/result')
    def api_job_result(job_id):
        """API: 取得工作結果"""
        job_info = async_processor.get_job_status(job_id)
        if not job_info:
            return jsonify({'error': '找不到指定的工作'}), 404
        
        if job_info['status'] != 'completed':
            return jsonify({'error': '工作尚未完成'}), 400
        
        return jsonify({
            'success': True,
            'result': job_info.get('result'),
            'message': job_info.get('message', '處理完成')
        })

    @app.route('/documents')
    def documents_list():
        try:
            documents = db.get_all_documents()
            for doc in documents:
                content = doc.get('content', '')
                doc['content_preview'] = content[:200] + '...' if content and len(content) > 200 else content
            return render_template('documents_list.html', documents=documents)
        except Exception as e:
            app.logger.error(f"Loading documents list failed: {e}", exc_info=True)
            flash(f'載入文件列表時發生錯誤: {str(e)}', 'danger')
            return redirect(url_for('index'))

    @app.route('/document/<int:doc_id>')
    def document_detail(doc_id):
        document = db.get_document_by_id(doc_id)
        if not document:
            abort(404)
        return render_template('document_detail.html', document=document)

    @app.route('/delete_document/<int:doc_id>', methods=['POST'])
    def delete_document(doc_id):
        try:
            document = db.get_document_by_id(doc_id)
            if not document:
                flash('文件不存在', 'danger')
                return redirect(url_for('documents_list'))

            # If it's a file, try to delete the physical file
            if document.get('file_path') and os.path.exists(document['file_path']):
                os.unlink(document['file_path'])
                app.logger.info(f"Deleted physical file: {document['file_path']}")

            db.delete_document(doc_id)
            flash('文件已成功刪除', 'success')
        except Exception as e:
            app.logger.error(f"Deleting document {doc_id} failed: {e}", exc_info=True)
            flash(f'刪除文件失敗: {str(e)}', 'danger')
        return redirect(url_for('documents_list'))

    @app.route('/original_document/<int:doc_id>')
    def original_document(doc_id):
        document = db.get_document_by_id(doc_id)
        if not document:
            abort(404)
        
        original_content = ""
        if document.get('source') and (document['source'].startswith('http://') or document['source'].startswith('https://')):
            # If it's a URL source, use the content directly from the database
            original_content = document.get('content', '')
        elif document.get('file_path') and os.path.exists(document['file_path']):
            # If it's a local file, read its content
            from ..utils.file_processor import FileProcessor
            original_content, _ = FileProcessor().process_input(document['file_path'])
        else:
            abort(404) # No valid source or file not found

        # 設定 markdown 配置使其輸出 Prism.js 相容的 class
        extension_configs = {
            'codehilite': {
                'guess_lang': False,
                'css_class': 'language-pseudocode',
                'use_pygments': False
            }
        }
        
        md = markdown.Markdown(
            extensions=['sane_lists', 'codehilite', 'fenced_code', 'tables'],
            extension_configs=extension_configs
        )
        original_content = fix_markdown_numbering(original_content)
        original_html = md.convert(original_content)
        
        return render_template('original_document.html', 
                             document=document, 
                             original_html=original_html)

    @app.route('/knowledge')
    def knowledge_list():
        subject = request.args.get('subject')
        kp_map = db.get_all_knowledge_points_with_stats()
        if subject:
            kp_map = {subject: kp_map.get(subject, [])}
        return render_template('knowledge.html', kp_map=kp_map, subject=subject)

    @app.route('/knowledge/<int:id>')
    def knowledge_detail(id):
        knowledge_point = db.get_knowledge_point_by_id(id)
        if not knowledge_point:
            abort(404)

        questions = db.get_questions_for_knowledge_point(id)
        return render_template(
            'knowledge_detail.html',
            name=knowledge_point['name'],
            subject=knowledge_point['subject'],
            questions=questions
        )

    @app.route('/learning-summaries')
    def learning_summaries():
        documents = db.get_documents_with_summaries()
        return render_template('learning_summaries.html', documents=documents)

    @app.route('/edit_mindmap/<q_id>')
    def edit_mindmap(q_id):
        """編輯心智圖頁面"""
        question = db.get_question_by_id(q_id)
        if not question:
            flash('找不到指定的題目')
            return redirect(url_for('questions_list'))
        
        return render_template('edit_mindmap.html', question=question)

    @app.route('/update_mindmap/<q_id>', methods=['POST'])
    def update_mindmap(q_id):
        """更新心智圖"""
        try:
            mindmap_code = request.form.get('mindmap_code', '').strip()
            
            if not mindmap_code:
                return jsonify({'success': False, 'error': '心智圖原始碼不能為空'})
            
            # 簡單驗證 mindmap 格式
            if not mindmap_code.startswith('mindmap'):
                return jsonify({'success': False, 'error': '心智圖必須以 "mindmap" 開頭'})
            
            # 更新資料庫 - 使用現有的 edit_question 方法
            question = db.get_question_by_id(q_id)
            if not question:
                return jsonify({'success': False, 'error': '找不到指定的題目'})
            
            db.edit_question(q_id, question['subject'], question['question_text'], 
                           question['answer_text'], mindmap_code, None)
            
            return jsonify({'success': True, 'message': '心智圖已成功更新'})
            
        except Exception as e:
            return jsonify({'success': False, 'error': f'更新失敗: {str(e)}'})

    @app.route('/regenerate_mindmap/<q_id>', methods=['POST'])
    def regenerate_mindmap(q_id):
        """重新生成心智圖"""
        try:
            # 使用 MindmapFlow 重新生成心智圖
            from ..flows.mindmap_flow import MindmapFlow
            mindmap_flow = MindmapFlow(gemini_client, db)
            
            # 使用 asyncio 執行異步任務
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(mindmap_flow.generate_and_save_mindmap(q_id))
                
                if isinstance(result, str):
                    # 成功生成心智圖
                    return jsonify({
                        'success': True, 
                        'message': '心智圖已重新生成', 
                        'mindmap_code': result
                    })
                elif isinstance(result, dict) and not result.get('success', True):
                    # 生成失敗
                    return jsonify({
                        'success': False, 
                        'error': result.get('error', '未知錯誤')
                    })
                else:
                    return jsonify({'success': False, 'error': '未知的返回格式'})
                    
            finally:
                loop.close()
                
        except Exception as e:
            app.logger.error(f"重新生成心智圖失敗: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'重新生成失敗: {str(e)}'})

    @app.route('/regenerate_answer/<q_id>', methods=['POST'])
    def regenerate_answer(q_id):
        """重新生成題目答案"""
        try:
            # 獲取題目信息
            question_data = db.get_question_by_id(q_id)
            if not question_data:
                return jsonify({'success': False, 'error': '找不到指定的題目'})
            
            question_text = question_data.get('question_text', '')
            if not question_text:
                return jsonify({'success': False, 'error': '題目內容為空'})
            
            # 使用 asyncio 執行異步任務
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 調用 Gemini 重新生成答案
                answer_result = loop.run_until_complete(gemini_client.generate_answer(question_text))
                
                if answer_result and answer_result.get('answer'):
                    answer_text = answer_result['answer']
                    sources = answer_result.get('sources', [])
                    
                    # 更新資料庫中的答案
                    subject = question_data.get('subject', '')
                    db.edit_question(q_id, subject, question_text, answer_text, None, None)
                    
                    # 保存答案來源
                    import json
                    if sources:
                        try:
                            # 更新答案來源
                            with db._session_scope() as session:
                                from src.core.database import Question
                                session.query(Question).filter(Question.id == q_id).update({
                                    'answer_sources': json.dumps(sources, ensure_ascii=False)
                                })
                        except Exception as e:
                            print(f"保存答案來源失敗: {e}")
                    
                    return jsonify({
                        'success': True, 
                        'message': '答案已重新生成',
                        'answer': answer_text,
                        'sources': sources
                    })
                else:
                    return jsonify({'success': False, 'error': '答案生成失敗，請稍後重試'})
                    
            finally:
                loop.close()
                
        except Exception as e:
            app.logger.error(f"重新生成答案失敗: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'重新生成失敗: {str(e)}'})

    @app.route('/generate_solving_tips/<q_id>', methods=['POST'])
    def generate_solving_tips(q_id):
        """生成題目解題技巧"""
        try:
            # 獲取題目信息
            question_data = db.get_question_by_id(q_id)
            if not question_data:
                return jsonify({'success': False, 'error': '找不到指定的題目'})
            
            question_text = question_data.get('question_text', '')
            question_title = question_data.get('title', '')
            
            if not question_text:
                return jsonify({'success': False, 'error': '題目內容為空'})
            
            # 使用 asyncio 執行異步任務
            import asyncio
            # 檢查是否已有運行中的事件循環
            try:
                loop = asyncio.get_running_loop()
                # 如果有運行中的循環，直接使用 run_until_complete 可能會出錯
                # 所以我們使用 asyncio.run 在新的線程中執行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        gemini_client.generate_question_summary(question_text, question_title)
                    )
                    summary_result = future.result()
            except RuntimeError:
                # 如果沒有運行中的循環，直接使用 asyncio.run
                summary_result = asyncio.run(
                    gemini_client.generate_question_summary(question_text, question_title)
                )
            
            if summary_result and 'summary' in summary_result and 'solving_tips' in summary_result:
                # 儲存解題技巧到資料庫
                db.update_question_solving_tips(
                    q_id, 
                    summary_result['summary'], 
                    summary_result['solving_tips']
                )
                
                return jsonify({
                    'success': True, 
                    'message': '解題技巧已生成並儲存',
                    'summary': summary_result['summary'],
                    'solving_tips': summary_result['solving_tips']
                })
            else:
                return jsonify({'success': False, 'error': '解題技巧生成失敗，請稍後重試'})
                    
        except Exception as e:
            app.logger.error(f"生成解題技巧失敗: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'生成失敗: {str(e)}'})

    @app.route('/personal_notes')
    def personal_notes():
        return render_template('personal_notes.html')

    @app.route('/learning-summary/<int:doc_id>')
    def learning_summary_detail(doc_id):
        document = db.get_document_by_id(doc_id)
        if not document:
            abort(404)
        
        if not document.get('key_points_summary') and not document.get('quick_quiz'):
            flash('此文件尚未生成學習摘要與測驗', 'warning')
            return redirect(url_for('learning_summaries'))
            
        # 設定 markdown 配置使其輸出 Prism.js 相容的 class
        extension_configs = {
            'codehilite': {
                'guess_lang': False,
                'css_class': 'language-pseudocode',
                'use_pygments': False
            }
        }
        
        md = markdown.Markdown(
            extensions=['sane_lists', 'codehilite', 'fenced_code', 'tables'],
            extension_configs=extension_configs
        )
        document['content'] = md.convert(
            fix_markdown_numbering(document.get('content', ''))
        )
        md.reset()
        document['key_points_summary'] = md.convert(
            fix_markdown_numbering(document.get('key_points_summary', ''))
        )
        return render_template('learning_summary_detail.html', document=document)

    @app.route('/knowledge-graph')
    def knowledge_graph():
        return render_template('knowledge_graph.html')

    # --- API Routes ---
    @app.route('/api/questions')
    def api_questions():
        document_id = request.args.get('document_id', type=int)
        if document_id:
            questions = db.get_questions_by_document_id(document_id)
        else:
            questions = db.get_all_questions_with_source()
        return jsonify({'questions': questions})

    # --- Exports ---
    def export_md_content(questions_data):
        md_content = f"# 題庫匯出\n\n匯出時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        for i, q in enumerate(questions_data, 1):
            md_content += f"## 題目 {i} (ID: {q['id']})\n\n"
            md_content += f"**考科:** {q['subject']}\n"
            md_content += f"**來源:** {q.get('doc_title', '未知')}\n\n"
            md_content += f"### 題目內容\n\n{q.get('question_text', '')}\n\n"
            if q.get('answer_text'):
                md_content += f"### 參考答案\n\n{q.get('answer_text', '')}\n\n"
            if q.get('knowledge_points'):
                md_content += "### 相關知識點\n\n"
                for kp in q['knowledge_points']:
                    md_content += f"- {kp['name']}\n"
                md_content += "\n"
            if q.get('mindmap_code'):
                md_content += f"### 心智圖\n\n```mermaid\n{q['mindmap_code']}\n```\n\n"
            md_content += "---\n\n"
        return md_content

    @app.route('/export_question/<q_id>')
    def export_question(q_id):
        q = db.get_question_by_id(q_id)
        if not q:
            abort(404)
        md_content = export_md_content([q])
        return Response(
            md_content,
            mimetype='text/markdown',
            headers={'Content-Disposition': f'attachment; filename=question_{q_id}.md'}
        )

    @app.route('/batch_export', methods=['POST'])
    def batch_export():
        question_ids_str = request.form.getlist('question_ids')
        if not question_ids_str:
            flash('請選擇要匯出的題目')
            return redirect(url_for('questions'))
        
        questions_data = []
        for q_id in question_ids_str:
            q = db.get_question_by_id(q_id)
            if q:
                questions_data.append(q)
        
        md_content = export_md_content(questions_data)
        return Response(
            md_content,
            mimetype='text/markdown',
            headers={'Content-Disposition': 'attachment; filename=questions_batch_export.md'}
        )

    # # Print all registered routes for debugging
    # with app.test_request_context():
    #     print("\n--- Registered Routes ---")
    #     for rule in app.url_map.iter_rules():
    #         print(f"Endpoint: {rule.endpoint}, Methods: {rule.methods}, Rule: {rule.rule}")
    #     print("-------------------------\n")

    return app
