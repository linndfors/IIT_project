import os
import uuid
from datetime import datetime, date
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
import soundfile as sf

import lsb_stego 
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key-lsb-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database_lsb.db')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['CERT_FOLDER'] = 'static/certificates'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CERT_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    """
    Модель користувача системи.
    Зберігає облікові дані та роль користувача (Author/Auditor).
    """
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='author')
    tracks = db.relationship('AudioTrack', backref='owner', lazy=True)

class AudioTrack(db.Model):
    """
    Модель аудіо-треку.
    Зберігає метадані про завантажений файл та посилання на його захищену версію.
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    artist = db.Column(db.String(100), nullable=False)
    isrc = db.Column(db.String(20))
    filename = db.Column(db.String(200))
    owner_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    watermark = db.relationship('WatermarkRecord', backref='track', uselist=False, lazy=True)

class WatermarkRecord(db.Model):
    """
    Модель запису про водяний знак.
    Пов'язує трек з унікальним кодом (Payload), який було вшито у файл.
    """
    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.Integer, db.ForeignKey('audio_track.id'), nullable=False)
    watermark_payload = db.Column(db.String(100), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    pdf_certificate = db.Column(db.String(200))

@login_manager.user_loader
def load_user(user_id):
    """Завантажує користувача з БД за ID для Flask-Login."""
    return User.query.get(int(user_id))


def generate_pdf(track, watermark_code, created_at_time):
    """
    Генерує PDF-сертифікат про захист авторського права.

    :param track: Об'єкт моделі AudioTrack.
    :param watermark_code: Унікальний рядок (UUID), вшитий у файл.
    :return: Ім'я створеного PDF-файлу.
    :rtype: str
    """
    filename = f"cert_{track.id}_{watermark_code}.pdf"
    path = os.path.join(app.config['CERT_FOLDER'], filename)
    c = canvas.Canvas(path)
    c.drawString(100, 800, "СЕРТИФІКАТ LSB ЗАХИСТУ")
    c.drawString(100, 750, f"Трек: {track.title}")
    c.drawString(100, 730, f"Артист: {track.artist}")
    c.drawString(100, 710, f"ISRC: {track.isrc}")
    c.drawString(100, 690, f"Власник: {track.owner.email}")
    c.drawString(100, 650, f"Вшитий код (Hidden Payload): {watermark_code}")
    c.drawString(100, 630, f"Метод захисту: LSB Steganography (.wav)")
    c.drawString(100, 630, f"Дата захисту: {created_at_time}")
    c.save()
    return filename


@app.route('/')
def index():
    """Перенаправляє на сторінку входу."""
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Сторінка реєстрації нового користувача."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if User.query.filter_by(email=email).first():
            flash('Такий email вже є')
            return redirect(url_for('register'))
        user = User(email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Сторінка входу в систему."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Помилка входу')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Особистий кабінет користувача. Відображає список захищених треків."""
    return render_template('dashboard.html', name=current_user.email, tracks=current_user.tracks)

@app.route('/logout')
@login_required
def logout():
    """Вихід із системи."""
    logout_user()
    return redirect(url_for('login'))

@app.route('/protect', methods=['GET', 'POST'])
@login_required
def protect():
    """
    Основний маршрут для захисту аудіофайлу.

    Алгоритм роботи:
    1. Приймає файл (.wav або .mp3) та метадані.
    2. Якщо файл у форматі MP3, виконує конвертацію у WAV (використовуючи pydub/ffmpeg).
    3. Генерує унікальний ідентифікатор (UUID).
    4. Викликає модуль `lsb_stego` для вбудовування ідентифікатора у біти файлу.
    5. Зберігає інформацію в БД та генерує PDF-сертифікат.

    :return: Рендер сторінки або перенаправлення на dashboard.
    """
    if request.method == 'POST':
        title = request.form.get('title')
        isrc = request.form.get('isrc')
        artist = request.form.get('artist')
        file = request.files['file']
        
        if file:
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower()
            
            if ext not in ['wav', 'mp3']:
                flash("Підтримуються тільки WAV та MP3 файли!")
                return redirect(url_for('protect'))

            temp_input_path = os.path.join(app.config['UPLOAD_FOLDER'], "temp_input_" + filename)
            file.save(temp_input_path)
            
            if ext == 'mp3':
                wav_filename = filename.rsplit('.', 1)[0] + ".wav"
                temp_wav_path = os.path.join(app.config['UPLOAD_FOLDER'], "converted_" + wav_filename)
                
                try:
                    data, samplerate = sf.read(temp_input_path)
                    sf.write(temp_wav_path, data, samplerate)
                    
                    os.remove(temp_input_path)
                    temp_input_path = temp_wav_path
                    filename = wav_filename
                except Exception as e:
                    flash(f"Помилка обробки MP3: {e}")
                    return redirect(url_for('protect'))

            wm_payload = str(uuid.uuid4())[:8]
            protected_filename = f"protected_{wm_payload}_{filename}"
            protected_path = os.path.join(app.config['UPLOAD_FOLDER'], protected_filename)
            
            secret_message = f"COPYRIGHT|{wm_payload}"
            success = lsb_stego.encode_lsb(temp_input_path, protected_path, secret_message)
            
            if os.path.exists(temp_input_path):
                os.remove(temp_input_path)
            
            if not success:
                flash("Помилка: Файл занадто малий або пошкоджений!")
                return redirect(url_for('protect'))

            new_track = AudioTrack(title=title, artist=artist, isrc=isrc, filename=protected_filename, owner=current_user)
            db.session.add(new_track)
            db.session.commit()
            created_at_time = date.today()
            cert = generate_pdf(new_track, wm_payload, created_at_time)
            wm_rec = WatermarkRecord(track_id=new_track.id, watermark_payload=wm_payload, pdf_certificate=cert, created_at=created_at_time)
            db.session.add(wm_rec)
            db.session.commit()
            
            flash('Трек успішно сконвертовано у WAV та захищено!')
            return redirect(url_for('dashboard'))
            
    return render_template('protect.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    """
    Маршрут для аудиту (перевірки) файлів.

    Дозволяє завантажити підозрілий файл, спробувати декодувати LSB
    та перевірити наявність витягнутого ключа в базі даних.
    Повертає статус PROTECTED (із даними власника) або CLEAN.
    """
    verification_result = None
    
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower()
            
            temp_check_path = os.path.join(app.config['UPLOAD_FOLDER'], "verify_temp_" + filename)
            file.save(temp_check_path)
            
            path_to_scan = temp_check_path

            if ext == 'mp3':
                wav_path = temp_check_path + ".wav"
                try:
                    data, samplerate = sf.read(temp_check_path)
                    sf.write(wav_path, data, samplerate)
                    path_to_scan = wav_path
                except Exception as e:
                    print(f"Error converting MP3 during verify: {e}")
                    pass

            hidden_msg = lsb_stego.decode_lsb(path_to_scan)
            
            if os.path.exists(temp_check_path): os.remove(temp_check_path)
            if ext == 'mp3' and path_to_scan != temp_check_path and os.path.exists(path_to_scan): 
                os.remove(path_to_scan)
            
            if hidden_msg and hidden_msg.startswith("COPYRIGHT|"):
                extracted_id = hidden_msg.split('|')[1]
                record = WatermarkRecord.query.filter_by(watermark_payload=extracted_id).first()
                if record:
                    track = record.track
                    verification_result = {
                        'status': 'PROTECTED',
                        'method': 'LSB Steganography',
                        'title': track.title,
                        'artist': track.artist,
                        'owner': track.owner.email,
                        'isrc': track.isrc,
                        'watermark_id': extracted_id
                    }
            
            if not verification_result:
                verification_result = {'status': 'CLEAN'}
                
    return render_template('verify.html', result=verification_result)

@app.route('/download_cert/<filename>')
def download_cert(filename):
    """Завантаження PDF-сертифіката."""
    return send_from_directory(app.config['CERT_FOLDER'], filename)

@app.route('/download_track/<filename>')
def download_track(filename):
    """Завантаження захищеного WAV-файлу."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)