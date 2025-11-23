from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# 1. Define db globally here. Do not re-define it in app.py
db = SQLAlchemy()


def create_app(config_updates=None):
    app = Flask(__name__)

    # Default configuration
    app.config.update(
        {
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///main.db",  # Default fallback
        }
    )

    # 2. Apply updates (from app.py) BEFORE initializing db
    if config_updates:
        app.config.update(config_updates)

    # 3. Initialize plugins
    db.init_app(app)

    # 4. Context needs to be pushed to create tables if models are imported externally
    with app.app_context():
        # Note: This only works if models are imported before this function runs
        # or if they are imported here. To be safe, we usually run this
        # in the main entry point, but we'll leave it here for your convenience.
        db.create_all()

    return app
