from __future__ import annotations

import json
import os
import secrets
import shutil
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, session
from flask_cors import CORS
from werkzeug.utils import secure_filename

from auth_models import db, User, BankFile
from scripts.analysis_engine import run_analysis
from scripts.generate_dataset import ensure_demo_dataset
from scripts.normalize_data import normalize_multiple
from chatbot_engine import NexusChatbot

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'
FINAL_DATASET = PROCESSED_DIR / 'final_dataset.csv'
DISMISSED_FILE = PROCESSED_DIR / 'dismissed_anomalies.json'
GOALS_FILE = PROCESSED_DIR / 'goals.json'

ALLOWED_EXTENSIONS = {'csv', 'pdf'}

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + str(BASE_DIR / 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
db.init_app(app)
CORS(app)

with app.app_context():
    db.create_all()


def serialize_user(user: User) -> dict:
    return {
        'id': user.id,
        'email': user.email,
        'full_name': user.full_name,
        'alert_email': user.email,
    }


def get_logged_in_user() -> User | None:
    user_id = session.get('user_id')
    if not user_id:
        return None
    return db.session.get(User, int(user_id))


def get_user_data_dirs(user_id: int):
    raw = RAW_DIR / str(user_id)
    processed = PROCESSED_DIR / str(user_id)
    raw.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    return raw, processed


def get_user_files(user_id: int):
    _, processed = get_user_data_dirs(user_id)
    return {
        'dataset': processed / 'final_dataset.csv',
        'dismissed': processed / 'dismissed_anomalies.json',
        'goals': processed / 'goals.json',
        'metadata': processed / 'source_metadata.json',
        'alerts': processed / 'alert_state.json',
    }


def ensure_paths() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    if not DISMISSED_FILE.exists():
        DISMISSED_FILE.write_text('[]', encoding='utf-8')
    if not GOALS_FILE.exists():
        GOALS_FILE.write_text('[]', encoding='utf-8')


def ensure_data_ready() -> None:
    ensure_paths()
    if not FINAL_DATASET.exists() or FINAL_DATASET.stat().st_size == 0:
        ensure_demo_dataset(BASE_DIR)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def process_upload(user_id: int, files, bank_hints):
    raw_dir, _ = get_user_data_dirs(user_id)
    user_files = get_user_files(user_id)

    saved_paths = []
    for idx, file in enumerate(files):
        if not file or not file.filename:
            continue
        if not allowed_file(file.filename):
            continue

        filename = secure_filename(file.filename)
        unique_name = f"{uuid4().hex[:8]}_{filename}"
        output_path = raw_dir / unique_name
        file.save(output_path)
        saved_paths.append(str(output_path))

        bf = BankFile(user_id=user_id, filename=unique_name, original_name=file.filename)
        db.session.add(bf)

    if not saved_paths:
        return None, 'No valid files uploaded'

    db.session.commit()

    merged = normalize_multiple(saved_paths, bank_hints=bank_hints, output_path=user_files['dataset'])
    if merged.empty:
        return None, 'Unable to parse uploaded statements'

    write_json(user_files['metadata'], {'mode': 'uploaded'})
    if not user_files['dismissed'].exists():
        write_json(user_files['dismissed'], [])
    if not user_files['goals'].exists():
        write_json(user_files['goals'], [])
    if user_files['alerts'].exists():
        user_files['alerts'].unlink()

    return merged, None


@app.route('/api/signup', methods=['POST'])
def signup():
    payload = request.get_json(silent=True) or request.form
    email = (payload.get('email') or '').strip().lower()
    password = payload.get('password') or ''
    full_name = (payload.get('full_name') or '').strip() or None

    if not email or '@' not in email or not password:
        return jsonify({'status': 'error', 'message': 'Valid email and password required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'status': 'error', 'message': 'Email already registered'}), 400

    user = User(email=email, full_name=full_name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    session.clear()
    session['user_id'] = user.id
    session.permanent = True
    return jsonify({'status': 'success', 'user': serialize_user(user)})


@app.route('/api/login', methods=['POST'])
def login():
    payload = request.get_json(silent=True) or request.form
    email = (payload.get('email') or '').strip().lower()
    password = payload.get('password') or ''

    if not email or not password:
        return jsonify({'status': 'error', 'message': 'Email and password required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'status': 'error', 'message': 'Invalid email or password'}), 401

    session.clear()
    session['user_id'] = user.id
    session.permanent = True
    return jsonify({'status': 'success', 'user': serialize_user(user)})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'success'})


@app.route('/api/user')
def current_user_route():
    user = get_logged_in_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    return jsonify({'status': 'success', 'user': serialize_user(user)})


@app.route('/api/profile', methods=['GET', 'POST'])
def profile():
    user = get_logged_in_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'Login required'}), 401

    if request.method == 'GET':
        return jsonify({'status': 'success', 'user': serialize_user(user)})

    payload = request.get_json(silent=True) or request.form
    new_email = (payload.get('email') or user.email).strip().lower()
    full_name = (payload.get('full_name') or payload.get('name') or '').strip() or None

    if not new_email or '@' not in new_email:
        return jsonify({'status': 'error', 'message': 'Valid email required'}), 400

    existing = User.query.filter_by(email=new_email).first()
    if existing and existing.id != user.id:
        return jsonify({'status': 'error', 'message': 'Email already in use'}), 400

    user.email = new_email
    user.full_name = full_name
    db.session.commit()
    return jsonify({
        'status': 'success',
        'message': 'Profile updated. Future alerts will be sent to this email.',
        'user': serialize_user(user),
    })


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload.html')
def upload_page():
    return render_template('upload.html')


@app.route('/dashboard.html')
def dashboard_page():
    return render_template('dashboard.html')


@app.route('/investments.html')
def investments_page():
    return render_template('investments.html')


@app.route('/insurance.html')
def insurance_page():
    return render_template('insurance.html')


@app.route('/transactions.html')
def transactions_page():
    return render_template('transactions.html')


@app.route('/settings.html')
def settings_page():
    return render_template('settings.html')


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/upload', methods=['POST'])
def upload_files():
    user = get_logged_in_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'Login required'}), 401

    files = request.files.getlist('files')
    if not files:
        return jsonify({'status': 'error', 'message': 'No files uploaded'}), 400

    bank_hints = []
    for idx in range(len(files)):
        bank_hints.append(request.form.get(f'bank_{idx}') or request.form.get('bank') or '')

    merged, error = process_upload(user.id, files, bank_hints)
    if error:
        return jsonify({'status': 'error', 'message': error}), 400

    date_from = merged['date'].min().strftime('%d %b %Y')
    date_to = merged['date'].max().strftime('%d %b %Y')
    return jsonify({
        'status': 'success',
        'banks_detected': sorted(merged['bank'].dropna().unique().tolist()),
        'total_transactions': int(len(merged)),
        'date_range': {'from': date_from, 'to': date_to},
    })


