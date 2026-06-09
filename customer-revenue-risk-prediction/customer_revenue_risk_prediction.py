"""
Customer Revenue Risk Prediction
================================

Portfolio-ready Python script for building a customer revenue-risk model.

The model uses historical order activity to identify customers with a high
probability of revenue decline. It includes:

- Customer-level feature engineering
- Recency, frequency and monetary metrics
- Behavioural ratios over 12, 6 and 3 month windows
- Random Forest classification
- Feature importance analysis
- Export of customers classified as high risk

This version is anonymised and does not contain company names, private paths,
credentials or internal datasets.

Expected input columns
----------------------
The input dataset should include the following columns:

- customer_id
- order_id
- order_date
- sales
- quantity
- product_family
- account_manager
- marketing_opt_in
- customer_segment
- first_purchase_year
- customer_group

You can adapt COLUMN_MAPPING below if your raw dataset uses different names.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COLUMN_MAPPING = {
    # Raw column name: portfolio/public column name
    "id_cliente": "customer_id",
    "id_order": "order_id",
    "order_date": "order_date",
    "Sales": "sales",
    "Quantity": "quantity",
    "Family": "product_family",
    "KAM": "account_manager",
    "Optin": "marketing_opt_in",
    "SIC": "customer_segment",
    "year_firstpurch": "first_purchase_year",
    "Grupo": "customer_group",
}

FEATURE_COLUMNS = [
    "sales_last_6m",
    "orders_last_6m",
    "sales_last_3m",
    "orders_last_3m",
    "days_since_last_purchase",
    "sales_variation_3m_vs_6m",
    "account_manager",
    "marketing_opt_in",
    "years_as_customer",
    "customer_segment",
]


@dataclass
class ModelConfig:
    """Configuration used to train and evaluate the model."""

    risk_threshold: float = 0.34
    test_size: float = 0.30
    random_state: int = 42
    n_estimators: int = 100
    min_sales_12m: float = 8000.0
    min_orders_12m: int = 3


# ---------------------------------------------------------------------------
# Data loading and preparation
# ---------------------------------------------------------------------------


def load_orders(file_path: str | Path) -> pd.DataFrame:
    """Load an Excel or CSV orders dataset and standardise column names."""
    file_path = Path(file_path)

    if file_path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(file_path)
    elif file_path.suffix.lower() == ".csv":
        df = pd.read_csv(file_path)
    else:
        raise ValueError("Unsupported file format. Use .xlsx, .xls or .csv")

    df = df.rename(columns=COLUMN_MAPPING)
    return validate_orders_schema(df)


def validate_orders_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and clean the minimum required input schema."""
    required_columns = {
        "customer_id",
        "order_id",
        "order_date",
        "sales",
        "quantity",
        "product_family",
        "account_manager",
        "marketing_opt_in",
        "customer_segment",
        "first_purchase_year",
        "customer_group",
    }

    missing = required_columns.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df["order_date"] = pd.to_datetime(df["order_date"], dayfirst=True, errors="coerce")
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["account_manager"] = pd.to_numeric(df["account_manager"], errors="coerce").fillna(0)
    df["marketing_opt_in"] = pd.to_numeric(df["marketing_opt_in"], errors="coerce").fillna(0)
    df["first_purchase_year"] = pd.to_numeric(df["first_purchase_year"], errors="coerce")

    df = df.dropna(subset=["customer_id", "order_id", "order_date", "sales", "quantity"])
    return df


