import unittest
import os
import wave
import shutil
from app.init import create_app
from app.app import db, User, AudioTrack, WatermarkRecord
import utils.lsb_stego as lsb_stego

class TestSteganography(unittest.TestCase):
    """
    Тестування модуля lsb_stego.py (Core Logic)
    """
    TEST_FILE = "test_samples/file_example_WAV_1MG.wav"
    PROTECTED_FILE = "test_samples/protected_6a74851f_file_example_WAV_1MG.wav"

    def setUp(self):
        with wave.open(self.TEST_FILE, 'wb') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(44100)
            f.writeframes(b'\x00\x00' * 44100)

    def tearDown(self):
        if os.path.exists(self.TEST_FILE):
            os.remove(self.TEST_FILE)
        if os.path.exists(self.PROTECTED_FILE):
            os.remove(self.PROTECTED_FILE)

    def test_encode_decode_success(self):
        """Перевірка успішного вбудовування та зчитування коду
        вбудувати повідомлення → зчитати → порівняти"""
        secret_payload = "COPYRIGHT|12345678"
        
        result = lsb_stego.encode_lsb(self.TEST_FILE, self.PROTECTED_FILE, secret_payload)
        self.assertTrue(result, "Функція кодування має повернути True")
        
        decoded_msg = lsb_stego.decode_lsb(self.PROTECTED_FILE)
        
        self.assertEqual(decoded_msg, secret_payload, "Декодоване повідомлення має співпадати з оригіналом")

    def test_decode_clean_file(self):
        """Перевірка чистого файлу (має повернути None)"""
        decoded_msg = lsb_stego.decode_lsb(self.TEST_FILE)
        self.assertIsNone(decoded_msg, "Чистий файл не повинен містити повідомлення")

    # def test_encode_too_long_message_raises_error(self):
    #     """Перевищення ємності WAV має викликати ValueError"""
    #     payload = "A" * 10000
    #     with self.assertRaises(ValueError):
    #         lsb_stego.encode_lsb(self.TEST_FILE, self.PROTECTED_FILE, payload)


class TestDatabaseModels(unittest.TestCase):
    """
    Тестування бази даних та моделей (User, AudioTrack)
    """
    def setUp(self):
        # створюємо окремий тестовий застосунок
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })
        self.app_context = self.app.app_context()
        self.app_context.push()

        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_user_creation(self):
        """Створення користувача"""
        user = User(email="test@test.com", password_hash="hash123")
        db.session.add(user)
        db.session.commit()
        
        fetched_user = User.query.filter_by(email="test@test.com").first()
        self.assertIsNotNone(fetched_user)
        self.assertEqual(fetched_user.role, 'author')

    def test_track_relationship(self):
        """Перевірка зв'язку Користувач -> Трек"""
        user = User(email="artist@test.com", password_hash="123")
        db.session.add(user)
        db.session.commit()

        track = AudioTrack(title="Hit Song", artist="Me", owner=user, filename="song.wav")
        db.session.add(track)
        db.session.commit()

        self.assertEqual(len(user.tracks), 1)
        self.assertEqual(user.tracks[0].title, "Hit Song")

    def test_watermark_record(self):
        """Перевірка запису про водяний знак"""
        user = User(email="u", password_hash="p")
        db.session.add(user)
        db.session.commit()
        
        track = AudioTrack(title="T", artist="A", owner=user, filename="f.wav")
        db.session.add(track)
        db.session.commit()
        
        wm = WatermarkRecord(track=track, watermark_payload="UUID-CODE-123", pdf_certificate="cert.pdf")
        db.session.add(wm)
        db.session.commit()
        
        fetched_wm = WatermarkRecord.query.filter_by(watermark_payload="UUID-CODE-123").first()
        self.assertIsNotNone(fetched_wm)
        self.assertEqual(fetched_wm.track.title, "T")

    def test_create_audio_track(self):
        """Створення AudioTrack має коректно зберігатися в БД"""
        user = User(email="x@test.com", password_hash="p")
        db.session.add(user)
        db.session.commit()
        track = AudioTrack(title="Song", artist="Me", filename="a.wav", owner=user)
        db.session.add(track)
        db.session.commit()
        t = AudioTrack.query.first()
        self.assertEqual(t.title, "Song")

    def test_track_watermark_relationship(self):
        """Зв’язок Track → Watermark має працювати коректно"""
        user = User(email="y@test.com", password_hash="p")
        db.session.add(user)
        db.session.commit()
        track = AudioTrack(title="Track", artist="A", owner=user, filename="b.wav")
        db.session.add(track)
        db.session.commit()
        wm = WatermarkRecord(track=track, watermark_payload="WM-1", pdf_certificate="c.pdf")
        db.session.add(wm)
        db.session.commit()
        self.assertEqual(track.watermark.watermark_payload, "WM-1")


if __name__ == '__main__':
    unittest.main()