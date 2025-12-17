from flask import Flask
import os

from app.config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS
from app.database import init_db


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )

    # -----------------------------
    # SECRET KEY (MANDATORY)
    # -----------------------------
    secret = os.environ.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY not set")

    app.secret_key = secret

    # -----------------------------
    # APP CONFIG
    # -----------------------------
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.config["ALLOWED_EXTENSIONS"] = ALLOWED_EXTENSIONS

    # -----------------------------
    # INITIALIZE DATABASE (SAFE)
    # -----------------------------
    with app.app_context():
        init_db()

    # -----------------------------
    # BLUEPRINTS
    # -----------------------------
    from app.routes import main
    app.register_blueprint(main)

    from app.admin_routes import admin
    app.register_blueprint(admin)

    return app