def build_customer_features(df_orders: pd.DataFrame, reference_date: pd.Timestamp) -> pd.DataFrame:
    """Create customer-level features from transactional order data."""
    df_orders = df_orders.dropna(subset=["quantity"]).copy()

    df_12m = df_orders[df_orders["order_date"] >= reference_date - pd.DateOffset(months=12)]
    df_6m = df_orders[df_orders["order_date"] >= reference_date - pd.DateOffset(months=6)]
    df_3m = df_orders[df_orders["order_date"] >= reference_date - pd.DateOffset(months=3)]

    agg_12m = (
        df_12m.groupby("customer_id")
        .agg(
            sales_last_12m=("sales", "sum"),
            orders_last_12m=("order_id", "nunique"),
            units_last_12m=("quantity", "sum"),
            product_families_last_12m=("product_family", "nunique"),
        )
    )

    agg_6m = (
        df_6m.groupby("customer_id")
        .agg(
            sales_last_6m=("sales", "sum"),
            orders_last_6m=("order_id", "nunique"),
            units_last_6m=("quantity", "sum"),
        )
    )
    agg_6m["avg_ticket_6m"] = safe_divide(agg_6m["sales_last_6m"], agg_6m["orders_last_6m"])

    agg_3m = (
        df_3m.groupby("customer_id")
        .agg(
            sales_last_3m=("sales", "sum"),
            orders_last_3m=("order_id", "nunique"),
            units_last_3m=("quantity", "sum"),
        )
    )
    agg_3m["avg_ticket_3m"] = safe_divide(agg_3m["sales_last_3m"], agg_3m["orders_last_3m"])

    last_purchase = df_orders.groupby("customer_id")["order_date"].max().reset_index()
    last_purchase["days_since_last_purchase"] = (
        reference_date - last_purchase["order_date"]
    ).dt.days
    last_purchase = last_purchase[["customer_id", "days_since_last_purchase"]]

    current_year = reference_date.year
    customer_profile = (
        df_orders.groupby("customer_id")
        .agg(
            account_manager=("account_manager", "max"),
            marketing_opt_in=("marketing_opt_in", "max"),
            customer_segment=("customer_segment", most_frequent_value),
            first_purchase_year=("first_purchase_year", "min"),
        )
        .reset_index()
    )
    customer_profile["years_as_customer"] = (
        current_year - customer_profile["first_purchase_year"]
    )
    customer_profile = customer_profile.drop(columns=["first_purchase_year"])

    features = agg_12m.merge(agg_6m, on="customer_id", how="left")
    features = features.merge(agg_3m, on="customer_id", how="left")
    features = features.merge(last_purchase, on="customer_id", how="left")
    features = features.merge(customer_profile, on="customer_id", how="left")

    features["sales_variation_3m_vs_6m"] = safe_divide(
        features["sales_last_3m"] - features["sales_last_6m"],
        features["sales_last_6m"],
    )
    features["sales_ratio_3m_vs_12m"] = safe_divide(
        features["sales_last_3m"], features["sales_last_12m"]
    )
    features["orders_ratio_3m_vs_12m"] = safe_divide(
        features["orders_last_3m"], features["orders_last_12m"]
    )

    features = features.fillna(0).reset_index()
    return features


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide two series while avoiding inf and NaN values."""
    result = numerator / denominator.replace(0, np.nan)
    return result.replace([np.inf, -np.inf], np.nan).fillna(0)


def most_frequent_value(series: Iterable) -> object:
    """Return the most frequent value in a series or 'Unknown' when empty."""
    series = pd.Series(series).dropna()
    if series.empty:
        return "Unknown"
    return series.mode().iloc[0]


def create_training_dataset(
    active_customers: pd.DataFrame,
    declined_customers: pd.DataFrame,
    config: ModelConfig,
) -> pd.DataFrame:
    """Create the modelling dataset and target variable.

    The target is defined as 1 when a customer is considered at risk of revenue
    decline. In this example, declined_customers are labelled as risk cases, while
    active customers are labelled based on minimum sales and order thresholds.
    """
    active_customers = active_customers.copy()
    active_customers["target_revenue_risk"] = np.where(
        (active_customers["sales_last_12m"] < config.min_sales_12m)
        | (active_customers["orders_last_12m"] < config.min_orders_12m),
        1,
        0,
    )

    declined_customers = declined_customers.copy()
    declined_customers["target_revenue_risk"] = 1

    common_cols = active_customers.columns.intersection(declined_customers.columns)
    model_df = pd.concat(
        [active_customers[common_cols], declined_customers[common_cols]],
        ignore_index=True,
    )
    return model_df


# ---------------------------------------------------------------------------
# Model training and scoring
# ---------------------------------------------------------------------------


def train_revenue_risk_model(
    model_df: pd.DataFrame,
    config: ModelConfig,
) -> tuple[RandomForestClassifier, pd.DataFrame]:
    """Train a Random Forest model and return feature importances."""
    encoded_df = pd.get_dummies(
        model_df[FEATURE_COLUMNS + ["target_revenue_risk"]],
        columns=["customer_segment"],
        drop_first=True,
    )

    X = encoded_df.drop("target_revenue_risk", axis=1)
    y = encoded_df["target_revenue_risk"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=config.test_size,
        random_state=config.random_state,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=config.n_estimators,
        random_state=config.random_state,
    )
    model.fit(X_train, y_train)

    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= config.risk_threshold).astype(int)

    print(f"\nConfusion matrix with threshold {config.risk_threshold}")
    print(confusion_matrix(y_test, y_pred))
    print("\nClassification report:")
    print(classification_report(y_test, y_pred))

    feature_importances = (
        pd.Series(model.feature_importances_, index=X.columns)
        .sort_values(ascending=False)
        .reset_index()
    )
    feature_importances.columns = ["feature", "importance"]

    return model, feature_importances


def plot_feature_importance(feature_importances: pd.DataFrame) -> None:
    """Plot model feature importances."""
    plot_data = feature_importances.sort_values("importance", ascending=True)

    plt.figure(figsize=(10, 6))
    plt.barh(plot_data["feature"], plot_data["importance"])
    plt.title("Feature Importance - Revenue Risk Model")
    plt.xlabel("Importance")
    plt.tight_layout()
    plt.show()


def save_model(model: RandomForestClassifier, output_path: str | Path) -> None:
    """Persist the trained model to disk."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    print(f"Model saved to: {output_path}")


