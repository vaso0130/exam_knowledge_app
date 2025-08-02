

import os
import json
import tempfile
import asyncio
import markdown
import re
from ..utils.markdown_utils import format_answer_text

def fix_markdown_numbering(text: str) -> str:
    """只修正明顯重複的阿拉伯數字編號問題，保持所有其他格式不變"""
    if not text:
        return text
    
    lines = text.split('\n')
    result_lines = []
    
    for i, line in enumerate(lines):
        # 檢查是否為阿拉伯數字編號行
        arabic_match = re.match(r'^(\s*)(\d+)\.\s+(.+)$', line)
        
        if arabic_match:
            indent, old_number, content = arabic_match.groups()
            
            # 只有在明確發現重複編號時才修正
            should_fix = False
            correct_number = int(old_number)
            
            # 向前查找同層級的最近編號
            for j in range(i-1, max(-1, i-5), -1):
                if j < 0 or not lines[j].strip():
                    continue
                    
                prev_match = re.match(r'^(\s*)(\d+)\.\s+', lines[j])
                if prev_match:
                    prev_indent, prev_number = prev_match.groups()
                    
                    # 如果是同層級
                    if len(prev_indent) == len(indent):
                        expected_number = int(prev_number) + 1
                        # 只有當編號不連續且不是正確的連續編號時才修正
                        if int(old_number) == int(prev_number) and int(old_number) != expected_number:
                            should_fix = True
                            correct_number = expected_number
                        break
            
            if should_fix:
                result_lines.append(f"{indent}{correct_number}. {content}")
            else:
                result_lines.append(line)
        else:
            result_lines.append(line)
    
    return '\n'.join(result_lines)
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
            
            from ..utils.file_processor import FileProcessor
            web_content = FileProcessor.fetch_url_content_sync(url_content)

            if not web_content or len(web_content.strip()) < 10:
                return jsonify({'error': '無法從該網址獲取有效內容'}), 400

            title = url_content.split('//')[-1].split('/')[0]

            result = flow_manager.content_flow.complete_ai_processing(
                web_content, title, suggested_subject, source_url=url_content
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
            app.logger.error(f"URL processing failed: {e}", exc_info=True)
            return jsonify({'error': f'系統錯誤: {str(e)}'}), 500

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
                
                db.edit_question(q_id, new_subject, new_question, new_answer)
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
        
        md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables'])
        question_html = md.convert(q.get('question_text', ''))
        
        # 處理答案文本 - 暫時停用修正，測試原始渲染效果
        answer_text = q.get('answer_text', '')
        # 暫時停用編號修正
        # if answer_text:
        #     answer_text = fix_markdown_numbering(answer_text)
        answer_html = md.convert(answer_text)
        
        return render_template('question_detail.html', 
                             question=q, 
                             question_html=question_html,
                             answer_html=answer_html,
                             mindmap_code=q.get('mindmap_code'))

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

        md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables'])
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
            
        md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables'])
        document['content'] = md.convert(document.get('content', ''))
        document['key_points_summary'] = md.convert(document.get('key_points_summary', ''))
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
