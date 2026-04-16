from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import pickle
import os
import pandas as pd   # ✅ REQUIRED FOR ML

app = Flask(__name__)
app.secret_key = "secret123"

# ------------------ LOAD MODEL ------------------
model = None
features = []

if os.path.exists("final_xgboost_model.pkl"):
    model = pickle.load(open("final_xgboost_model.pkl", "rb"))

if os.path.exists("features.pkl"):
    features = pickle.load(open("features.pkl", "rb"))

# ------------------ DATABASE INIT ------------------

def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()

def init_product_db():
    conn = sqlite3.connect("products.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price REAL,
            old_price REAL,
            rating REAL,
            badge TEXT,
            image TEXT,
            color1 TEXT,
            color2 TEXT
        )
    """)
    conn.commit()
    conn.close()

def init_inventory_db():
    conn = sqlite3.connect("inventory.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id TEXT PRIMARY KEY,
            code TEXT,
            name TEXT,
            weight TEXT,
            cartons INTEGER,
            packets INTEGER,
            price REAL
        )
    """)
    conn.commit()
    conn.close()

init_db()
init_product_db()
init_inventory_db()

# ------------------ AUTH ------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                    (request.form["username"], request.form["password"]))
        conn.commit()
        conn.close()
        return redirect("/login")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?",
                    (request.form["username"], request.form["password"]))
        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = request.form["username"]
            session["cart"] = []
            return redirect("/")
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ------------------ HOME ------------------

@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")
    return render_template("index.html")

# ------------------ SHOP ------------------

@app.route("/shop")
def shop():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("products.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()
    conn.close()

    return render_template("shop.html", products=products)

# ------------------ CART ------------------

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    if "cart" not in session:
        session["cart"] = []

    session["cart"].append(request.json)
    session.modified = True

    return jsonify({"message": "Added to cart"})

@app.route("/get_cart")
def get_cart():
    return jsonify(session.get("cart", []))

# ------------------ INVENTORY ------------------

@app.route("/inventory_dashboard")
def inventory_dashboard():
    if "user" not in session:
        return redirect("/login")
    return render_template("inventory_dashboard.html")

@app.route("/get_inventory")
def get_inventory():
    conn = sqlite3.connect("inventory.db")
    cur = conn.cursor()
    cur.execute("SELECT id, code, name, weight, cartons, packets, price FROM inventory")
    rows = cur.fetchall()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "code": r[1],
            "name": r[2],
            "weight": r[3],
            "cartons": r[4],
            "packets": r[5],
            "price": r[6]
        }
        for r in rows
    ])

@app.route("/save_inventory", methods=["POST"])
def save_inventory():
    data = request.json

    conn = sqlite3.connect("inventory.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM inventory")

    for item in data:
        cur.execute("""
            INSERT INTO inventory (id, code, name, weight, cartons, packets, price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            item["id"],
            item["code"],
            item["name"],
            item["weight"],
            int(item["cartons"]),
            int(item["packets"]),
            float(item["price"])
        ))

    conn.commit()
    conn.close()

    return jsonify({"message": "Saved"})

# ------------------ SALES ------------------

@app.route("/sales")
def sales():
    if "user" not in session:
        return redirect("/login")
    return render_template("sales_graph.html")   # ✅ main dashboard

@app.route("/sales_graph")
def sales_graph():
    if "user" not in session:
        return redirect("/login")
    return render_template("sales_graph.html")

# ------------------ 🔥 ML PREDICTION ------------------

@app.route("/sales_predict", methods=["POST"])
def sales_predict():
    try:
        price = float(request.form.get("price", 0))
        stock = float(request.form.get("stock", 0))
        promotion = request.form.get("promotion", "No")

        promotion_flag = 1 if promotion.lower() == "yes" else 0

        input_data = pd.DataFrame([{
            "price": price,
            "stock": stock,
            "promotion": promotion_flag
        }])

        if features:
            input_data = input_data.reindex(columns=features, fill_value=0)

        prediction = model.predict(input_data)[0]
        revenue = prediction * price

        return jsonify({
            "prediction": float(round(prediction, 2)),
            "revenue": float(round(revenue, 2))
        })

    except Exception as e:
        return jsonify({"error": str(e)})

# ------------------ PRODUCTS ------------------

@app.route("/add_product", methods=["POST"])
def add_product():
    data = request.json

    conn = sqlite3.connect("products.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (name, price, old_price, rating, badge, image, color1, color2)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["name"], data["price"], data.get("old_price"),
        data.get("rating"), data.get("badge"), data.get("image"),
        data.get("color1"), data.get("color2")
    ))
    conn.commit()
    conn.close()

    return jsonify({"message": "Saved"})

@app.route("/get_products")
def get_products():
    conn = sqlite3.connect("products.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM products")
    rows = cur.fetchall()
    conn.close()

    return jsonify([
        {
            "name": r[1],
            "price": r[2],
            "old_price": r[3],
            "rating": r[4],
            "badge": r[5],
            "image": r[6],
            "color1": r[7],
            "color2": r[8]
        }
        for r in rows
    ])

# ------------------ RUN ------------------

if __name__ == "__main__":
    app.run(debug=True)