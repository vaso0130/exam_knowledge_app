import os
import json
import tempfile
import asyncio
import markdown
import re

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
from flask import Flask, render_template, request, abort, redirect, url_for, flash, jsonify, Response, g

from ..core.database import DatabaseManager
from ..core.gemini_client import GeminiClient
from ..flows.flow_manager import FlowManager
from .async_processor import AsyncProcessor

def get_client_ip():
    """獲取客戶端真實IP地址"""
    # 檢查是否通過代理伺服器
    if 'X-Forwarded-For' in request.headers:
        # X-Forwarded-For 可能包含多個IP，取第一個
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    elif 'X-Real-IP' in request.headers:
        return request.headers['X-Real-IP']
    else:
        return request.remote_addr

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
    
    # v3.1 點數系統和內容驗證
    from ..utils.points_manager import PointsManager
    from ..utils.content_validator import ContentValidator
    from ..utils.points_decorator import add_points_info_to_template
    points_manager = PointsManager(db)
    content_validator = ContentValidator(gemini_client, db)
    
    # 將 points_manager 存儲到 app 中供裝飾器使用
    app._points_manager = points_manager
    
    # 註冊模板上下文處理器
    app.context_processor(add_points_info_to_template())

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

    @app.template_filter('markdown')
    def markdown_filter(text):
        """將 Markdown 文本轉換為 HTML"""
        if not text:
            return ""
        
        # 修正編號格式，確保 Markdown 可以正確渲染
        text = fix_markdown_numbering(text)
        
        # 配置 Markdown 解析器
        md = markdown.Markdown(
            extensions=[
                'tables',           # 支援表格
                'fenced_code',      # 支援圍欄式程式碼區塊
                'codehilite',       # 支援程式碼高亮
                'toc',              # 支援目錄
                'nl2br'             # 換行轉為 <br>
            ],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight',
                    'use_pygments': False  # 使用前端的 Prism.js 進行高亮
                }
            }
        )
        
        # 轉換為 HTML
        html = md.convert(text)
        
        # 返回安全的 HTML（Flask 會自動處理 Markup）
        from markupsafe import Markup
        return Markup(html)

    @app.template_filter('format_datetime')
    def format_datetime_filter(value, format='%Y-%m-%d %H:%M'):
        """Formats an ISO datetime string into a more readable format."""
        if not value:
            return ""
        try:
            # Parse the ISO format string
            dt = datetime.fromisoformat(value)
            # Return the formatted string
            return dt.strftime(format)
        except (ValueError, TypeError):
            # If parsing fails, return the original value
            return value

    # --- Authentication Helpers ---
    @app.before_request
    def load_logged_in_user():
        """在每個請求前檢查用戶登入狀態"""
        user_id = request.cookies.get('user_id')
        if user_id:
            try:
                with db._session_scope() as session:
                    from ..core.database import User
                    user = session.query(User).filter(User.id == int(user_id)).first()
                    if user:
                        g.current_user = {
                            'id': user.id,
                            'username': user.username,
                            'role': user.role
                        }
                    else:
                        g.current_user = None
            except:
                g.current_user = None
        else:
            g.current_user = None
        
        # 檢查是否需要登入才能訪問（排除登入頁面本身）
        if not g.current_user and request.endpoint not in ['login', 'static', 'check_user']:
            return redirect(url_for('login'))

    # Register Blueprints
    from .main_blueprint import main_bp
    from .auth_blueprint import auth_bp
    # from .admin_blueprint import admin_bp  # 🔒 移除管理藍圖 - 僅通過獨立管理伺服器訪問
    from .notes_blueprint import notes_bp # 📝 Import the new notes blueprint

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    # app.register_blueprint(admin_bp, url_prefix='/admin')  # 🔒 禁用主程式中的管理路由
    app.register_blueprint(notes_bp, url_prefix='/notes') # 📝 Register the notes blueprint

    # --- Routes ---

    @app.route('/check-user', methods=['POST'])
    def check_user():
        """檢查用戶是否存在"""
        data = request.get_json()
        username = data.get('username', '').strip()
        
        if not username:
            return jsonify({'exists': False})
        
        try:
            with db._session_scope() as session:
                from ..core.database import User
                user = session.query(User).filter(User.username == username).first()
                return jsonify({'exists': user is not None})
        except:
            return jsonify({'exists': False})

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """登入頁面"""
        # 如果已經登入，直接跳轉到首頁
        if g.current_user:
            return redirect(url_for('index'))
            
        if request.method == 'POST':
            action = request.form.get('action', 'login')
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
            if not username or not password:
                flash('請輸入用戶名和密碼')
                return render_template('login.html')
            
            if action == 'register':
                # 新用戶註冊
                return handle_user_registration(username, password)
            else:
                # 現有用戶登入
                return handle_user_login(username, password)
                
        return render_template('login.html')

    def handle_user_login(username: str, password: str):
        """處理用戶登入"""
        try:
            with db._session_scope() as session:
                from ..core.database import User
                user = session.query(User).filter(User.username == username).first()
                
                if not user:
                    flash('用戶不存在')
                    return render_template('login.html')
                
                # 驗證密碼 - 使用與管理系統相同的方式
                from ..core.security_manager import SecurityManager
                security_manager = SecurityManager(db)
                if not security_manager.verify_password(password, user.password_hash):
                    flash('密碼錯誤，請重新輸入')
                    return render_template('login.html')
                
                # 設定登入 cookie
                resp = redirect(url_for('index'))
                resp.set_cookie('user_id', str(user.id), max_age=30*24*60*60)  # 30天
                flash(f'歡迎回來，{user.username}！')
                return resp
                
        except Exception as e:
            app.logger.error(f"登入錯誤: {e}")
            flash('登入時發生錯誤，請稍後再試')
            return render_template('login.html')

    def handle_user_registration(username: str, password: str):
        """處理用戶註冊"""
        fullname = request.form.get('fullname', '').strip()
        email = request.form.get('email', '').strip()
        invite_code = request.form.get('invite_code', '').strip()
        
        # 獲取客戶端資訊
        client_ip = get_client_ip()
        user_agent = request.headers.get('User-Agent', '')
        
        # 使用SecurityManager驗證邀請碼
        from ..core.security_manager import SecurityManager
        security_manager = SecurityManager(db)
        
        role = security_manager.validate_invitation_code(
            invite_code, 
            ip_address=client_ip, 
            user_agent=user_agent, 
            username_attempted=username
        )
        if not role:
            flash('邀請碼無效，請檢查後重新輸入')
            return render_template('login.html')
        
        if not fullname or not email:
            flash('請填寫完整的註冊資訊')
            return render_template('login.html')
        
        # 驗證密碼長度
        if len(password) < 6:
            flash('密碼長度至少6個字元')
            return render_template('login.html')
        
        try:
            with db._session_scope() as session:
                from ..core.database import User
                
                # 檢查用戶名是否已存在
                existing_user = session.query(User).filter(User.username == username).first()
                if existing_user:
                    flash('用戶名已存在，請選擇其他用戶名')
                    return render_template('login.html')
                
                # 檢查信箱是否已存在
                existing_email = session.query(User).filter(User.email == email).first()
                if existing_email:
                    flash('此信箱已被註冊，請使用其他信箱')
                    return render_template('login.html')
                
                # 創建新用戶
                password_hash = security_manager.hash_password(password)
                
                user = User(
                    username=username, 
                    password_hash=password_hash, 
                    role=role,
                    email=email,
                    full_name=fullname
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                
                # 設定登入 cookie
                resp = redirect(url_for('index'))
                resp.set_cookie('user_id', str(user.id), max_age=30*24*60*60)  # 30天
                
                role_name = '管理者' if role == 'admin' else '檢視者'
                flash(f'歡迎 {fullname}！帳號已成功創建，您的角色是：{role_name}')
                return resp
                
        except Exception as e:
            app.logger.error(f"註冊錯誤: {e}")
            flash('註冊時發生錯誤，請稍後再試')
            return render_template('login.html')

    @app.route('/logout')
    def logout():
        """登出"""
        resp = redirect(url_for('index'))
        resp.delete_cookie('user_id')
        flash('已成功登出')
        return resp

    @app.route('/')
    def index():
        subjects = db.get_all_subjects()
        return render_template('index.html', subjects=subjects)

    @app.route('/upload', methods=['GET', 'POST'])
    def upload_file():
        # v3.1: 需要登入才能上傳
        current_user = getattr(g, 'current_user', None)
        if not current_user:
            flash('請先登入才能上傳檔案')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            # v3.1: 檢查用戶點數和禁用狀態（僅對 viewer）
            if current_user.get('role') == 'viewer':
                user_status = points_manager.get_user_points(current_user['id'])
                if user_status.get("is_banned"):
                    flash(f'❌ 您的帳戶已被暫時禁用至 {user_status["ban_until"]}')
                    return redirect(request.url)
            
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
                    
                    # v3.1: 首先進行內容驗證
                    from ..utils.file_processor import FileProcessor
                    extracted_content, input_type = FileProcessor.process_input(str(file_path))
                    
                    # 驗證內容是否合法
                    validation_result = content_validator.validate_content_sync(
                        document_id=0,  # 暫時使用0，稍後會更新
                        content=extracted_content[:2000],  # 只取前2000字符驗證
                        user_id=current_user['id']
                    )
                    
                    if not validation_result["is_valid"]:
                        # 內容不合法，對 viewer 應用懲罰
                        if current_user.get('role') == 'viewer':
                            penalty_result = points_manager.apply_penalty(
                                user_id=current_user['id'],
                                document_id=0,
                                validation_details=validation_result["details"]
                            )
                            penalty_message = "您的帳戶已被暫時禁用48小時。"
                        else:
                            penalty_message = "管理員帳戶不受懲罰限制。"
                        
                        # 刪除檔案
                        if os.path.exists(file_path):
                            os.unlink(file_path)
                        
                        flash(f'❌ 上傳內容不符合學習用途要求，已被拒絕。{validation_result["reason"]}。{penalty_message}')
                        return redirect(request.url)
                    
                    suggested_subject = request.form.get('subject')
                    use_async = request.form.get('async_processing') == 'on'
                    
                    if use_async:
                        # 非同步處理
                        job_id = async_processor.submit_job(
                            'content_processing',
                            file_path=str(file_path),
                            filename=original_filename,
                            subject=suggested_subject or '',
                            uploader_id=current_user['id'],
                            uploader_name=current_user['username']
                        )
                        flash('✅ 檔案已提交處理，請稍候查看結果')
                        return redirect(url_for('job_status', job_id=job_id))
                    else:
                        # 同步處理
                        result = flow_manager.content_flow.process_file(
                            str(file_path), 
                            original_filename, 
                            suggested_subject,
                            uploader_id=current_user['id'],
                            uploader_name=current_user['username']
                        )
                        
                        if result.get('success'):
                            # 更新驗證記錄的 document_id
                            if result.get('document_id'):
                                with db._session_scope() as session:
                                    from ..core.database import ContentValidation
                                    validation_record = session.query(ContentValidation)\
                                        .filter(ContentValidation.document_id == 0)\
                                        .filter(ContentValidation.user_id == current_user['id'])\
                                        .order_by(ContentValidation.created_at.desc()).first()
                                    
                                    if validation_record:
                                        validation_record.document_id = result['document_id']
                                        session.commit()
                            
                            flash(result.get('message', '✅ 檔案處理完成！'))
                        else:
                            flash(f'❌ 檔案處理失敗: {result.get("error", "未知錯誤")}')
                        
                        return redirect(url_for('questions'))
                    
                except Exception as e:
                    app.logger.error(f"File processing failed: {e}", exc_info=True)
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                    flash(f'❌ 檔案處理失敗: {str(e)}')
                    return redirect(request.url)
            else:
                flash('❌ 不支援的檔案格式')
                return redirect(request.url)
        
        # GET request - 顯示上傳表單，僅對 viewer 顯示點數資訊
        user_points = None
        if current_user and current_user.get('role') == 'viewer':
            user_points = points_manager.get_user_points(current_user['id'])
        
        subjects = db.get_all_subjects()
        return render_template('upload.html', subjects=subjects, user_points=user_points)

    @app.route('/process_text', methods=['POST'])
    def process_text():
        # v3.1: 需要登入才能處理文字
        current_user = getattr(g, 'current_user', None)
        if not current_user:
            return jsonify({'error': '請先登入才能處理文字'}), 401
        
        try:
            text_content = request.form.get('text_content', '').strip()
            suggested_subject = request.form.get('subject', '').strip()
            
            if not text_content:
                return jsonify({'error': '請輸入文字內容'}), 400

            # v3.1: 檢查用戶點數和禁用狀態（僅對 viewer）
            if current_user.get('role') == 'viewer':
                user_status = points_manager.get_user_points(current_user['id'])
                if user_status.get("is_banned"):
                    return jsonify({'error': f'您的帳戶已被暫時禁用至 {user_status["ban_until"]}'}), 403
            
            # 對所有用戶進行內容驗證
            validation_result = content_validator.validate_content_sync(
                document_id=0,  # 暫時使用0
                content=text_content[:2000],
                user_id=current_user['id']
            )
            
            if not validation_result["is_valid"]:
                # 內容不合法，僅對 viewer 應用懲罰
                if current_user.get('role') == 'viewer':
                    penalty_result = points_manager.apply_penalty(
                        user_id=current_user['id'],
                        document_id=0,
                        validation_details=validation_result["details"]
                    )
                    penalty_message = "您的帳戶已被暫時禁用48小時。"
                else:
                    penalty_message = "管理員帳戶不受懲罰限制。"
                
                return jsonify({
                    'error': f'內容不符合學習用途要求，已被拒絕。{validation_result["reason"]}。{penalty_message}'
                }), 400
            
            # v3.1: 檢查並扣除處理費用（僅對 viewer）
            if current_user.get('role') == 'viewer':
                # 檢查並扣除處理費用（假設為中等考題生成）
                can_afford = points_manager.can_afford(current_user['id'], 'generate_quiz', question_count=15)
                if not can_afford['can_afford']:
                    return jsonify({
                        'error': f'點數不足。需要約 {can_afford["cost"]} 點，目前只有 {can_afford["current_points"]} 點'
                    }), 400

            result = flow_manager.content_flow.complete_ai_processing(
                text_content, 'user_input.txt', suggested_subject,
                uploader_id=current_user['id'],
                uploader_name=current_user['username']
            )
            
            if result.get('success'):
                # 對 viewer 扣除實際點數
                if current_user.get('role') == 'viewer':
                    actual_questions = len(result.get("questions", []))
                    deduct_result = points_manager.deduct_points(
                        user_id=current_user['id'],
                        action_type='generate_quiz',
                        question_count=actual_questions,
                        description=f'處理文字並生成{actual_questions}題考題'
                    )
                
                response = {
                    'success': True,
                    'message': result.get('message', '處理完成！'),
                    'questions_count': len(result.get("questions", []))
                }
                
                # 添加點數資訊
                if current_user.get('role') == 'viewer' and 'deduct_result' in locals():
                    response['points_deducted'] = deduct_result['points_deducted']
                    response['points_remaining'] = deduct_result['points_remaining']
                
                return jsonify(response)
            else:
                return jsonify({'error': f'處理失敗: {result.get("error", "未知錯誤")}'}), 500
                
        except Exception as e:
            app.logger.error(f"Text processing failed: {e}", exc_info=True)
            return jsonify({'error': f'系統錯誤: {str(e)}'}), 500

    @app.route('/process_url', methods=['POST'])
    def process_url():
        # v3.1: 需要登入才能處理網址
        current_user = getattr(g, 'current_user', None)
        if not current_user:
            return jsonify({'error': '請先登入才能處理網址'}), 401
        
        # v3.1: 檢查用戶點數和禁用狀態（僅對 viewer）
        if current_user.get('role') == 'viewer':
            user_status = points_manager.get_user_points(current_user['id'])
            if user_status.get("is_banned"):
                return jsonify({'error': f'您的帳戶已被暫時禁用至 {user_status["ban_until"]}'}), 403
        
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
        # v3.1: 檢查權限 - 只有管理員可以刪除題目
        current_user = getattr(g, 'current_user', None)
        if not current_user:
            flash('請先登入才能刪除題目')
            return redirect(url_for('login'))
        
        if current_user.get('role') != 'admin':
            flash('只有管理員可以刪除題目')
            return redirect(url_for('questions'))
        
        try:
            db.delete_question(q_id)
            flash('題目已刪除')
        except Exception as e:
            app.logger.error(f"Deleting question {q_id} failed: {e}", exc_info=True)
            flash(f'刪除失敗: {str(e)}')
        return redirect(url_for('questions'))

    @app.route('/batch_delete', methods=['POST'])
    def batch_delete():
        # v3.1: 檢查權限 - 只有管理員可以批次刪除題目
        current_user = getattr(g, 'current_user', None)
        if not current_user:
            flash('請先登入才能刪除題目')
            return redirect(url_for('login'))
        
        if current_user.get('role') != 'admin':
            flash('只有管理員可以刪除題目')
            return redirect(url_for('questions'))
        
        try:
            question_ids_str = request.form.getlist('question_ids')
            if not question_ids_str:
                flash('請選擇要刪除的題目')
                return redirect(url_for('questions'))
            
            questions_data = []
            for q_id in question_ids_str:
                q = db.get_question_by_id(q_id)
                if q:
                    questions_data.append(q)
            
            db.batch_delete_questions(question_ids_str)
            flash(f'已刪除 {len(question_ids_str)} 個題目')
        except Exception as e:
            app.logger.error(f"Batch deleting questions failed: {e}", exc_info=True)
            flash(f'批次刪除失敗: {str(e)}')
        return redirect(url_for('questions'))

    @app.route('/edit_question/<q_id>', methods=['GET', 'POST'])
    def edit_question(q_id):
        # v3.1: 檢查權限 - 只有管理員可以編輯題目
        current_user = getattr(g, 'current_user', None)
        if not current_user:
            flash('請先登入才能編輯題目')
            return redirect(url_for('login'))
        
        if current_user.get('role') != 'admin':
            flash('只有管理員可以編輯題目')
            return redirect(url_for('question_detail', q_id=q_id))
        
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
        
        # 檢查用戶是否已為此題目建立筆記
        related_notes = []
        if g.current_user:
            # 從 NoteAIAnalysis 表中尋找引用此問題的筆記
            from .notes_blueprint import note_manager
            try:
                from sqlalchemy import text
                with note_manager.db_manager.get_db_session() as session:
                    query = text("""
                    SELECT un.id, un.title, un.created_at 
                    FROM note_ai_analysis naa 
                    JOIN user_notes un ON naa.note_id = un.id 
                    WHERE naa.analysis_type = 'source_question' 
                    AND un.user_id = :user_id 
                    AND naa.result LIKE :question_id_pattern
                    ORDER BY un.created_at DESC
                    """)
                    
                    result = session.execute(query, {
                        'user_id': g.current_user['id'],
                        'question_id_pattern': f'%"id": "{q_id}"%'
                    })
                    
                    related_notes = [
                        {
                            'id': row[0],
                            'title': row[1],
                            'created_at': row[2]
                        } 
                        for row in result
                    ]
            except Exception as e:
                print(f"Error fetching related notes: {e}")
                
        # 解析答案來源，檢查是否來自筆記
        source_note_id = None
        if q.get('answer_sources') and '筆記：' in q['answer_sources'] and '(ID:' in q['answer_sources']:
            try:
                source_note_id = q['answer_sources'].split('(ID:')[1].split(')')[0].strip()
                # 驗證筆記存在
                if source_note_id:
                    # 如果來源筆記不在已關聯筆記中，可能需要特殊處理
                    source_note_exists = False
                    for note in related_notes:
                        if note['id'] == source_note_id:
                            source_note_exists = True
                            break
                    
                    # 如果來源筆記不在關聯筆記中，可能需要從資料庫中獲取
                    if not source_note_exists:
                        try:
                            # 取得來源筆記信息（不需要檢查用戶權限，因為這是公開顯示的）
                            with note_manager.db_manager.get_db_session() as session:
                                note_query = text("""
                                SELECT id, title, created_at FROM user_notes WHERE id = :note_id
                                """)
                                note_result = session.execute(note_query, {'note_id': source_note_id}).fetchone()
                                
                                if note_result:
                                    related_notes.append({
                                        'id': note_result[0],
                                        'title': note_result[1],
                                        'created_at': note_result[2],
                                        'is_source': True
                                    })
                        except Exception as e:
                            print(f"Error fetching source note: {e}")
            except Exception as e:
                print(f"Error parsing source note ID: {e}")
        
        return render_template('question_detail.html', 
                             question=q, 
                             question_html=question_html,
                             answer_html=answer_html,
                             mindmap_code=q.get('mindmap_code'),
                             question_summary=q.get('question_summary'),
                             solving_tips=q.get('solving_tips'),
                             related_notes=related_notes)

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

    @app.route('/document/<doc_id>')
    def document_detail(doc_id):
        document = db.get_document_by_id(doc_id)
        if not document:
            abort(404)
        return render_template('document_detail.html', document=document)

    @app.route('/delete_document/<doc_id>', methods=['POST'])
    def delete_document(doc_id):
        # v3.1: 檢查權限 - 只有管理員可以刪除文件
        current_user = getattr(g, 'current_user', None)
        if not current_user:
            flash('請先登入才能刪除文件', 'danger')
            return redirect(url_for('login'))
        
        if current_user.get('role') != 'admin':
            flash('只有管理員可以刪除文件', 'danger')
            return redirect(url_for('documents_list'))
        
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

    @app.route('/original_document/<doc_id>')
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
        elif document.get('original_content'):
            # For text input documents, use the original_content field
            original_content = document.get('original_content', '')
        else:
            # If no original content is available, use the processed content
            original_content = document.get('content', '')

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
        # v3.1: 檢查點數（僅對 viewer）
        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') == 'viewer':
            can_afford = points_manager.can_afford(current_user['id'], 'generate_mindmap')
            if not can_afford['can_afford']:
                return jsonify({
                    'success': False, 
                    'error': f'點數不足。需要 {can_afford["cost"]} 點，目前只有 {can_afford["current_points"]} 點'
                })
            
            # 扣除點數
            deduct_result = points_manager.deduct_points(
                user_id=current_user['id'],
                action_type='generate_mindmap',
                description=f'重新生成心智圖 (問題ID: {q_id})'
            )
            
            if not deduct_result['success']:
                return jsonify({'success': False, 'error': deduct_result['error']})
        
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
                
                if isinstance(result, dict) and result.get('success'):
                    # 成功生成心智圖
                    response = {
                        'success': True, 
                        'message': '心智圖已重新生成', 
                        'mindmap_code': result.get('mindmap_code', '')
                    }
                    
                    # 添加點數資訊
                    if current_user and current_user.get('role') == 'viewer':
                        response['points_deducted'] = deduct_result['points_deducted']
                        response['points_remaining'] = deduct_result['points_remaining']
                    
                    return jsonify(response)
                elif isinstance(result, dict) and not result.get('success', True):
                    # 生成失敗，如果已扣點數需要退還（這裡簡化處理）
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
        # v3.1: 檢查點數（僅對 viewer）
        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') == 'viewer':
            can_afford = points_manager.can_afford(current_user['id'], 'regenerate_answer')
            if not can_afford['can_afford']:
                return jsonify({
                    'success': False, 
                    'error': f'點數不足。需要 {can_afford["cost"]} 點，目前只有 {can_afford["current_points"]} 點'
                })
            
            # 扣除點數
            deduct_result = points_manager.deduct_points(
                user_id=current_user['id'],
                action_type='regenerate_answer',
                description=f'重新生成答案 (問題ID: {q_id})'
            )
            
            if not deduct_result['success']:
                return jsonify({'success': False, 'error': deduct_result['error']})
        
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
                    
                    response = {
                        'success': True, 
                        'message': '答案已重新生成',
                        'answer': answer_text,
                        'sources': sources
                    }
                    
                    # 添加點數資訊
                    if current_user and current_user.get('role') == 'viewer':
                        response['points_deducted'] = deduct_result['points_deducted']
                        response['points_remaining'] = deduct_result['points_remaining']
                    
                    return jsonify(response)
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
        # v3.1: 檢查點數（僅對 viewer）
        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') == 'viewer':
            can_afford = points_manager.can_afford(current_user['id'], 'generate_techniques')
            if not can_afford['can_afford']:
                return jsonify({
                    'success': False, 
                    'error': f'點數不足。需要 {can_afford["cost"]} 點，目前只有 {can_afford["current_points"]} 點'
                })
            
            # 扣除點數
            deduct_result = points_manager.deduct_points(
                user_id=current_user['id'],
                action_type='generate_techniques',
                description=f'生成解題技巧 (問題ID: {q_id})'
            )
            
            if not deduct_result['success']:
                return jsonify({'success': False, 'error': deduct_result['error']})
        
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
                
                response = {
                    'success': True, 
                    'message': '解題技巧已生成並儲存',
                    'summary': summary_result['summary'],
                    'solving_tips': summary_result['solving_tips']
                }
                
                # 添加點數資訊
                if current_user and current_user.get('role') == 'viewer':
                    response['points_deducted'] = deduct_result['points_deducted']
                    response['points_remaining'] = deduct_result['points_remaining']
                
                return jsonify(response)
            else:
                return jsonify({'success': False, 'error': '解題技巧生成失敗，請稍後重試'})
                    
        except Exception as e:
            app.logger.error(f"生成解題技巧失敗: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f'生成失敗: {str(e)}'})

    @app.route('/learning-summary/<doc_id>')
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