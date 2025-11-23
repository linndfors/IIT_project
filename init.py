from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(config_updates=None):
    app = Flask(__name__)

    app.config.update(
        {
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///main.db",
        }
    )

    if config_updates:
        app.config.update(config_updates)

    db.init_app(app)

    with app.app_context():

        db.create_all()

    return app
