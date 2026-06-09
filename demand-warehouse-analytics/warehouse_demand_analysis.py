"""
Warehouse Demand Analytics
--------------------------
Portfolio-safe version.

Purpose:
    Compare warehouse performance using traffic, orders and sales data.
    The goal is to support demand and availability decisions through data.

Expected columns:
    product_id, date, country_group, customer_type, warehouse_type,
    views, orders, sales
"""

from pathlib import Path
import numpy as np
import pandas as pd


def standardize_product_id(df: pd.DataFrame, column: str = "product_id") -> pd.DataFrame:
    df = df.copy()
    df[column] = df[column].astype(str).str.strip().str.replace("_", "-", regex=False)
    return df


def parse_dates(df: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    df = df.copy()
    df[column] = pd.to_datetime(df[column], errors="coerce", dayfirst=True)
    return df


def prepare_warehouse_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize the warehouse analytics dataset."""
    required = {
        "product_id", "date", "country_group", "customer_type",
        "warehouse_type", "views", "orders", "sales",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    data = standardize_product_id(df, "product_id")
    data = parse_dates(data, "date")
    data = data.dropna(subset=["date", "product_id", "warehouse_type"])

    for col in ["views", "orders", "sales"]:
        data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0)

    data["warehouse_type"] = data["warehouse_type"].str.upper().str.strip()
    data = data[data["warehouse_type"].isin(["FAST", "STANDARD"])]
    data["conversion_rate"] = data["orders"] / data["views"].replace(0, np.nan)
    return data


def product_warehouse_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Compare conversion and sales between warehouse types at product level."""
    agg = df.groupby(["product_id", "warehouse_type"]).agg(
        views=("views", "sum"),
        orders=("orders", "sum"),
        sales=("sales", "sum"),
    ).reset_index()

    pivot = agg.pivot(index="product_id", columns="warehouse_type", values=["views", "orders", "sales"])
    pivot.columns = [f"{metric.lower()}_{warehouse.lower()}" for metric, warehouse in pivot.columns]
    pivot = pivot.reset_index().fillna(0)

    for warehouse in ["fast", "standard"]:
        pivot[f"cr_{warehouse}"] = pivot[f"orders_{warehouse}"] / pivot[f"views_{warehouse}"].replace(0, np.nan)

    pivot["cr_delta_fast_vs_standard"] = pivot["cr_fast"] - pivot["cr_standard"]
    pivot["total_sales"] = pivot.get("sales_fast", 0) + pivot.get("sales_standard", 0)
    pivot["total_orders"] = pivot.get("orders_fast", 0) + pivot.get("orders_standard", 0)

    return pivot.sort_values("total_sales", ascending=False)


def executive_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Build a high-level warehouse performance summary."""
    summary = df.groupby("warehouse_type").agg(
        views=("views", "sum"),
        orders=("orders", "sum"),
        sales=("sales", "sum"),
        products=("product_id", "nunique"),
    ).reset_index()
    summary["conversion_rate"] = summary["orders"] / summary["views"].replace(0, np.nan)
    summary["avg_order_value"] = summary["sales"] / summary["orders"].replace(0, np.nan)
    return summary


if __name__ == "__main__":
    path = Path("data/warehouse_sample.csv")
    if not path.exists():
        raise FileNotFoundError("Place a portfolio-safe sample dataset at data/warehouse_sample.csv")
    df_raw = pd.read_csv(path)
    df_clean = prepare_warehouse_dataset(df_raw)
    print(executive_summary(df_clean))
    print(product_warehouse_comparison(df_clean).head())
