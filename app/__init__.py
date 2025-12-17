from flask import Flask
import os
from app.config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS

def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        instance_relative_config=True
    )

    # ❗ Secret key (must come from Railway env)
    app.secret_key = os.environ.get("SECRET_KEY")
    if not app.secret_key:
        raise RuntimeError("SECRET_KEY is not set")

    # Security basics
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Upload config
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.config["ALLOWED_EXTENSIONS"] = ALLOWED_EXTENSIONS

    # Blueprints
    from app.routes import main
    app.register_blueprint(main)

    from app.admin_routes import admin
    app.register_blueprint(admin)

    return app
