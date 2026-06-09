"""
Price Elasticity & Price Optimization Analysis
=============================================

Portfolio-safe version.

This script analyses product performance and provides price optimization recommendations
using traffic, sales, conversion rate and purchase cost data.

It includes:
- Product performance segmentation
- Price normalization
- Elasticity indicators
- Margin-based price pre-optimization
- Linear / polynomial price optimization
- Final recommended price calculation
- Model evaluation using MAE

All company-specific paths, internal folder names and private dataset references have been removed.

Expected input file:
- data/product_pricing_periods.xlsx

Expected columns:
- product_id
- price
- sales
- traffic
- stock
- purchase_price

Author: Adrián Soler
"""

from __future__ import annotations

from pathlib import Path
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from numpy import polyfit, poly1d
from scipy.optimize import minimize
from scipy.stats import linregress
from sklearn.metrics import mean_absolute_error


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")
LOG_DIR = Path("logs")

INPUT_FILE = DATA_DIR / "product_pricing_periods.xlsx"
OUTPUT_FILE = OUTPUT_DIR / "price_optimization_results.xlsx"
LOG_FILE = LOG_DIR / "price_elasticity_analysis.log"

MIN_MARGIN = 0.05
VAT_RATE = 0.21
MIN_TRAFFIC_THRESHOLD = 25
MIN_SIGNIFICANT_SALES = 6
MIN_SIGNIFICANT_TRAFFIC = 60


# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

def setup_logger() -> logging.Logger:
    """Configure project logger."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("price_elasticity_analysis")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    return logger


# ---------------------------------------------------------------------
# Data loading and validation
# ---------------------------------------------------------------------

def load_pricing_data(path: Path = INPUT_FILE) -> pd.DataFrame:
    """Load product pricing data from Excel."""
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}. Place the dataset in the `data/` folder or update INPUT_FILE."
        )

    df = pd.read_excel(path)

    rename_map = {
        "producto_id": "product_id",
        "precio": "price",
        "ventas": "sales",
        "trafico": "traffic",
        "precio_compra": "purchase_price",
    }
    df = df.rename(columns=rename_map)

    required_columns = ["product_id", "price", "sales", "traffic", "stock", "purchase_price"]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    for col in ["price", "sales", "traffic", "stock", "purchase_price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["product_id", "price", "sales", "traffic", "purchase_price"]).copy()
    df["product_id"] = df["product_id"].astype(str).str.strip()

    return df


# ---------------------------------------------------------------------
# Product segmentation
# ---------------------------------------------------------------------

def classify_product(row: pd.Series, low_traffic_q: float, medium_traffic_q: float) -> str:
    """Classify products using traffic and conversion rate."""
    traffic = row["traffic"]
    conversion_rate = row["conversion_rate"]

    if traffic < MIN_TRAFFIC_THRESHOLD or pd.isna(conversion_rate):
        return "Low visibility"
    if traffic > medium_traffic_q and conversion_rate > 1:
        return "Best seller"
    if conversion_rate > 3 and traffic <= medium_traffic_q:
        return "Hidden winner"
    if traffic > medium_traffic_q and conversion_rate < 1:
        return "At risk"
    if conversion_rate < 1:
        return "Needs adjustment"
    if conversion_rate > 1:
        return "Stable"
    return "Promising"


def build_product_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate data at product level and classify products."""
    total_traffic = df.groupby("product_id")["traffic"].sum().reset_index()
    low_traffic_q = total_traffic["traffic"].quantile(0.30)
    medium_traffic_q = total_traffic["traffic"].quantile(0.80)

    product_summary = (
        df.groupby("product_id")
        .agg(
            price=("price", "last"),
            sales=("sales", "sum"),
            traffic=("traffic", "sum"),
            stock=("stock", "last"),
            purchase_price=("purchase_price", "last"),
        )
        .reset_index()
    )

    product_summary["conversion_rate"] = (
        product_summary["sales"] / product_summary["traffic"]
    ) * 100

    product_summary["product_category"] = product_summary.apply(
        lambda row: classify_product(row, low_traffic_q, medium_traffic_q),
        axis=1,
    )

    product_summary["normalized_price"] = product_summary["price"].apply(normalize_price)
    product_summary["total_sales"] = product_summary["sales"]
    product_summary["total_traffic"] = product_summary["traffic"]

    product_summary["significance"] = np.where(
        (product_summary["total_sales"] >= MIN_SIGNIFICANT_SALES)
        & (product_summary["total_traffic"] >= MIN_SIGNIFICANT_TRAFFIC),
        "Significant",
        "Not significant",
    )

    return product_summary


# ---------------------------------------------------------------------
# Price normalization and elasticity
# ---------------------------------------------------------------------

