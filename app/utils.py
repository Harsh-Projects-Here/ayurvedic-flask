from app.database import get_db

def load_products():
    conn = get_db()
    if not conn:
        return []

    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products ORDER BY id DESC")
        return cur.fetchall()
    finally:
        conn.close()
