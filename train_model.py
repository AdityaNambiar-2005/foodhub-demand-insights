import pandas as pd
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "FOODHUB DATASET.xlsx")
MODEL_PATH = os.path.join(BASE_DIR, "models", "demand_model.pkl")

os.makedirs(os.path.join(BASE_DIR, "models"), exist_ok=True)

# -----------------------------
# Load dataset
# -----------------------------
df = pd.read_excel(DATA_PATH)

# -----------------------------
# Rename columns
# -----------------------------
df = df.rename(columns={
    "Average meal Price": "price",
    "Rating Type": "rating_text"
})

# -----------------------------
# Convert rating text → numeric
# -----------------------------
rating_map = {
    "Excellent": 5,
    "Very Good": 4,
    "Good": 3,
    "Average": 2,
    "Poor": 1
}

df["rating"] = df["rating_text"].map(rating_map)

# -----------------------------
# Drop invalid rows
# -----------------------------
df = df.dropna(subset=["price", "rating"])

# -----------------------------
# Create demand label
# High demand = good rating + affordable price
# -----------------------------
price_threshold = df["price"].median()

df["demand"] = (
    (df["rating"] >= 4) & (df["price"] <= price_threshold)
).astype(int)

print("Demand distribution:")
print(df["demand"].value_counts())

# -----------------------------
# Features & target
# -----------------------------
X = df[["price", "rating"]]
y = df["demand"]

# -----------------------------
# Train-test split
# -----------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# -----------------------------
# Train model
# -----------------------------
model = RandomForestClassifier(
    n_estimators=200,
    random_state=42
)

model.fit(X_train, y_train)

# -----------------------------
# Save model
# -----------------------------
joblib.dump(model, MODEL_PATH)
print("✅ Model trained and saved successfully")