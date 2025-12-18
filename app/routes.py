from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from app.utils import load_products
from app.database import get_db
from datetime import datetime
from functools import wraps

main = Blueprint("main", __name__)


# -----------------------
# HELPERS
# -----------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("main.login"))
        return view(*args, **kwargs)
    return wrapped


def _get_product_image(product):
    images = product.get("images") or []
    return images[0] if images else "default.png"


# -----------------------
# AUTH
# -----------------------

@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone")
        name = request.form.get("name")

        if not phone:
            return render_template("login.html", error="Phone number required")

        conn = get_db()
        if not conn:
            return render_template("login.html", error="Service unavailable")

        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
            user = cur.fetchone()

            # NEW USER → AUTO CREATE
            if not user:
                cur.execute(
                    "INSERT INTO users (name, phone, created_at) VALUES (%s, %s, %s)",
                    (name or "Customer", phone, datetime.now())
                )
                conn.commit()

                cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
                user = cur.fetchone()

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("main.home"))
        finally:
            conn.close()

    return render_template("login.html")


@main.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.home"))


# -----------------------
# ACCOUNT
# -----------------------
@main.route("/account")
@login_required
def account():
    return render_template("account.html")


@main.route("/account/orders")
@login_required
def my_orders():
    conn = get_db()
    if not conn:
        return render_template("my_orders.html", orders=[])

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, total, status, created_at FROM orders WHERE user_id = %s ORDER BY id DESC",
            (session["user_id"],)
        )
        orders = cur.fetchall()

        return render_template("my_orders.html", orders=orders)
    finally:
        conn.close()


# Account Update

@main.route("/account/update", methods=["POST"])
@login_required
def update_account():
    name = request.form.get("name")
    phone = request.form.get("phone")

    if not name or not phone:
        return redirect(url_for("main.account"))

    conn = get_db()
    if not conn:
        return redirect(url_for("main.account"))

    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET name = %s, phone = %s WHERE id = %s",
            (name, phone, session["user_id"])
        )
        conn.commit()

        session["user_name"] = name
        return redirect(url_for("main.account"))
    finally:
        conn.close()


# -----------------------
# HOME
# -----------------------
@main.route("/")
def home():
    products = load_products()

    for p in products:
        p["category"] = p.get("category", "Other")

    categories = sorted(set(p["category"] for p in products))

    return render_template(
        "index.html",
        products=products,
        categories=categories
    )


# -----------------------
# PRODUCTS
# -----------------------
@main.route("/products")
def products():
    products = load_products()
    categories = sorted(set(p["category"] for p in products if p.get("category")))

    selected_category = request.args.get("category")
    if selected_category:
        products = [p for p in products if p["category"] == selected_category]

    return render_template("products.html", products=products, categories=categories, selected_category=selected_category)


@main.route("/product/<int:product_id>")
def product_detail(product_id):
    products = load_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return "Product not found", 404
    return render_template("product_detail.html", product=product)


# -----------------------
# CART (RESTORED ROUTES)
# -----------------------
@main.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):
    products = load_products()
    product = next((p for p in products if p["id"] == product_id), None)

    if not product or product["stock"] <= 0:
        return "Out of stock", 400

    cart = session.get("cart", [])
    item = next((i for i in cart if i["id"] == product_id), None)

    if item:
        item["quantity"] += 1
    else:
        cart.append({
            "id": product["id"],
            "name": product["name"],
            "price": float(product["price"]),
            "image": _get_product_image(product),
            "quantity": 1
        })

    session["cart"] = cart
    return redirect(url_for("main.view_cart"))


@main.route("/cart")
def view_cart():
    cart = session.get("cart", [])
    products = load_products()
    total = 0
    for item in cart:
        product = next((p for p in products if p["id"] == item["id"]), None)
        if product:
            total += float(product["price"]) * item["quantity"]

    return render_template("cart.html", cart=cart, total=total)


@main.route("/cart/increase/<int:product_id>")
def increase_quantity(product_id):
    cart = session.get("cart", [])
    products = load_products()

    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return redirect(url_for("main.view_cart"))

    for item in cart:
        if item["id"] == product_id and item["quantity"] < product["stock"]:
            item["quantity"] += 1
            break

    session["cart"] = cart
    return redirect(url_for("main.view_cart"))



