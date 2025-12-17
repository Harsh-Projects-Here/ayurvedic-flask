import os

# Base paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# Data directory (persistent)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Database (❗ THIS WAS MISSING)
DATABASE_PATH = os.path.join(DATA_DIR, "database.db")

# Admin credentials (from environment variables)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# Upload settings
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "images")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

# Products JSON
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
