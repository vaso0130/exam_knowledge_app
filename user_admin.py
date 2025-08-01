from flask import Flask, request, render_template_string
from werkzeug.security import generate_password_hash
from src.core.database import DatabaseManager


def create_user_app():
    app = Flask(__name__)
    app.secret_key = 'user-admin-secret'
    db = DatabaseManager()

    form_html = """
    <h2>新增帳號</h2>
    <form method='post'>
        <div><label>帳號：<input name='username'></label></div>
        <div><label>密碼：<input type='password' name='password'></label></div>
        <button type='submit'>建立</button>
    </form>
    """

    @app.route('/', methods=['GET', 'POST'])
    def create_user():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            if username and password:
                db.add_user(username, generate_password_hash(password))
                return 'User created successfully'
        return render_template_string(form_html)

    return app


if __name__ == '__main__':
    create_user_app().run(host='127.0.0.1', port=8002)
