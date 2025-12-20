import json
import os

DATA_FILE = os.path.join("data", "products.json")

def load_products():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
