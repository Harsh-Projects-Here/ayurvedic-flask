from flask import Blueprint, render_template, request, redirect, url_for, session
import json, os, uuid
from functools import wraps
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD, PRODUCTS_FILE, UPLOAD_FOLDER
from datetime import datetime
from werkzeug.utils import secure_filename
from urllib.parse import quote
from app.database import get_db

admin = Blueprint("admin", __name__, url_prefix="/admin")

# -----------------------------
# FILE CONSTANTS
# -----------------------------
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

# -----------------------------
# AUTH
# -----------------------------
def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.admin_login"))
        return view(*args, **kwargs)
    return wrapped


# -----------------------------
# PRODUCT HELPERS (JSON)
# -----------------------------
def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _ensure_upload_folder():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _load_products():
    try:
        with open(PRODUCTS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def _ensure_products_file_dir():
    os.makedirs(os.path.dirname(PRODUCTS_FILE), exist_ok=True)


def _save_products(products):
    _ensure_products_file_dir()
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=4)



def get_categories():
    products = _load_products()
    return sorted(set(p.get("category") for p in products if p.get("category")))


# -----------------------------
# ORDER HELPERS (SQLITE)
# -----------------------------
def load_orders():
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()

        orders = []
        for o in rows:
            items = db.execute(
                "SELECT name, price, quantity FROM order_items WHERE order_id = ?",
                (o["id"],)
            ).fetchall()

            orders.append({
                **dict(o),
                "items": [dict(i) for i in items]
            })

        return orders
    finally:
        db.close()


def load_order(order_id):
    db = get_db()
    try:
        order = db.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,)
        ).fetchone()

        if not order:
            return None

        items = db.execute(
            "SELECT name, price, quantity FROM order_items WHERE order_id = ?",
            (order_id,)
        ).fetchall()

        return {
            **dict(order),
            "items": [dict(i) for i in items]
        }
    finally:
        db.close()


# -----------------------------
# ADMIN LOGIN / LOGOUT
# -----------------------------
@admin.route("/login", methods=["GET", "POST"])
def admin_login():
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        return "Admin credentials not configured", 500

    if request.method == "POST":
        if (
            request.form.get("username") == ADMIN_USERNAME
            and request.form.get("password") == ADMIN_PASSWORD
        ):
            session["admin_logged_in"] = True
            return redirect(url_for("admin.admin_dashboard"))

        return render_template("admin/login.html", error="Invalid credentials")

    return render_template("admin/login.html")


@admin.route("/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin.admin_login"))


# -----------------------------
# DASHBOARD
# -----------------------------
@admin.route("/dashboard")
@admin_required
def admin_dashboard():
    orders = load_orders()

    total_orders = len(orders)
    pending_orders = sum(1 for o in orders if o["status"] == "PENDING")
    delivered_orders = sum(1 for o in orders if o["status"] == "DELIVERED")
    total_revenue = sum(float(o["total"]) for o in orders)

    today = datetime.now().strftime("%Y-%m-%d")
    daily_revenue = sum(
        float(o["total"]) for o in orders if o["created_at"].startswith(today)
    )

    current_month = datetime.now().strftime("%Y-%m")
    monthly_revenue = sum(
        float(o["total"]) for o in orders if o["created_at"].startswith(current_month)
    )

    return render_template(
        "admin/dashboard.html",
        total_orders=total_orders,
        pending_orders=pending_orders,
        delivered_orders=delivered_orders,
        total_revenue=total_revenue,
        daily_revenue=daily_revenue,
        monthly_revenue=monthly_revenue,
        orders=orders
    )


# -----------------------------
# ORDERS
# -----------------------------
@admin.route("/orders")
@admin_required
def admin_orders():
    return render_template("admin/orders.html", orders=load_orders())


@admin.route("/order/<int:order_id>")
@admin_required
def order_detail(order_id):
    order = load_order(order_id)
    if not order:
        return "Order not found", 404

    return render_template("admin/order_detail.html", order=order)


@admin.route("/orders/delete/<int:order_id>", endpoint="delete_order")
@admin_required
def delete_order(order_id):
    db = get_db()
    try:
        # delete order items first (foreign key safety)
        db.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        db.execute("DELETE FROM orders WHERE id = ?", (order_id,))

        db.commit()
    finally:
        db.close()

    return redirect(url_for("admin.admin_orders"))


