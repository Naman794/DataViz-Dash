from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import json
import os
from flask_pymongo import PyMongo
import pandas as pd
from tempfile import NamedTemporaryFile


app = Flask(__name__)

# Use a static secret key for development; in production, consider using environment variables for security
app.secret_key = 'your_development_secret_key'
app.config["MONGO_URI"] = "mongodb+srv://Naman:DashWeb-Project@atlascluster.dwhh58a.mongodb.net/?retryWrites=true&w=majority&appName=AtlasCluster"
mongo = PyMongo(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

def load_user_credentials():
    try:
        with open('users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        flash('User credentials file not found.', 'error')
        return {}
    except json.JSONDecodeError:
        flash('Error decoding user credentials file.', 'error')
        return {}

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def user_loader(user_id):
    users = load_user_credentials()
    if user_id not in users:
        return None
    return User(user_id)

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        users = load_user_credentials()
        username = request.form['username']
        password = request.form['password']
        user = users.get(username, None)
        if user and user['password'] == password:
            user_obj = User(username)
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('index.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload_and_preview():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.xlsx'):
            temp = NamedTemporaryFile(delete=False, suffix='.xlsx')
            file.save(temp.name)
            session['uploaded_file_path'] = temp.name
            # Read the first few rows to generate a preview
            df = pd.read_excel(temp.name, nrows=5)
            # Convert to HTML to render in the template
            preview_html = df.to_html(index=False)
            return render_template('preview.html', preview_html=preview_html)
        else:
            flash('Invalid file type. Please upload an Excel file.')
            return redirect(url_for('upload_and_preview'))
    return render_template('upload.html')




@app.route('/process-upload', methods=['POST'])
def process_upload():
    decision = request.form.get('submit')
    temp_file_path = session.get('uploaded_file_path', '')

    if decision == 'Confirm' and os.path.exists(temp_file_path):
        # Read the entire file this time
        df = pd.read_excel(temp_file_path)
        records = df.to_dict('records')

        # Use "UserDatas" database and create a collection named after the user's username
        user_collection = mongo.cx["UserDatas"][current_user.id]  # Adjusted to use current_user.id for collection name
        user_collection.insert_many(records)
        flash('Data successfully uploaded.')

    # Cleanup
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)
        session.pop('uploaded_file_path', None)

    return redirect(url_for('dashboard' if decision == 'Confirm' else 'upload_and_preview'))



@app.route('/dashboard')
@login_required
def dashboard():
    # Assuming 'dashboard.html' exists in the 'templates' directory
    return render_template('dashboard.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
