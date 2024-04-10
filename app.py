from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import json
import pandas as pd
from tempfile import NamedTemporaryFile
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import os

app = Flask(__name__)
app.secret_key = 'your_development_secret_key'

# MongoDB connection setup
mongo_client = MongoClient('mongodb+srv://Naman:DashWeb-Project@dataviz.kegwtgt.mongodb.net/?retryWrites=true&w=majority&appName=DataViz', server_api=ServerApi('1'))
db = mongo_client['UserDatas']  # Accessing the 'UserDatas' database

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username

@login_manager.user_loader
def user_loader(user_id):
    users = load_user_credentials()
    if user_id not in users:
        return None
    return User(user_id)

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'xls', 'xlsx'}

@app.route('/upload-excel', methods=['POST'])
@login_required
def upload_excel():
    if 'excel_file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['excel_file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Create a NamedTemporaryFile and close it to avoid file lock on Windows
        temp_file = NamedTemporaryFile(delete=False)
        temp_file.close()
        file.save(temp_file.name)
        
        df = pd.read_excel(temp_file.name)
        records = df.to_dict('records')
        
        user_collection_name = current_user.username
        user_collection = db[user_collection_name]
        user_collection.insert_many(records)
        
        flash('File successfully uploaded and data stored in MongoDB.')
        os.remove(temp_file.name)

        return redirect(url_for('dashboard'))
    else:
        flash('Invalid file type')
        return redirect(request.url)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=3000)
