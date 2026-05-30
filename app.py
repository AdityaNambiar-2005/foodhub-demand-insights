from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import plotly.express as px
import joblib
import sqlite3

from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)

from werkzeug.security import generate_password_hash, check_password_hash
from database import create_users_table


app = Flask(__name__)
app.secret_key = "supersecretkey"  # session security

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
class User(UserMixin):
    def __init__(self, id, username, email, password):
        self.id = id
        self.username = username
        self.email = email
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, email, password FROM users WHERE id = ?",
        (user_id,)
    )
    user = cursor.fetchone()
    conn.close()

    if user:
        return User(user[0], user[1], user[2], user[3])
    return None
import os
import pandas as pd

# -----------------------------
# Paths (WITH data folder)
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "FOODHUB DATASET.xlsx")
MODEL_PATH = os.path.join(BASE_DIR, "models", "demand_model.pkl")

# -----------------------------
# Load Excel dataset ONCE
# -----------------------------
if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(
        f"Dataset not found at {DATA_PATH}. "
        "Make sure FOODHUB DATASET.xlsx is inside the data folder."
    )

df = pd.read_excel(DATA_PATH)

# -----------------------------
# Extract REAL values for dropdowns
# -----------------------------
RESTAURANTS = sorted(
    df["Name of the Restaurant"].dropna().astype(str).unique()
)

CUISINES = sorted(
    df["Cuisine Category"].dropna().astype(str).unique()
)

CITIES = sorted(
    df["Name of the city"].dropna().astype(str).unique()
)