def score_customers(
    model: RandomForestClassifier,
    customer_features: pd.DataFrame,
    threshold: float = 0.34,
) -> pd.DataFrame:
    """Score customers and return risk probabilities."""
    encoded_df = pd.get_dummies(
        customer_features[FEATURE_COLUMNS],
        columns=["customer_segment"],
        drop_first=True,
    )

    for col in model.feature_names_in_:
        if col not in encoded_df.columns:
            encoded_df[col] = 0

    encoded_df = encoded_df[model.feature_names_in_]
    probabilities = model.predict_proba(encoded_df)[:, 1]
    predictions = (probabilities >= threshold).astype(int)

    scored_customers = customer_features.copy()
    scored_customers["revenue_risk_probability"] = probabilities
    scored_customers["revenue_risk_prediction"] = predictions
    return scored_customers


def export_high_risk_customers(scored_customers: pd.DataFrame, output_path: str | Path) -> None:
    """Export customers classified as high revenue-risk."""
    output_columns = [
        "customer_id",
        "sales_last_12m",
        "orders_last_12m",
        "sales_last_6m",
        "sales_last_3m",
        "orders_last_6m",
        "orders_last_3m",
        "days_since_last_purchase",
        "sales_variation_3m_vs_6m",
        "years_as_customer",
        "account_manager",
        "marketing_opt_in",
        "customer_segment",
        "revenue_risk_probability",
    ]

    high_risk = scored_customers[scored_customers["revenue_risk_prediction"] == 1]
    high_risk = high_risk.sort_values("revenue_risk_probability", ascending=False)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    high_risk[output_columns].to_excel(output_path, index=False)
    print(f"High-risk customer file exported to: {output_path}")


# ---------------------------------------------------------------------------
# Example pipeline
# ---------------------------------------------------------------------------


def run_pipeline(input_path: str | Path) -> None:
    """Run the full training and scoring pipeline."""
    config = ModelConfig()
    orders = load_orders(input_path)
    reference_date = orders["order_date"].max()

    active_orders = orders[orders["customer_group"] == 1]
    declined_orders = orders[orders["customer_group"] == 3]

    active_features = build_customer_features(active_orders, reference_date)
    declined_features = build_customer_features(declined_orders, reference_date)

    model_df = create_training_dataset(active_features, declined_features, config)
    model, feature_importances = train_revenue_risk_model(model_df, config)

    print("\nFeature importances:")
    print(feature_importances)
    plot_feature_importance(feature_importances)

    model_path = Path("models/revenue_risk_random_forest.joblib")
    save_model(model, model_path)

    all_customer_features = build_customer_features(orders, reference_date)
    scored_customers = score_customers(
        model,
        all_customer_features,
        threshold=config.risk_threshold,
    )
    export_high_risk_customers(
        scored_customers,
        "outputs/high_revenue_risk_customers.xlsx",
    )


if __name__ == "__main__":
    # Replace this with your anonymised dataset path.
    # The raw dataset is intentionally not included in this repository.
    example_input_path = Path("data/customer_orders_dataset.xlsx")

    if example_input_path.exists():
        run_pipeline(example_input_path)
    else:
        print(
            "No input file found. Add an anonymised dataset at "
            f"{example_input_path} to run the pipeline."
        )
