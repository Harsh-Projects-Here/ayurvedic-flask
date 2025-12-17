import sqlite3
import os
from app.config import DATABASE_PATH, DATA_DIR


def get_db():
    os.makedirs(DATA_DIR, exist_ok=True)

    conn = sqlite3.connect(
        DATABASE_PATH,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()
    cursor = db.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        landmark TEXT,
        payment_method TEXT,
        latitude TEXT,
        longitude TEXT,
        map_link TEXT,
        total REAL NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    );
    """)

    db.commit()
    db.close()