def price_segment(price):
    if price <= 250:
        return "Budget"
    elif price <= 500:
        return "Mid-Range"
    else:
        return "Premium"


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, email, password FROM users WHERE username = ?",
            (username,)
        )
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            user_obj = User(user[0], user[1], user[2], user[3])
            login_user(user_obj)
            return redirect(url_for("dashboard"))

        flash("Invalid username or password")
        return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])


        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()

        # Check if user already exists
        cursor.execute(
            "SELECT * FROM users WHERE username=? OR email=?",
            (username, email)
        )

        existing_user = cursor.fetchone()

        if existing_user:
            flash("Username or Email already exists")
            conn.close()
            return redirect(url_for("register"))

        # Insert new user
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, password)
        )

        conn.commit()
        conn.close()

        flash("Registration successful. Please login.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))




@app.route("/dashboard")
@login_required
def dashboard():

    data = df.copy()

    # ===============================
    # KPI METRICS
    # ===============================
    total_restaurants = data["Name of the Restaurant"].nunique()
    total_cities = data["Name of the city"].nunique()
    avg_price = round(data["Average meal Price"].mean(), 2)

    # Market Saturation Index
    saturation_index = round(total_restaurants / avg_price, 2)

    if saturation_index < 0.8:
        saturation_level = "Low"
    elif saturation_index < 1.5:
        saturation_level = "Moderate"
    else:
        saturation_level = "High"

    # ===============================
    # REVENUE POTENTIAL BY CITY
    # ===============================
    city_counts = data["Name of the city"].value_counts()
    city_avg_price = data.groupby("Name of the city")["Average meal Price"].mean()

    revenue_df = (city_counts * city_avg_price).reset_index()
    revenue_df.columns = ["City", "Revenue Potential"]

    fig_revenue = px.bar(
        revenue_df.sort_values("Revenue Potential", ascending=False),
        x="City",
        y="Revenue Potential",
        title="Estimated Revenue Potential by City"
    )
    graph_revenue = fig_revenue.to_html(full_html=False)

    # ===============================
    # PRICE DISTRIBUTION
    # ===============================
    fig_price = px.histogram(
        data,
        x="Average meal Price",
        nbins=20,
        title="Average Meal Price Distribution"
    )
    graph_price = fig_price.to_html(full_html=False)

    # ===============================
    # CUISINE PRESENCE HEATMAP
    # ===============================
    pivot = pd.pivot_table(
        data,
        index="Cuisine Category",
        columns="Name of the city",
        values="Name of the Restaurant",
        aggfunc="count",
        fill_value=0
    )

    fig_heatmap = px.imshow(
        pivot,
        aspect="auto",
        title="Cuisine Presence Across Cities"
    )
    graph_heatmap = fig_heatmap.to_html(full_html=False)

    # ===============================
    # SMART BUSINESS OPPORTUNITY LOGIC
    # ===============================
    grouped = (
        data.groupby(["Name of the city", "Cuisine Category"])
        .agg(
            restaurant_count=("Name of the Restaurant", "count"),
            avg_price=("Average meal Price", "mean")
        )
        .reset_index()
    )

    city_avg_price_map = data.groupby("Name of the city")["Average meal Price"].mean()

    grouped["opportunity_score"] = (
        (1 / grouped["restaurant_count"]) *
        (city_avg_price_map[grouped["Name of the city"]].values / grouped["avg_price"])
    )

    best = grouped.sort_values("opportunity_score", ascending=False).iloc[0]

    best_opportunity = (
        f"{best['Cuisine Category']} cuisine in {best['Name of the city']} "
        f"shows strong growth potential due to low competition and attractive pricing."
    )

    return render_template(
        "dashboard.html",
        total_restaurants=total_restaurants,
        total_cities=total_cities,
        avg_price=avg_price,
        saturation_level=saturation_level,
        best_opportunity=best_opportunity,
        graph_revenue=graph_revenue,
        graph_price=graph_price,
        graph_heatmap=graph_heatmap
    )
@app.route("/insights")
@login_required
def insights():


    # Top 5 Cities
    fig1 = px.bar(
        df['Name of the city'].value_counts().head(5),
        title="Top Cities with Most Restaurants"
    )
    graph1 = fig1.to_html(full_html=False)

    # Cuisine Distribution
    fig2 = px.pie(
        df,
        names='Cuisine Type',
        title="Cuisine Distribution"
    )
    graph2 = fig2.to_html(full_html=False)

    return render_template(
        "insights.html",
        graph1=graph1,
        graph2=graph2
    )
@app.route("/predict", methods=["GET", "POST"])
@login_required
def prediction():
    result = None

    selected_restaurant = None
    selected_cuisine = None
    selected_city = None
    selected_rating = None
    selected_price = None

    if request.method == "POST":
        try:
            selected_restaurant = request.form.get("restaurant")
            selected_cuisine = request.form.get("cuisine")
            selected_city = request.form.get("city")
            selected_rating = request.form.get("rating")
            selected_price = request.form.get("average_meal_price")

            price = float(selected_price)
            rating = int(selected_rating)

            model = joblib.load(MODEL_PATH)

            X_input = [[price, rating]]
            pred = model.predict(X_input)[0]
            prob = model.predict_proba(X_input)[0][pred]

            if pred == 1:
                result = f"High Demand (Confidence: {prob * 100:.1f}%)"
            else:
                result = f"Low Demand (Confidence: {prob * 100:.1f}%)"

        except Exception as e:
            print("Prediction error:", e)
            result = "Prediction failed. Please check inputs."

    return render_template(
        "prediction.html",
        result=result,
        restaurants=RESTAURANTS,
        cuisines=CUISINES,
        cities=CITIES,
        selected_restaurant=selected_restaurant,
        selected_cuisine=selected_cuisine,
        selected_city=selected_city,
        selected_rating=selected_rating,
        selected_price=selected_price
    )
@app.route("/recommend", methods=["GET", "POST"])
@login_required
def recommend():

    recommendations = []

    selected_city = None
    selected_cuisine = None
    selected_segment = None

    if request.method == "POST":
        selected_city = request.form.get("city")
        selected_cuisine = request.form.get("cuisine")
        selected_segment = request.form.get("segment")

        filtered_df = df.copy()

        # ✅ City filter
        filtered_df = filtered_df[
            filtered_df["Name of the city"] == selected_city
        ]

        # ✅ IMPORTANT FIX: Cuisine CONTAINS (not ==)
        filtered_df = filtered_df[
            filtered_df["Cuisine Category"]
            .str.contains(selected_cuisine, case=False, na=False)
        ]

        # ✅ Price segment filter
        if selected_segment == "budget":
            filtered_df = filtered_df[
                filtered_df["Average meal Price"] <= 250
            ]
        elif selected_segment == "mid":
            filtered_df = filtered_df[
                (filtered_df["Average meal Price"] > 250) &
                (filtered_df["Average meal Price"] <= 500)
            ]
        elif selected_segment == "premium":
            filtered_df = filtered_df[
                filtered_df["Average meal Price"] > 500
            ]

        # ✅ Return ALL matching restaurants
        recommendations = filtered_df[
            [
                "Name of the Restaurant",
                "Cuisine Category",
                "Name of the city",
                "Average meal Price",
                "Zomato Restaurant URL"
            ]
        ].to_dict(orient="records")

    return render_template(
        "recommend.html",
        cities=sorted(df["Name of the city"].dropna().unique()),
        cuisines=sorted(
            set(
                c.strip()
                for row in df["Cuisine Category"].dropna()
                for c in row.split(",")
            )
        ),
        recommendations=recommendations,
        selected_city=selected_city,
        selected_cuisine=selected_cuisine,
        selected_segment=selected_segment
    )
if __name__ == "__main__":
    create_users_table()
    app.run(host="0.0.0.0", port=5000)

