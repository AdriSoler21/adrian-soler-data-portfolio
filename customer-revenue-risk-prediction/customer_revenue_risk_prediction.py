"""
Customer Revenue Risk Prediction
--------------------------------
Portfolio-safe version.

Purpose:
    Build a customer-level dataset and train a classification model to detect
    customers at risk of revenue decline.

Notes:
    - No proprietary data, paths, company names, credentials or internal IDs are included.
    - Expected input is a generic orders dataset with customer, order, revenue and product fields.

Expected columns:
    customer_id, order_id, order_date, sales, quantity, product_family

Optional columns:
    account_manager, marketing_opt_in, sector, first_purchase_year
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split


@dataclass
class RiskModelConfig:
    reference_date: str
    min_revenue_12m: float = 8000.0
    min_orders_12m: int = 3
    test_size: float = 0.25
    random_state: int = 42


def _safe_mode(series: pd.Series, default: str = "Unknown") -> str:
    mode = series.dropna().mode()
    return mode.iloc[0] if not mode.empty else default


def prepare_customer_features(orders: pd.DataFrame, config: RiskModelConfig) -> pd.DataFrame:
    """Aggregate transactional data into customer-level features."""
    required = {"customer_id", "order_id", "order_date", "sales", "quantity", "product_family"}
    missing = required - set(orders.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = orders.copy()
    df = df.dropna(subset=["customer_id", "order_id", "order_date", "sales", "quantity"])
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df = df[df["order_date"].notna()]

    ref_date = pd.to_datetime(config.reference_date)

    windows = {
        "12m": df[df["order_date"] >= ref_date - pd.DateOffset(months=12)],
        "6m": df[df["order_date"] >= ref_date - pd.DateOffset(months=6)],
        "3m": df[df["order_date"] >= ref_date - pd.DateOffset(months=3)],
    }

    features = windows["12m"].groupby("customer_id").agg(
        revenue_12m=("sales", "sum"),
        orders_12m=("order_id", "nunique"),
        units_12m=("quantity", "sum"),
        distinct_families_12m=("product_family", "nunique"),
    )

    for label in ["6m", "3m"]:
        agg = windows[label].groupby("customer_id").agg(
            **{
                f"revenue_{label}": ("sales", "sum"),
                f"orders_{label}": ("order_id", "nunique"),
                f"units_{label}": ("quantity", "sum"),
            }
        )
        agg[f"avg_ticket_{label}"] = agg[f"revenue_{label}"] / agg[f"orders_{label}"].replace(0, np.nan)
        features = features.join(agg, how="left")

    last_order = df.groupby("customer_id")["order_date"].max().to_frame("last_order_date")
    last_order["days_since_last_order"] = (ref_date - last_order["last_order_date"]).dt.days
    features = features.join(last_order[["days_since_last_order"]], how="left")

    if {"account_manager", "marketing_opt_in", "sector", "first_purchase_year"}.issubset(df.columns):
        current_year = ref_date.year
        profile = df.groupby("customer_id").agg(
            account_manager=("account_manager", "max"),
            marketing_opt_in=("marketing_opt_in", "max"),
            sector=("sector", _safe_mode),
            first_purchase_year=("first_purchase_year", "min"),
        )
        profile["customer_tenure_years"] = current_year - profile["first_purchase_year"]
        features = features.join(profile.drop(columns=["first_purchase_year"]), how="left")

    features = features.fillna(0)

    features["revenue_trend_3m_vs_6m"] = (
        (features["revenue_3m"] - features["revenue_6m"]) / features["revenue_6m"].replace(0, np.nan)
    ).fillna(0)
    features["revenue_ratio_3m_vs_12m"] = (
        features["revenue_3m"] / features["revenue_12m"].replace(0, np.nan)
    ).fillna(0)
    features["orders_ratio_3m_vs_12m"] = (
        features["orders_3m"] / features["orders_12m"].replace(0, np.nan)
    ).fillna(0)

    features["target_revenue_risk"] = np.where(
        (features["revenue_12m"] < config.min_revenue_12m)
        | (features["orders_12m"] < config.min_orders_12m),
        1,
        0,
    )

    return features.reset_index()


def train_risk_model(customer_features: pd.DataFrame, config: RiskModelConfig):
    """Train and evaluate a Random Forest customer risk classifier."""
    df = pd.get_dummies(customer_features, drop_first=True)
    y = df["target_revenue_risk"]
    X = df.drop(columns=["customer_id", "target_revenue_risk"], errors="ignore")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.test_size, random_state=config.random_state, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        random_state=config.random_state,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    print("Confusion matrix:")
    print(confusion_matrix(y_test, predictions))
    print("\nClassification report:")
    print(classification_report(y_test, predictions))

    feature_importance = pd.DataFrame({
        "feature": X.columns,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    return model, feature_importance


if __name__ == "__main__":
    input_path = Path("data/orders_sample.csv")
    config = RiskModelConfig(reference_date="2025-12-31")

    if not input_path.exists():
        raise FileNotFoundError(
            "Place a portfolio-safe sample dataset at data/orders_sample.csv "
            "with the columns documented in this script."
        )

    orders_df = pd.read_csv(input_path)
    features_df = prepare_customer_features(orders_df, config)
    model, importances = train_risk_model(features_df, config)
    print(importances.head(15))
