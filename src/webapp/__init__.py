from flask import Flask, render_template, request, abort, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from ..core.database import DatabaseManager
from ..core.gemini_client import GeminiClient
from ..flows.flow_manager import FlowManager
from ..utils.file_processor import FileProcessor
import markdown
import os
import tempfile
from pathlib import Path


def create_app(db_path: str = "./db.sqlite3"):
    db = DatabaseManager(db_path)
    gemini_client = GeminiClient()
    flow_manager = FlowManager(gemini_client, db)
    
    app = Flask(__name__)
    app.secret_key = 'your-secret-key-here'  # 在生產環境中請使用更安全的密鑰
    
    # 設定上傳檔案的限制
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'html', 'htm', 'md'}

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
                filename = secure_filename(file.filename)
                
                # 建立臨時檔案
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp_file:
                    file.save(tmp_file.name)
                    file_path = tmp_file.name
                
                try:
                    # 選擇處理流程
                    subject = request.form.get('subject', '資料結構')
                    flow_type = request.form.get('flow_type', 'content')  # content, info, answer, mindmap
                    
                    if flow_type == 'content':
                        result = flow_manager.content_flow.process_file(file_path, filename, subject)
                    elif flow_type == 'info':
                        result = flow_manager.info_flow.process_file(file_path, filename, subject)
                    elif flow_type == 'answer':
                        result = flow_manager.answer_flow.process_file(file_path, filename, subject)
                    elif flow_type == 'mindmap':
                        result = flow_manager.mindmap_flow.process_file(file_path, filename, subject)
                    else:
                        result = flow_manager.content_flow.process_file(file_path, filename, subject)
                    
                    # 清理臨時檔案
                    os.unlink(file_path)
                    
                    flash(f'檔案處理完成！處理了 {len(result.get("questions", []))} 道題目')
                    return redirect(url_for('questions'))
                    
                except Exception as e:
                    # 清理臨時檔案
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                    flash(f'檔案處理失敗: {str(e)}')
                    return redirect(request.url)
            else:
                flash('不支援的檔案格式')
                return redirect(request.url)
        
        subjects = ['資料結構', '資訊管理', '資通網路與資訊安全', '資料庫應用']
        return render_template('upload.html', subjects=subjects)

    @app.route('/process_text', methods=['POST'])
    def process_text():
        """處理直接輸入的文字內容"""
        try:
            text_content = request.form.get('text_content', '').strip()
            subject = request.form.get('subject', '資料結構')
            flow_type = request.form.get('flow_type', 'content')
            
            if not text_content:
                return jsonify({'error': '請輸入文字內容'}), 400
            
            # 建立臨時檔案
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_file:
                tmp_file.write(text_content)
                file_path = tmp_file.name
            
            try:
                # 選擇處理流程
                if flow_type == 'content':
                    result = flow_manager.content_flow.process_file(file_path, 'user_input.txt', subject)
                elif flow_type == 'info':
                    result = flow_manager.info_flow.process_file(file_path, 'user_input.txt', subject)
                elif flow_type == 'answer':
                    result = flow_manager.answer_flow.process_file(file_path, 'user_input.txt', subject)
                elif flow_type == 'mindmap':
                    result = flow_manager.mindmap_flow.process_file(file_path, 'user_input.txt', subject)
                else:
                    result = flow_manager.content_flow.process_file(file_path, 'user_input.txt', subject)
                
                # 清理臨時檔案
                os.unlink(file_path)
                
                return jsonify({
                    'success': True,
                    'message': f'處理完成！處理了 {len(result.get("questions", []))} 道題目',
                    'questions_count': len(result.get("questions", []))
                })
                
            except Exception as e:
                # 清理臨時檔案
                if os.path.exists(file_path):
                    os.unlink(file_path)
                return jsonify({'error': f'處理失敗: {str(e)}'}), 500
                
        except Exception as e:
            return jsonify({'error': f'系統錯誤: {str(e)}'}), 500

    @app.route('/questions')
    def questions():
        subject = request.args.get('subject')
        if subject:
            rows = db.get_questions_by_subject(subject)
        else:
            rows = db.get_all_questions_with_source()
        questions = [
            {
                'id': r[0], 'subject': r[1], 'text': r[2],
                'answer': r[3], 'doc_title': r[4], 'created_at': r[5]
            } for r in rows
        ]
        return render_template('questions.html', questions=questions, subject=subject)

    @app.route('/question/<int:q_id>')
    def question_detail(q_id):
        q = db.get_question_by_id(q_id)
        if not q:
            abort(404)
        
        # 使用更好的 Markdown 渲染，支援程式碼高亮
        md = markdown.Markdown(extensions=[
            'codehilite',
            'fenced_code',
            'tables',
            'toc'
        ])
        
        question_html = md.convert(q['question_text'] or '')
        answer_html = md.convert(q['answer_text'] or '') if q['answer_text'] else ''
        
        return render_template('question_detail.html', 
                             question=q, 
                             question_html=question_html,
                             answer_html=answer_html)

    @app.route('/knowledge')
    def knowledge():
        subject = request.args.get('subject')
        kp_map = db.get_all_knowledge_points_with_stats()
        if subject:
            kp_map = {subject: kp_map.get(subject, [])}
        return render_template('knowledge.html', kp_map=kp_map, subject=subject)

    @app.route('/knowledge/<int:kp_id>')
    def knowledge_detail(kp_id):
        info = db.cursor.execute('SELECT name, subject FROM knowledge_points WHERE id = ?', (kp_id,)).fetchone()
        if not info:
            abort(404)
        name, subject = info
        rows = db.get_questions_for_knowledge_point(kp_id)
        questions = [
            {
                'id': r[0], 'subject': r[1], 'text': r[2],
                'answer': r[3], 'doc_title': r[4], 'created_at': r[5]
            } for r in rows
        ]
        return render_template('knowledge_detail.html', name=name, subject=subject, questions=questions)

    return app