@main.route("/cart/decrease/<int:product_id>")
def decrease_quantity(product_id):
    cart = session.get("cart", [])

    for item in cart:
        if item["id"] == product_id and item["quantity"] > 1:
            item["quantity"] -= 1
            break

    session["cart"] = cart
    return redirect(url_for("main.view_cart"))


@main.route("/cart/remove/<int:product_id>")
def remove_from_cart(product_id):
    cart = session.get("cart", [])
    session["cart"] = [i for i in cart if i["id"] != product_id]
    return redirect(url_for("main.view_cart"))



# -----------------------
# CHECKOUT (LOGIN REQUIRED)
# -----------------------
@main.route("/checkout")
@login_required
def checkout():
    cart = session.get("cart", [])
    if not cart:
        return redirect(url_for("main.view_cart"))

    products = load_products()
    total = 0
    for item in cart:
        product = next((p for p in products if p["id"] == item["id"]), None)
        if product:
            total += float(product["price"]) * item["quantity"]

    return render_template("checkout.html", cart=cart, total=total)


@main.route("/place_order", methods=["POST"])
@login_required
def place_order():
    cart = session.get("cart", [])
    if not cart:
        return jsonify(success=False, message="Cart is empty"), 400

    try:
        name = request.form.get("name")
        phone = request.form.get("phone")
        address = request.form.get("address")
        landmark = request.form.get("landmark")
        payment_method = request.form.get("payment_method")
        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")

        if not all([name, phone, address, payment_method, latitude, longitude]):
            return jsonify(success=False, message="Missing required fields"), 400

        map_link = f"https://maps.google.com/?q={latitude},{longitude}"
        
        products = load_products()
        total = 0
        for item in cart:
            product = next((p for p in products if p["id"] == item["id"]), None)
            if not product or item["quantity"] > product["stock"]:
                return jsonify(success=False, message="Stock changed"), 400
            total += float(product["price"]) * item["quantity"]

        conn = get_db()
        if not conn:
            return jsonify(success=False, message="Service unavailable"), 503

        try:
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO orders
                (user_id, name, phone, address, landmark, payment_method,
                 latitude, longitude, map_link, total, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                session["user_id"],
                name,
                phone,
                address,
                landmark,
                payment_method,
                latitude,
                longitude,
                map_link,
                total,
                "PENDING",
                datetime.now()
            ))

            order_id = cur.fetchone()["id"]

            for item in cart:
                product = next((p for p in products if p["id"] == item["id"]), None)
                price = float(product["price"])
                
                cur.execute("""
                    INSERT INTO order_items
                    (order_id, product_id, name, price, quantity)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    order_id,
                    item["id"],
                    item["name"],
                    price,
                    item["quantity"]
                ))

            conn.commit()

            session["cart"] = []

            return jsonify(
                success=True,
                order={
                    "id": order_id,
                    "name": name,
                    "phone": phone,
                    "address": address,
                    "landmark": landmark,
                    "payment_method": payment_method,
                    "items": cart,
                    "total": total,
                    "map_link": map_link
                }
            )
        finally:
            conn.close()

    except Exception as e:
        print("ORDER ERROR:", e)
        return jsonify(success=False, message="Server error"), 500



# -----------------------
# STATIC PAGES (RESTORED)
# -----------------------
@main.route("/offers")
def offers():
    return render_template("offers.html")


@main.route("/faq")
def faq():
    return render_template("faq.html")


@main.route("/contact")
def contact():
    return render_template("contact.html")


@main.route("/blog")
def blog():
    return render_template("blog.html")


@main.route("/about")
def about():
    return render_template("about.html")


# -----------------------
# BUY NOW (RESTORED)
# -----------------------
@main.route("/buy_now/<int:product_id>")
@login_required
def buy_now(product_id):
    products = load_products()
    product = next((p for p in products if p["id"] == product_id), None)

    if not product or product["stock"] <= 0:
        return "Product out of stock", 400

    session["cart"] = [{
        "id": product["id"],
        "name": product["name"],
        "price": float(product["price"]),
        "image": _get_product_image(product),
        "quantity": 1
    }]

    return redirect(url_for("main.checkout"))