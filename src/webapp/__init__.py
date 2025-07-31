from flask import Flask, render_template, request, abort, redirect, url_for, flash, jsonify, Response
from werkzeug.utils import secure_filename
from ..core.database import DatabaseManager
from ..core.gemini_client import GeminiClient
from ..flows.flow_manager import FlowManager
from ..utils.file_processor import FileProcessor
import markdown
import os
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime
import re


def create_app(db_path: str = "./db.sqlite3"):
    db = DatabaseManager(db_path)
    gemini_client = GeminiClient()
    flow_manager = FlowManager(gemini_client, db)
    
    app = Flask(__name__)
    app.secret_key = 'your-secret-key-here'  # 在生產環境中請使用更安全的密鑰
    
    # 註冊自定義模板過濾器
    @app.template_filter('fromjson')
    def fromjson_filter(value):
        """JSON 字串轉 Python 物件的過濾器"""
        if not value:
            return []
        try:
            import json
            return json.loads(value)
        except:
            return []
    
    # 設定上傳檔案的限制
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'html', 'htm', 'md', 'jpg', 'jpeg', 'png', 'bmp', 'webp', 'gif'}

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
                    # 智慧處理：讓 AI 自動判斷內容類型和考科
                    flow_type = request.form.get('flow_type', 'smart')  # 預設使用智慧模式
                    suggested_subject = request.form.get('subject')  # 使用者建議的考科（可選）
                    
                    if flow_type == 'smart' or flow_type == 'content':
                        # 使用智慧內容處理
                        result = flow_manager.content_flow.process_file(file_path, filename, suggested_subject)
                    elif flow_type == 'answer':
                        result = flow_manager.answer_flow.process_file(file_path, filename, suggested_subject)
                    elif flow_type == 'mindmap':
                        result = flow_manager.mindmap_flow.process_file(file_path, filename, suggested_subject)
                    else:
                        # 預設使用智慧處理
                        result = flow_manager.content_flow.process_file(file_path, filename, suggested_subject)
                    
                    # 清理臨時檔案
                    os.unlink(file_path)
                    
                    # 根據結果顯示訊息
                    if result.get('success'):
                        questions_count = len(result.get('questions', []))
                        detected_subject = result.get('subject', '未知')
                        content_type = result.get('content_type', '內容')
                        confidence = result.get('confidence', 0)
                        
                        message = f'檔案處理完成！'
                        message += f'\\n偵測到考科：{detected_subject}'
                        message += f'\\n內容類型：{content_type}'
                        message += f'\\n處理了 {questions_count} 個項目'
                        if confidence:
                            message += f'\\n信心度：{confidence:.1%}'
                        
                        flash(message)
                    else:
                        flash(f'檔案處理失敗: {result.get("error", "未知錯誤")}')
                    
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
            suggested_subject = request.form.get('subject', '').strip()  # 允許空值
            flow_type = request.form.get('flow_type', 'smart')  # 預設使用智慧模式
            
            if not text_content:
                return jsonify({'error': '請輸入文字內容'}), 400
            
            # 建立臨時檔案
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_file:
                tmp_file.write(text_content)
                file_path = tmp_file.name
            
            try:
                # 選擇處理流程 - 預設使用智慧處理
                if flow_type == 'smart' or not flow_type:
                    # 使用智慧處理，讓 AI 自動判斷科目和內容類型
                    result = flow_manager.content_flow.process_file(file_path, 'user_input.txt', suggested_subject)
                elif flow_type == 'content':
                    result = flow_manager.content_flow.process_file(file_path, 'user_input.txt', suggested_subject)
                elif flow_type == 'info':
                    result = flow_manager.info_flow.process_file(file_path, 'user_input.txt', suggested_subject)
                elif flow_type == 'answer':
                    result = flow_manager.answer_flow.process_file(file_path, 'user_input.txt', suggested_subject)
                elif flow_type == 'mindmap':
                    result = flow_manager.mindmap_flow.process_file(file_path, 'user_input.txt', suggested_subject)
                else:
                    result = flow_manager.content_flow.process_file(file_path, 'user_input.txt', suggested_subject)
                
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

    @app.route('/process_url', methods=['POST'])
    def process_url():
        """處理網址內容"""
        try:
            
            url_content = request.form.get('url_content', '').strip()
            suggested_subject = request.form.get('subject', '').strip()  # 允許空值
            flow_type = request.form.get('flow_type', 'smart')
            
            if not url_content:
                return jsonify({'error': '請輸入網址'}), 400
            
            # 檢查 URL 格式
            if not (url_content.startswith('http://') or url_content.startswith('https://')):
                url_content = 'https://' + url_content
            
            try:
                # 獲取網址內容
                from ..utils.file_processor import FileProcessor
                web_content = FileProcessor.fetch_url_content_sync(url_content)

                if not web_content or len(web_content.strip()) < 10:
                    return jsonify({'error': '無法從該網址獲取有效內容'}), 400

                # 嘗試從內容中擷取標題作為檔名
                title = '網頁內容'
                first_line = web_content.strip().splitlines()[0] if web_content else ''
                m = re.match(r'^#\s*(.+)', first_line)
                if m:
                    candidate = m.group(1).strip()
                    if candidate:
                        title = candidate

                # 使用智慧內容處理，讓 AI 自動判斷科目和內容類型
                result = flow_manager.content_flow.complete_ai_processing(
                    web_content, title, suggested_subject, source_url=url_content
                )
                
                return jsonify({
                    'success': True,
                    'message': f'網址內容處理完成！處理了 {len(result.get("questions", []))} 道題目',
                    'questions_count': len(result.get("questions", []))
                })
                
            except Exception as e:
                return jsonify({'error': f'處理網址失敗: {str(e)}'}), 500
                
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
                'id': r[0],
                'subject': r[1],
                'title': r[2],
                'text': r[3],
                'answer': r[4],
                'difficulty': r[5],
                'guidance_level': r[6],
                'doc_title': r[7],
                'created_at': r[8],
            }
            for r in rows
        ]
        return render_template('questions.html', questions=questions, subject=subject)

    @app.route('/delete_question/<int:q_id>', methods=['POST'])
    def delete_question(q_id):
        """刪除單個問題"""
        try:
            # 這裡需要在資料庫中新增刪除方法
            db.cursor.execute('DELETE FROM questions WHERE id = ?', (q_id,))
            db.conn.commit()
            flash('題目已刪除')
        except Exception as e:
            flash(f'刪除失敗: {str(e)}')
        return redirect(url_for('questions'))

    @app.route('/batch_delete', methods=['POST'])
    def batch_delete():
        """批次刪除問題"""
        try:
            question_ids = request.form.getlist('question_ids')
            if question_ids:
                placeholders = ','.join(['?' for _ in question_ids])
                db.cursor.execute(f'DELETE FROM questions WHERE id IN ({placeholders})', question_ids)
                db.conn.commit()
                flash(f'已刪除 {len(question_ids)} 個題目')
            else:
                flash('請選擇要刪除的題目')
        except Exception as e:
            flash(f'批次刪除失敗: {str(e)}')
        return redirect(url_for('questions'))

    @app.route('/edit_question/<int:q_id>', methods=['GET', 'POST'])
    def edit_question(q_id):
        """編輯問題"""
        if request.method == 'POST':
            try:
                new_subject = request.form.get('subject')
                new_question = request.form.get('question_text')
                new_answer = request.form.get('answer_text')
                
                db.cursor.execute('''
                    UPDATE questions 
                    SET subject = ?, question_text = ?, answer_text = ? 
                    WHERE id = ?
                ''', (new_subject, new_question, new_answer, q_id))
                db.conn.commit()
                flash('題目已更新')
                return redirect(url_for('question_detail', q_id=q_id))
            except Exception as e:
                flash(f'更新失敗: {str(e)}')
        
        # GET 請求：顯示編輯表單
        q = db.get_question_by_id(q_id)
        if not q:
            abort(404)
        
        subjects = ['資料結構', '資訊管理', '資通網路與資訊安全', '資料庫應用', '其他']
        return render_template('edit_question.html', question=q, subjects=subjects)

    @app.route('/export_question/<int:q_id>')
    def export_question(q_id):
        """匯出單個問題為 Markdown"""
        try:
            q = db.get_question_by_id(q_id)
            if not q:
                abort(404)

            # Initialize Markdown converter with extensions for code highlighting
            md_converter = markdown.Markdown(extensions=[
                'codehilite',
                'fenced_code',
                'tables',
                'toc'
            ])
            
            # Generate Markdown content
            md_content = f"# {q['subject']} - 題目 #{q_id}\n\n"
            md_content += f"**來源文件:** {q.get('doc_title', '未知')}\n\n"
            md_content += f"**建立時間:** {q.get('created_at', '')}\n\n"
            
            # Convert question_text and answer_text to HTML using the Markdown converter
            question_html = md_converter.convert(q['question_text'] or '')
            answer_html = md_converter.convert(q['answer_text'] or '') if q['answer_text'] else ''

            md_content += f"## 題目\n\n{question_html}\n\n" # Use HTML for code highlighting
            if q['answer_text']:
                md_content += f"## 參考答案\n\n{answer_html}\n\n" # Use HTML for code highlighting
            
            # 加入知識點
            if q.get('knowledge_points'):
                md_content += "## 相關知識點\n\n"
                for kp in q['knowledge_points']:
                    md_content += f"- {kp['name']}\n"
                md_content += "\n"

            # Add mindmap data if available
            doc_id = q.get('document_id')
            if doc_id:
                document = db.get_document_by_id(doc_id)
                mindmap_data = document.get('mindmap') if document else None
                if mindmap_data:
                    md_content += f"## 心智圖\n\n```mermaid\n{mindmap_data}\n```\n\n"
            
            # 設定下載
            from flask import Response
            return Response(
                md_content,
                mimetype='text/markdown',
                headers={'Content-Disposition': f'attachment; filename=question_{q_id}.md'}
            )
            
        except Exception as e:
            flash(f'匯出失敗: {str(e)}')
            return redirect(url_for('questions'))

    @app.route('/knowledge/<int:id>')
    def knowledge_detail(id):
        """顯示單一知識點的詳細資訊，包括關聯題目和心智圖"""
        try:
            knowledge_point = db.get_knowledge_point_by_id(id)
            if not knowledge_point:
                abort(404)

            questions = db.get_questions_for_knowledge_point(id)
            
            # 獲取文檔 ID，優先從題目中獲取
            doc_id = None
            if questions:
                doc_id = questions[0]['document_id']

            mindmap_data = None
            if doc_id:
                document = db.get_document_by_id(doc_id)
                mindmap_data = document.get('mindmap') if document else None

            return render_template(
                'knowledge_detail.html',
                id=id,
                name=knowledge_point['name'],
                subject=knowledge_point['subject'],
                questions=questions,
                mindmap=mindmap_data
            )
        except Exception as e:
            flash(f"載入知識點詳情時發生錯誤: {e}", "danger")
            return redirect(url_for('knowledge_list'))

    @app.route('/batch_export', methods=['POST'])
    def batch_export():
        """批次匯出問題為 Markdown"""
        try:
            question_ids = request.form.getlist('question_ids')
            if not question_ids:
                flash('請選擇要匯出的題目')
                return redirect(url_for('questions'))
            
            # Initialize Markdown converter with extensions for code highlighting
            md_converter = markdown.Markdown(extensions=[
                'codehilite',
                'fenced_code',
                'tables',
                'toc'
            ])

            # 生成批次 Markdown 內容
            md_content = "# 題庫匯出\n\n"
            md_content += f"匯出時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            for i, q_id in enumerate(question_ids, 1):
                q = db.get_question_by_id(int(q_id))
                if q:
                    md_content += f"## 題目 {i} (ID: {q_id})\n\n"
                    md_content += f"**考科:** {q['subject']}\n\n"
                    md_content += f"**來源:** {q.get('doc_title', '未知')}\n\n"
                    
                    # Convert question_text and answer_text to HTML using the Markdown converter
                    question_html = md_converter.convert(q['question_text'] or '')
                    answer_html = md_converter.convert(q['answer_text'] or '') if q['answer_text'] else ''

                    md_content += f"### 題目內容\n\n{question_html}\n\n"
                    if q['answer_text']:
                        md_content += f"### 參考答案\n\n{answer_html}\n\n"
                    
                    if q.get('knowledge_points'):
                        md_content += "### 相關知識點\n\n"
                        for kp in q['knowledge_points']:
                            md_content += f"- {kp['name']}\n"
                        md_content += "\n"

                    # Add mindmap data if available
                    doc_id = q.get('document_id')
                    if doc_id:
                        document = db.get_document_by_id(doc_id)
                        mindmap_data = document.get('mindmap') if document else None
                        if mindmap_data:
                            md_content += f"### 心智圖\n\n```mermaid\n{mindmap_data}\n```\n\n"
                    
                    md_content += "---\n\n"
            
            from flask import Response
            return Response(
                md_content,
                mimetype='text/markdown',
                headers={'Content-Disposition': f'attachment; filename=questions_batch_export.md'}
            )
            
        except Exception as e:
            flash(f'批次匯出失敗: {str(e)}')
            return redirect(url_for('questions'))

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
        
        print(f"DEBUG: mindmap_code for question {q_id}: {q.get('mindmap_code')}")
        return render_template('question_detail.html', 
                             question=q, 
                             question_html=question_html,
                             answer_html=answer_html)

    @app.route('/knowledge')
    def knowledge_list():
        subject = request.args.get('subject')
        kp_map = db.get_all_knowledge_points_with_stats()
        if subject:
            kp_map = {subject: kp_map.get(subject, [])}
        return render_template('knowledge.html', kp_map=kp_map, subject=subject)

    @app.route('/documents')
    def documents_list():
        """顯示所有原始文件列表"""
        try:
            documents = db.get_all_documents()
            # 轉換為字典格式以便在模板中使用
            docs_list = []
            for doc in documents:
                docs_list.append({
                    'id': doc[0],
                    'title': doc[1],
                    'content': doc[2][:200] + '...' if len(doc[2]) > 200 else doc[2],  # 預覽內容
                    'type': doc[3],
                    'subject': doc[4],
                    'file_path': doc[5],
                    'source': doc[6],  # 新增 source 欄位
                    'created_at': doc[7]  # 更新索引
                })
            return render_template('documents_list.html', documents=docs_list)
        except Exception as e:
            flash(f'載入文件列表時發生錯誤: {str(e)}', 'danger')
            return redirect(url_for('index'))

    @app.route('/document/<int:doc_id>')
    def document_detail(doc_id):
        """檢視文件詳情"""
        document = db.get_document_by_id(doc_id)
        if not document:
            abort(404)
        return render_template('document_detail.html', document=document)

    @app.route('/original_document/<int:doc_id>')
    def original_document(doc_id):
        """檢視原始文件內容"""
        document = db.get_document_by_id(doc_id)
        if not document:
            abort(404)
        
        # 使用 Markdown 渲染原始內容
        md = markdown.Markdown(extensions=[
            'codehilite',
            'fenced_code',
            'tables',
            'toc'
        ])
        
        original_content = document.get('original_content') or document.get('content', '')
        original_html = md.convert(original_content)
        
        return render_template('original_document.html', 
                             document=document, 
                             original_html=original_html)

    @app.route('/api/questions')
    def api_questions():
        """API端點：取得問題列表"""
        document_id = request.args.get('document_id', type=int)
        
        if document_id:
            # 根據文件 ID 取得問題
            questions = db.get_questions_by_document_id(document_id)
        else:
            # 取得所有問題
            questions = db.get_all_questions_with_source()
        
        return jsonify({
            'questions': [
                {
                    'id': q[0] if len(q) > 0 else None,
                    'title': q[2] if len(q) > 2 else f'Q{q[0]}',
                    'question_text': q[3] if len(q) > 3 else '',
                    'subject': q[1] if len(q) > 1 else '未分類'
                } for q in questions
            ]
        })

    @app.route('/summary-quiz')
    def summary_quiz():
        """學習摘要測驗頁面"""
        # 取得所有知識點作為測驗選項
        knowledge_points = db.get_all_knowledge_points()
        return render_template('summary_quiz.html', knowledge_points=knowledge_points)

    @app.route('/generate-quiz', methods=['POST'])
    def generate_quiz():
        """生成測驗題目"""
        try:
            # 取得選擇的知識點
            selected_knowledge = request.json.get('knowledge_points', [])
            quiz_type = request.json.get('quiz_type', 'multiple_choice')
            num_questions = int(request.json.get('num_questions', 5))
            
            if not selected_knowledge:
                return jsonify({'error': '請選擇至少一個知識點'}), 400
            
            # 從資料庫取得相關的題目和知識點內容
            knowledge_content = []
            for kp_id in selected_knowledge:
                kp = db.get_knowledge_point_by_id(kp_id)
                if kp:
                    # 取得該知識點相關的題目
                    related_questions = db.get_questions_by_knowledge_point(kp_id)
                    knowledge_content.append({
                        'name': kp[1],  # 假設 name 在索引 1
                        'description': kp[2] if len(kp) > 2 else '',  # 假設 description 在索引 2
                        'related_questions': related_questions
                    })
            
            # 使用 Gemini AI 生成測驗題目
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                quiz_data = loop.run_until_complete(
                    flow_manager.generate_quiz_from_knowledge(
                        knowledge_content, quiz_type, num_questions
                    )
                )
                return jsonify(quiz_data)
            finally:
                loop.close()
                
        except Exception as e:
            return jsonify({'error': f'生成測驗時發生錯誤: {str(e)}'}), 500

    @app.route('/knowledge-graph')
    def knowledge_graph():
        """知識圖譜視覺化頁面"""
        # 取得所有知識點和它們的關聯
        knowledge_points = db.get_all_knowledge_points()
        # 這裡後續需要實作知識點之間的關聯邏輯
        return render_template('knowledge_graph.html', knowledge_points=knowledge_points)

    @app.route('/learning-summaries')
    def learning_summaries():
        """學習摘要與測驗列表頁面"""
        # 取得所有包含摘要和測驗的文件
        documents = db.get_documents_with_summaries()
        return render_template('learning_summaries.html', documents=documents)

    @app.route('/learning-summary/<int:doc_id>')
    def learning_summary_detail(doc_id):
        """單一文件的學習摘要與測驗頁面"""
        document = db.get_document_by_id(doc_id)
        if not document:
            abort(404)
        
        # 確保文件有摘要或測驗內容
        if not document.get('key_points_summary') and not document.get('quick_quiz'):
            flash('此文件尚未生成學習摘要與測驗', 'warning')
            return redirect(url_for('learning_summaries'))
            
        import markdown
        md = markdown.Markdown(extensions=[
            'codehilite',
            'fenced_code',
            'tables',
            'toc'
        ])
        document['content'] = md.convert(document.get('content', ''))
        document['key_points_summary'] = md.convert(document.get('key_points_summary', ''))
        return render_template('learning_summary_detail.html', document=document)
        
    return app
