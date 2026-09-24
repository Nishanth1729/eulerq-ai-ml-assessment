
from pathlib import Path
import re
import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.cluster import KMeans

NUMERIC_FEATURES = [
    "age", "monthly_charges", "total_charges_filled",
    "num_support_calls", "tenure_days", "recency_days", "speed_mbps"
]
CATEGORICAL_FEATURES = [
    "contract_type", "internet_service", "payment_method", "plan_tier"
]

CLUSTER_NAMES = {
    0: "Active Standard-Market Customers",
    1: "High-Value Long-Term Customers",
    2: "Dormant / Low-Recent-Activity Customers",
}

def engineer_features(df: pd.DataFrame, reference_date=None) -> pd.DataFrame:
    out = df.copy()
    out["signup_date"] = pd.to_datetime(out["signup_date"], errors="coerce")
    out["last_login_date"] = pd.to_datetime(out["last_login_date"], errors="coerce")

    if reference_date is None:
        reference_date = out["last_login_date"].max()
    reference_date = pd.Timestamp(reference_date)

    out["tenure_days"] = (out["last_login_date"] - out["signup_date"]).dt.days.clip(lower=0)
    out["recency_days"] = (reference_date - out["last_login_date"]).dt.days.clip(lower=0)

    parsed = out["plan_details"].str.extract(
        r"^(.*?) Plan - \$([\d.]+)/mo - (\d+)Mbps"
    )
    parsed.columns = ["plan_tier", "plan_price", "speed_mbps"]
    out = pd.concat([out, parsed], axis=1)
    out["plan_price"] = pd.to_numeric(out["plan_price"], errors="coerce")
    out["speed_mbps"] = pd.to_numeric(out["speed_mbps"], errors="coerce")

    # Missing total charges are estimated from monthly charges and observed tenure.
    # This avoids dropping otherwise usable customers and avoids creating a cluster
    # whose primary characteristic is a data-quality flag.
    tenure_months = out["tenure_days"] / 30.44
    out["total_charges_filled"] = out["total_charges"].fillna(
        out["monthly_charges"] * tenure_months.clip(lower=1)
    )
    return out

def build_preprocessor():
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer([
        ("numeric", numeric, NUMERIC_FEATURES),
        ("categorical", categorical, CATEGORICAL_FEATURES),
    ])

def fit_segmenter(df: pd.DataFrame, n_clusters=3, random_state=42):
    # Full duplicate records are removed before this function is called.
    engineered = engineer_features(df)
    preprocessor = build_preprocessor()
    X = preprocessor.fit_transform(engineered)
    model = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init=20,
        max_iter=300,
    )
    model.fit(X)
    return engineered, preprocessor, model

def assign_segments(df: pd.DataFrame, artifact):
    engineered = engineer_features(df, artifact["reference_date"])
    X = artifact["preprocessor"].transform(engineered)
    labels = artifact["model"].predict(X)
    out = df.copy()
    out["segment_id"] = labels
    out["segment_name"] = [artifact["cluster_names"][int(x)] for x in labels]
    return out

def load_artifact(path="segment_model.joblib"):
    return joblib.load(path)