def normalize_price(price: float) -> float:
    """Normalize prices into business-friendly price steps."""
    if price <= 10:
        return np.floor(price * 4) / 4
    if price <= 30:
        return np.floor(price * 2) / 2
    if price <= 70:
        return np.floor(price)
    if price <= 150:
        return np.floor(price / 2) * 2
    if price <= 400:
        return np.floor(price / 5) * 5
    return np.floor(price / 10) * 10


def build_price_level_table(df: pd.DataFrame, product_summary: pd.DataFrame) -> pd.DataFrame:
    """Aggregate significant products by product and normalized price."""
    significant_ids = product_summary.loc[
        product_summary["significance"] == "Significant",
        "product_id",
    ]

    significant_df = df[df["product_id"].isin(significant_ids)].copy()
    significant_df["normalized_price"] = significant_df["price"].apply(normalize_price)

    price_level = (
        significant_df.groupby(["product_id", "normalized_price"])
        .agg(
            number_periods=("product_id", "size"),
            sales_sum=("sales", "sum"),
            traffic_sum=("traffic", "sum"),
            purchase_price_mean=("purchase_price", "mean"),
            stock_mean=("stock", "mean"),
        )
        .reset_index()
    )

    price_level["sales_per_period"] = price_level["sales_sum"] / price_level["number_periods"]
    price_level["traffic_per_period"] = price_level["traffic_sum"] / price_level["number_periods"]
    price_level["conversion_rate_per_period"] = (
        price_level["sales_per_period"] / price_level["traffic_per_period"]
    ) * 100

    price_level["margin_per_period"] = (
        1000
        * (price_level["conversion_rate_per_period"] / 100)
        * (price_level["normalized_price"] - price_level["purchase_price_mean"])
    )

    return price_level.replace([np.inf, -np.inf], np.nan)


def calculate_average_elasticities(group: pd.DataFrame) -> pd.Series:
    """Calculate average price elasticity for sales and conversion rate."""
    group = group.sort_values("normalized_price")

    sales_elasticities = []
    conversion_elasticities = []

    for i in range(1, len(group)):
        p0 = group["normalized_price"].iloc[i - 1]
        p1 = group["normalized_price"].iloc[i]
        sales0 = group["sales_per_period"].iloc[i - 1]
        sales1 = group["sales_per_period"].iloc[i]
        cr0 = group["conversion_rate_per_period"].iloc[i - 1]
        cr1 = group["conversion_rate_per_period"].iloc[i]

        if p0 != 0 and sales0 != 0 and (p1 - p0) != 0:
            sales_elasticities.append(((sales1 - sales0) / sales0) / ((p1 - p0) / p0))

        if p0 != 0 and cr0 != 0 and (p1 - p0) != 0:
            conversion_elasticities.append(((cr1 - cr0) / cr0) / ((p1 - p0) / p0))

    return pd.Series(
        {
            "sales_price_elasticity": np.mean(sales_elasticities) if sales_elasticities else 0.0,
            "conversion_price_elasticity": (
                np.mean(conversion_elasticities) if conversion_elasticities else 0.0
            ),
        }
    )


def add_elasticity_metrics(price_level: pd.DataFrame) -> pd.DataFrame:
    """Add elasticity indicators to the price-level table."""
    elasticities = (
        price_level.groupby("product_id")
        .apply(calculate_average_elasticities)
        .reset_index()
    )

    return price_level.merge(elasticities, on="product_id", how="left")


# ---------------------------------------------------------------------
# Price optimization
# ---------------------------------------------------------------------

def calculate_pre_optimized_price(group: pd.DataFrame) -> float:
    """Select price level with the highest estimated margin per period."""
    max_margin = group["margin_per_period"].max()
    return group.loc[group["margin_per_period"] == max_margin, "normalized_price"].max()


def optimize_price_for_product(row: pd.Series, price_level: pd.DataFrame) -> float:
    """Optimize product price using linear or polynomial approximation."""
    product_id = row["product_id"]
    product_data = price_level[price_level["product_id"] == product_id].copy()

    prices = product_data["normalized_price"].values
    margins = product_data["margin_per_period"].values

    if len(prices) <= 1:
        return row["price"]

    if len(prices) == 2:
        try:
            slope, _, _, _, _ = linregress(prices, margins)
            return float(prices.max() * 1.2 if slope > 0 else prices.min() * 0.8)
        except Exception:
            return row["price"]

    try:
        coefficients = polyfit(prices, margins, 2)
        polynomial = poly1d(coefficients)
        objective = lambda p: -polynomial(p)
        result = minimize(
            objective,
            x0=(prices.min() + prices.max()) / 2,
            bounds=[(prices.min() * 0.9, prices.max() * 1.1)],
        )
        return float(result.x[0])
    except Exception:
        return row["price"]


def round_recommended_price(price: float) -> float:
    """Apply commercial rounding to recommended prices."""
    if price <= 100:
        return (np.floor(price * 10) - 0.1) / 10
    return np.floor(price) - 0.01


