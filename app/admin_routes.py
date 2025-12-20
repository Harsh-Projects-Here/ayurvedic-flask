from flask import Blueprint, render_template, request, redirect, url_for, session
import json, os, uuid
from functools import wraps
from app.config import ADMIN_USERNAME, ADMIN_PASSWORD
from datetime import datetime
from werkzeug.utils import secure_filename
from urllib.parse import quote
from app.database import get_db

admin = Blueprint("admin", __name__, url_prefix="/admin")

# -----------------------------
# FILE CONSTANTS
# -----------------------------

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



# -----------------------------
# ORDER HELPERS (POSTGRESQL)
# -----------------------------
def load_orders():
    conn = get_db()
    if not conn:
        return []

    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders ORDER BY id DESC")
        rows = cur.fetchall()

        orders = []
        for o in rows:
            cur.execute(
                "SELECT name, price, quantity FROM order_items WHERE order_id = %s",
                (o["id"],)
            )
            items = cur.fetchall()

            orders.append({
                **dict(o),
                "items": [dict(i) for i in items]
            })

        return orders
    finally:
        conn.close()


def load_order(order_id):
    conn = get_db()
    if not conn:
        return None

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM orders WHERE id = %s",
            (order_id,)
        )
        order = cur.fetchone()

        if not order:
            return None

        cur.execute(
            "SELECT name, price, quantity FROM order_items WHERE order_id = %s",
            (order_id,)
        )
        items = cur.fetchall()

        return {
            **dict(order),
            "items": [dict(i) for i in items]
        }
    finally:
        conn.close()


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

    now = datetime.now()

    daily_revenue = sum(
        float(o["total"])
        for o in orders
        if o["created_at"] and o["created_at"].date() == now.date()
    )

    monthly_revenue = sum(
        float(o["total"])
        for o in orders
        if o["created_at"]
        and o["created_at"].year == now.year
        and o["created_at"].month == now.month
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
    conn = get_db()
    if not conn:
        return redirect(url_for("admin.admin_orders"))

    try:
        cur = conn.cursor()
        # delete order items first (foreign key safety)
        cur.execute("DELETE FROM order_items WHERE order_id = %s", (order_id,))
        cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))

        conn.commit()
    finally:
        conn.close()

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


@admin.route("/orders/update/<int:order_id>", methods=["POST"])
@admin_required
def update_order_status(order_id):
    status = request.form.get("status")
    print("STATUS RECEIVED:", status)

    if status not in ["PENDING", "CONFIRMED", "SHIPPED", "DISPATCHED", "DELIVERED", "CANCELLED"]:
        print("INVALID STATUS BLOCKED")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    conn = get_db()
    if not conn:
        return redirect(url_for("admin.order_detail", order_id=order_id))

    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE orders SET status = %s WHERE id = %s",
            (status, order_id)
        )
        conn.commit()
        print("STATUS UPDATED IN DB")
    finally:
        conn.close()

    return redirect(url_for("admin.order_detail", order_id=order_id))


def load_products():
    conn = get_db()
    if not conn:
        return []

    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products ORDER BY id DESC")
        products = cur.fetchall()

        for p in products:
            p["images"] = p["images"] or []
            p["badges"] = p["badges"] or []

        return products
    finally:
        conn.close()


def load_product(product_id):
    conn = get_db()
    if not conn:
        return None

    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
        product = cur.fetchone()
        if product:
            product["images"] = product["images"] or []
            product["badges"] = product["badges"] or []
        return product
    finally:
        conn.close()


def get_categories():
    conn = get_db()
    if not conn:
        return []

    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
        return sorted([row["category"] for row in cur.fetchall()])
    finally:
        conn.close()


# -----------------------------
# PRODUCTS (DATABASE)
# -----------------------------
@admin.route("/products")
@admin_required
def admin_products():
    products = load_products()
    return render_template("admin/products.html", products=products)


@admin.route("/products/add", methods=["GET", "POST"])
@admin_required
def add_product():
    if request.method == "POST":
        conn = get_db()
        if not conn:
            return "Database unavailable", 500

        try:
            cur = conn.cursor()
            images = request.files.getlist("images")

            if len(images) != 5:
                return render_template(
                    "admin/add_product.html",
                    error="Exactly 5 images required"
                )

            image_names = []
            for img in images:
                filename = secure_filename(img.filename)
                img.save(os.path.join("app/static/images", filename))
                image_names.append(filename)

            cur.execute("""
                INSERT INTO products
                (name, mrp, price, rating, rating_count, delivery_days,
                 description, stock, category, badges, images, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                request.form["name"],
                request.form["mrp"],
                request.form["price"],
                request.form.get("rating", 0),
                request.form.get("rating_count", 0),
                request.form.get("delivery_days", 0),
                request.form["description"],
                request.form["stock"],
                request.form["category"],
                json.loads(request.form.get("badges", "[]")),
                json.dumps(image_names),
                datetime.now()
            ))

            conn.commit()
            return redirect(url_for("admin.admin_products"))
        finally:
            conn.close()

    return render_template("admin/add_product.html")


@admin.route("/products/edit/<int:product_id>", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    product = load_product(product_id)
    if not product:
        return "Product not found", 404

    if request.method == "POST":
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE products SET
                name=%s, mrp=%s, price=%s, rating=%s, rating_count=%s,
                delivery_days=%s, description=%s, stock=%s,
                category=%s, badges=%s
                WHERE id=%s
            """, (
                request.form["name"],
                request.form["mrp"],
                request.form["price"],
                request.form.get("rating", 0),
                request.form.get("rating_count", 0),
                request.form.get("delivery_days", 0),
                request.form["description"],
                request.form["stock"],
                request.form["category"],
                json.loads(request.form.get("badges", "[]")),
                product_id
            ))
            conn.commit()
        finally:
            conn.close()

        return redirect(url_for("admin.admin_products"))

    return render_template(
        "admin/edit_product.html",
        product=product,
        categories=get_categories()
    )


@admin.route("/products/delete/<int:product_id>")
@admin_required
def delete_product(product_id):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM products WHERE id=%s", (product_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("admin.admin_products"))