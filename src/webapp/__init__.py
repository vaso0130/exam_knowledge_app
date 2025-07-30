from flask import Flask, render_template, request, abort
from ..core.database import DatabaseManager
import markdown


def create_app(db_path: str = "./db.sqlite3"):
    db = DatabaseManager(db_path)
    app = Flask(__name__)

    @app.route('/')
    def index():
        subjects = db.get_all_subjects()
        return render_template('index.html', subjects=subjects)

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
        html = markdown.markdown(q['question_text'] + '\n\n' + (q['answer_text'] or ''))
        return render_template('question_detail.html', question=q, html=html)

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