def add_price_recommendations(
    product_summary: pd.DataFrame,
    price_level: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate optimized and final recommended prices."""
    pre_optimized = (
        price_level.groupby("product_id")
        .apply(calculate_pre_optimized_price)
        .reset_index(name="pre_optimized_price")
    )

    product_summary = product_summary.merge(pre_optimized, on="product_id", how="left")

    product_summary["optimized_price"] = product_summary.apply(
        lambda row: optimize_price_for_product(row, price_level),
        axis=1,
    )

    product_summary["optimized_price"] = np.maximum(
        product_summary["optimized_price"],
        product_summary["purchase_price"] * (1 + MIN_MARGIN),
    )

    product_summary["optimized_price"] = product_summary["optimized_price"].fillna(
        product_summary["price"]
    )

    product_summary["recommended_price"] = np.where(
        product_summary["optimized_price"] > 0,
        np.maximum(product_summary["optimized_price"], 2.0),
        product_summary["price"],
    )

    product_summary["recommended_price_with_vat"] = (
        product_summary["recommended_price"] * (1 + VAT_RATE)
    ).apply(round_recommended_price)

    return product_summary


# ---------------------------------------------------------------------
# Evaluation and plotting
# ---------------------------------------------------------------------

def evaluate_recommendations(product_summary: pd.DataFrame) -> dict[str, float]:
    """Evaluate recommended prices against current prices using MAE."""
    clean_optimized = product_summary.dropna(subset=["price", "optimized_price"])
    clean_recommended = product_summary.dropna(subset=["price", "recommended_price"])

    optimized_mae = mean_absolute_error(
        clean_optimized["price"],
        clean_optimized["optimized_price"],
    )

    recommended_mae = mean_absolute_error(
        clean_recommended["price"],
        clean_recommended["recommended_price"],
    )

    metrics = {
        "optimized_price_mae": optimized_mae,
        "recommended_price_mae": recommended_mae,
        "average_optimized_price": product_summary["optimized_price"].mean(),
        "average_recommended_price": product_summary["recommended_price"].mean(),
    }

    return metrics


def plot_current_vs_optimized_price(product_summary: pd.DataFrame) -> None:
    """Plot current vs optimized price by product category."""
    plot_df = product_summary.dropna(
        subset=["price", "optimized_price", "product_category"]
    )

    categories = plot_df["product_category"].astype("category")
    category_codes = categories.cat.codes

    plt.figure(figsize=(10, 6))
    scatter = plt.scatter(
        plot_df["price"],
        plot_df["optimized_price"],
        c=category_codes,
        alpha=0.7,
    )

    min_price = min(plot_df["price"].min(), plot_df["optimized_price"].min())
    max_price = max(plot_df["price"].max(), plot_df["optimized_price"].max())

    plt.plot([min_price, max_price], [min_price, max_price], linestyle="--")
    plt.title("Current Price vs Optimized Price by Product Category")
    plt.xlabel("Current Price")
    plt.ylabel("Optimized Price")
    plt.grid(True)

    handles, _ = scatter.legend_elements()
    plt.legend(handles, list(categories.cat.categories), title="Product category")
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------

def run_pipeline(generate_plot: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """Run the complete price elasticity and optimization pipeline."""
    logger = setup_logger()
    logger.info("Price elasticity analysis started")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_pricing_data(INPUT_FILE)

    product_summary = build_product_summary(df)
    price_level = build_price_level_table(df, product_summary)
    price_level = add_elasticity_metrics(price_level)

    product_summary = add_price_recommendations(product_summary, price_level)

    selected_columns = [
        "product_id",
        "product_category",
        "price",
        "purchase_price",
        "traffic",
        "sales",
        "conversion_rate",
        "pre_optimized_price",
        "optimized_price",
        "recommended_price",
        "recommended_price_with_vat",
    ]

    optional_columns = [
        "sales_price_elasticity",
        "conversion_price_elasticity",
    ]

    price_level_elasticities = (
        price_level.groupby("product_id")[optional_columns]
        .first()
        .reset_index()
        if all(col in price_level.columns for col in optional_columns)
        else pd.DataFrame()
    )

    if not price_level_elasticities.empty:
        product_summary = product_summary.merge(price_level_elasticities, on="product_id", how="left")
        selected_columns += optional_columns

    selected_columns = [col for col in selected_columns if col in product_summary.columns]
    product_summary[selected_columns].to_excel(OUTPUT_FILE, index=False)

    metrics = evaluate_recommendations(product_summary)
    logger.info("Evaluation metrics: %s", metrics)

    if generate_plot:
        plot_current_vs_optimized_price(product_summary)

    print(f"Results saved to: {OUTPUT_FILE}")
    print("Evaluation metrics:")
    for key, value in metrics.items():
        print(f"- {key}: {value:.4f}")

    return product_summary, price_level, metrics


if __name__ == "__main__":
    run_pipeline(generate_plot=True)
