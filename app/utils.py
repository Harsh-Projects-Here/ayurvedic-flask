import json
import os

def load_products():
    file_path = os.path.join("data", "products.json")
    with open(file_path, "r") as f:
        return json.load(f)