@admin.route("/orders/whatsapp/<int:order_id>")
@admin_required
def send_whatsapp_update(order_id):
    order = load_order(order_id)
    if not order:
        return "Order not found", 404

    message = f"""
Order Update – AyurShop

Order ID: {order['id']}
Name: {order['name']}
Status: {order['status']}
Total: ₹{order['total']}
""".strip()

    whatsapp_url = (
        "https://wa.me/91"
        + str(order["phone"])
        + "?text="
        + quote(message)
    )

    return redirect(whatsapp_url)


@admin.route("/invoice/<int:order_id>")
@admin_required
def view_invoice(order_id):
    order = load_order(order_id)
    if not order:
        return "Invoice not found", 404

    return render_template("admin/invoice.html", order=order)


# -----------------------------
# PRODUCTS (JSON — UNCHANGED)
# -----------------------------
@admin.route("/products")
@admin_required
def admin_products():
    return render_template("admin/products.html", products=_load_products())


@admin.route("/products/add", methods=["GET", "POST"])
@admin_required
def add_product():
    if request.method == "POST":
        _ensure_upload_folder()

        files = request.files.getlist("images")
        if len(files) != 5:
            return render_template(
                "admin/add_product.html",
                error="Upload exactly 5 images",
                categories=get_categories()
            )

        images = []
        for f in files:
            if not _allowed_file(f.filename):
                return render_template(
                    "admin/add_product.html",
                    error="Invalid image format",
                    categories=get_categories()
                )
            name = f"{uuid.uuid4().hex}_{secure_filename(f.filename)}"
            f.save(os.path.join(UPLOAD_FOLDER, name))
            images.append(name)

        products = _load_products()

        new_id = max((p["id"] for p in products), default=0) + 1

        products.append({
            "id": new_id,
            "name": request.form.get("name"),
            "mrp": float(request.form.get("mrp")),
            "price": float(request.form.get("price")),
            "rating": float(request.form.get("rating") or 0),
            "rating_count": int(request.form.get("rating_count") or 0),
            "delivery_days": int(request.form.get("delivery_days") or 0),
            
            "description": request.form.get("description"),
            "stock": int(request.form.get("stock")),
            "category": request.form.get("category"),
            "created_at": datetime.now().isoformat(),
            "images": images
        })

        _save_products(products)
        return redirect(url_for("admin.admin_products"))

    return render_template(
        "admin/add_product.html",
        categories=get_categories()
    )

@admin.route("/products/edit/<int:product_id>", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    products = _load_products()
    product = next((p for p in products if p["id"] == product_id), None)

    if not product:
        return "Product not found", 404

    if request.method == "POST":

        def safe_float(v, default=0.0):
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        def safe_int(v, default=0):
            try:
                return int(v)
            except (TypeError, ValueError):
                return default

        raw_badges = request.form.get("badges", "")
        badges = [b.strip() for b in raw_badges.split(",") if b.strip()]

        product.update({
            "name": request.form.get("name"),
            "mrp": safe_float(request.form.get("mrp")),
            "price": safe_float(request.form.get("price")),
            "rating": safe_float(request.form.get("rating")),
            "rating_count": safe_int(request.form.get("rating_count")),
            "delivery_days": safe_int(request.form.get("delivery_days")),
            "badges": badges,
            "description": request.form.get("description"),
            "stock": safe_int(request.form.get("stock")),
            "category": request.form.get("category"),
        })

        _save_products(products)
        return redirect(url_for("admin.admin_products"))

    return render_template(
        "admin/edit_product.html",
        product=product,
        categories=get_categories()
    )


def delete_product(product_id):
    products = [p for p in _load_products() if p["id"] != product_id]
    _save_products(products)

    return redirect(url_for("admin.admin_products"))


@admin.route("/orders/update/<int:order_id>", methods=["POST"])
@admin_required
def update_order_status(order_id):
    status = request.form.get("status")
    print("STATUS RECEIVED:", status)

    if status not in ["PENDING", "CONFIRMED", "SHIPPED", "DISPATCHED", "DELIVERED", "CANCELLED"]:
        print("INVALID STATUS BLOCKED")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    db = get_db()
    try:
        db.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (status, order_id)
        )
        db.commit()
        print("STATUS UPDATED IN DB")
    finally:
        db.close()

    return redirect(url_for("admin.order_detail", order_id=order_id))
