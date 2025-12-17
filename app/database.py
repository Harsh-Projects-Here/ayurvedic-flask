import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db():
    if not DATABASE_URL:
        return None

    try:
        return psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor
        )
    except Exception as e:
        print("Database connection error:", e)
        return None


def init_db():
    conn = get_db()
    if not conn:
        print("DB not available, skipping init")
        return

    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        landmark TEXT,
        payment_method TEXT,
        latitude TEXT,
        longitude TEXT,
        map_link TEXT,
        total NUMERIC NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER REFERENCES orders(id),
        product_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        price NUMERIC NOT NULL,
        quantity INTEGER NOT NULL
    );
    """)

    conn.commit()
    conn.close()
