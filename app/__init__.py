from flask import Flask
import os
from app.config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS

def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )

    app.secret_key = os.environ.get("SECRET_KEY", "unsafe-dev-key")

    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.config["ALLOWED_EXTENSIONS"] = ALLOWED_EXTENSIONS

    from app.routes import main
    app.register_blueprint(main)

    from app.admin_routes import admin
    app.register_blueprint(admin)

    return app