@app.route('/api/analyze')
def analyze():
    user = get_logged_in_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'Login required'}), 401

    user_files = get_user_files(user.id)
    bank = request.args.get('bank') or None
    result = run_analysis(
        base_dir=BASE_DIR,
        bank=bank,
        dataset_path=user_files['dataset'],
        user_files=user_files,
        alert_email=user.email,
        user_name=user.full_name or user.email.split('@')[0],
    )
    return jsonify(result)


@app.route('/api/dismiss_anomaly', methods=['POST'])
def dismiss_anomaly():
    user = get_logged_in_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'Login required'}), 401

    user_files = get_user_files(user.id)
    payload = request.get_json(silent=True) or {}
    anomaly_id = payload.get('anomaly_id')
    if not anomaly_id:
        return jsonify({'status': 'error', 'message': 'Missing anomaly_id'}), 400

    dismissed = set(read_json(user_files['dismissed'], []))
    dismissed.add(anomaly_id)
    write_json(user_files['dismissed'], sorted(dismissed))
    return jsonify({'status': 'success', 'dismissed_count': len(dismissed)})


@app.route('/api/set_goal', methods=['POST'])
def set_goal():
    user = get_logged_in_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'Login required'}), 401

    user_files = get_user_files(user.id)
    payload = request.get_json(silent=True) or {}
    name = (payload.get('name') or '').strip()
    target = float(payload.get('target') or 0)
    deadline = payload.get('deadline')
    if not name or target <= 0 or not deadline:
        return jsonify({'status': 'error', 'message': 'Goal requires name, target and deadline'}), 400

    goals = read_json(user_files['goals'], [])
    goals = [g for g in goals if g.get('name') != name]
    goals.append({'name': name, 'target': target, 'deadline': deadline})
    write_json(user_files['goals'], goals)
    return jsonify({'status': 'success', 'goals': goals})


@app.route('/api/goals')
def get_goals():
    user = get_logged_in_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'Login required'}), 401

    user_files = get_user_files(user.id)
    return jsonify({'goals': read_json(user_files['goals'], [])})


@app.route('/api/reset', methods=['POST'])
def reset_data():
    user = get_logged_in_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'Login required'}), 401

    raw_dir, processed_dir = get_user_data_dirs(user.id)
    user_files = get_user_files(user.id)

    if raw_dir.exists():
        shutil.rmtree(raw_dir, ignore_errors=True)
    if processed_dir.exists():
        shutil.rmtree(processed_dir, ignore_errors=True)

    BankFile.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    get_user_data_dirs(user.id)
    write_json(user_files['dismissed'], [])
    write_json(user_files['goals'], [])

    return jsonify({'status': 'success'})


@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    user = get_logged_in_user()
    payload = request.get_json(silent=True) or {}
    query = (payload.get('query') or '').strip()
    if not query:
        return jsonify({'response': 'Please type a question!'}), 400
    user_id = user.id if user else None
    user_files = get_user_files(user_id) if user_id else None
    try:
        analysis = run_analysis(
            base_dir=BASE_DIR,
            bank=None,
            dataset_path=user_files['dataset'] if user_files else None,
            user_files=user_files
        )
    except Exception:
        return jsonify({'response': 'Upload your bank statement so I can analyze your data!'})
    from chatbot_engine import NexusChatbot
    bot = NexusChatbot(analysis)
    return jsonify(bot.respond(query))


if __name__ == '__main__':
    ensure_data_ready()
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
