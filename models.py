from init import db
from flask_login import UserMixin
from datetime import datetime

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