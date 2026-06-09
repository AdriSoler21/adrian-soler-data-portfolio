"""
Price Elasticity Analysis
-------------------------
Portfolio-safe version.

Purpose:
    Estimate product-level relationship between price and demand/conversion,
    classify products by traffic and conversion, and support pricing decisions.

Expected input file:
    data/pricing_sample.csv

Expected columns:
    product_id, period, price, units_sold, traffic, stock, purchase_cost
"""

from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import linregress


def normalize_price(price: float) -> float:
    """Round prices into business-friendly price steps."""
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


def classify_product(row: pd.Series, low_traffic: float, high_traffic: float) -> str:
    traffic = row["traffic_total"]
    conversion = row["conversion_rate"]

    if traffic < 25 or pd.isna(conversion):
        return "Invisible product"
    if traffic > high_traffic and conversion > 0.01:
        return "Best seller"
    if traffic > high_traffic and conversion < 0.01:
        return "At risk"
    if traffic < low_traffic and conversion > 0.03:
        return "Hidden winner"
    if conversion < 0.01:
        return "Needs adjustment"
    return "Stable product"


def build_product_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Build a product-level summary with traffic, sales and conversion metrics."""
    data = df.copy()
    data["price"] = pd.to_numeric(data["price"], errors="coerce")
    data["units_sold"] = pd.to_numeric(data["units_sold"], errors="coerce").fillna(0)
    data["traffic"] = pd.to_numeric(data["traffic"], errors="coerce").fillna(0)

    product = data.groupby("product_id").agg(
        current_price=("price", "last"),
        units_total=("units_sold", "sum"),
        traffic_total=("traffic", "sum"),
        stock_last=("stock", "last"),
        purchase_cost=("purchase_cost", "last"),
    ).reset_index()

    product["conversion_rate"] = product["units_total"] / product["traffic_total"].replace(0, np.nan)
    product["normalized_price"] = product["current_price"].apply(normalize_price)

    traffic_by_product = product["traffic_total"]
    low_traffic = traffic_by_product.quantile(0.30)
    high_traffic = traffic_by_product.quantile(0.80)
    product["product_category"] = product.apply(classify_product, axis=1, args=(low_traffic, high_traffic))

    return product


def estimate_elasticity(df: pd.DataFrame) -> pd.DataFrame:
    """Estimate simple log-log price elasticity per product."""
    data = df.copy()
    data = data[(data["price"] > 0) & (data["units_sold"] > 0)]
    results = []

    for product_id, group in data.groupby("product_id"):
        if group["price"].nunique() < 2 or len(group) < 4:
            continue
        x = np.log(group["price"])
        y = np.log(group["units_sold"])
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        results.append({
            "product_id": product_id,
            "elasticity": slope,
            "r_squared": r_value ** 2,
            "p_value": p_value,
            "observations": len(group),
        })

    return pd.DataFrame(results).sort_values("r_squared", ascending=False)


if __name__ == "__main__":
    path = Path("data/pricing_sample.csv")
    if not path.exists():
        raise FileNotFoundError("Place a portfolio-safe sample dataset at data/pricing_sample.csv")
    df_pricing = pd.read_csv(path)
    print(build_product_summary(df_pricing).head())
    print(estimate_elasticity(df_pricing).head())
