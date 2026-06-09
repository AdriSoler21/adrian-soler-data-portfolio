"""
Warehouse Demand & Conversion Analysis
=====================================

Portfolio-safe version.

This script builds a monthly conversion table by combining:
- Product views / traffic data
- Sales orders
- Warehouse classification history
- Product family metadata
- Product validity flags

The goal is to analyse product demand and conversion performance by warehouse type,
country group, customer type, product family and month.

All company-specific paths, internal folders, sensitive product family names and private
dataset references have been removed.

Expected input files:
- data/product_views.csv
- data/sales_orders.xlsx
- data/product_families.xlsx
- data/valid_products.xlsx
- data/warehouse_classification.csv

Author: Adrián Soler
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")

PRODUCT_VIEWS_FILE = DATA_DIR / "product_views.csv"
SALES_ORDERS_FILE = DATA_DIR / "sales_orders.xlsx"
PRODUCT_FAMILIES_FILE = DATA_DIR / "product_families.xlsx"
VALID_PRODUCTS_FILE = DATA_DIR / "valid_products.xlsx"
WAREHOUSE_CLASSIFICATION_FILE = DATA_DIR / "warehouse_classification.csv"

MONTHLY_CONVERSION_OUTPUT = OUTPUT_DIR / "monthly_warehouse_conversion_table.xlsx"
ORDER_WAREHOUSE_OUTPUT = OUTPUT_DIR / "orders_with_warehouse_classification.xlsx"


MONTH_MAP_ES_TO_EN = {
    "ene": "Jan",
    "feb": "Feb",
    "mar": "Mar",
    "abr": "Apr",
    "may": "May",
    "jun": "Jun",
    "jul": "Jul",
    "ago": "Aug",
    "sep": "Sep",
    "sept": "Sep",
    "sept.": "Sep",
    "oct": "Oct",
    "nov": "Nov",
    "dic": "Dec",
}


# ---------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------

def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV file with validation."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}. Place it in the `data/` folder.")
    return pd.read_csv(path)


def load_excel(path: Path) -> pd.DataFrame:
    """Load an Excel file with validation."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}. Place it in the `data/` folder.")
    return pd.read_excel(path)


def clean_product_id(series: pd.Series) -> pd.Series:
    """Normalize product IDs to avoid merge issues."""
    s = series.astype("string").str.strip()
    s = s.str.replace("_", "-", regex=False)
    s = s.str.replace(r"\s+", "", regex=True)
    s = s.str.replace(r"\.0$", "", regex=True)
    return s.replace({"": pd.NA, "nan": pd.NA, "<NA>": pd.NA})


def normalize_column_name(column: str) -> str:
    """Create a simplified column name for matching."""
    return (
        str(column)
        .strip()
        .lower()
        .replace("–", "-")
        .replace("—", "-")
        .replace("_", "-")
        .replace(" ", "")
    )


def standardize_product_id_column(df: pd.DataFrame) -> pd.DataFrame:
    """Find and standardize product ID column to `product_id`."""
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()

    product_col = None
    for col in df.columns:
        normalized = normalize_column_name(col)
        if normalized in {"product-id", "idp-idc"} or ("idp" in normalized and "idc" in normalized):
            product_col = col
            break
        if normalized == "productid":
            product_col = col
            break

    if product_col is None:
        raise KeyError(f"No product ID column found. Columns available: {list(df.columns)}")

    df = df.rename(columns={product_col: "product_id"})
    df["product_id"] = clean_product_id(df["product_id"])

    return df


def parse_date_es(series: pd.Series) -> pd.Series:
    """Parse dates that may include Spanish month abbreviations."""
    s = series.astype("string").str.strip().str.lower()

    for es_month, en_month in MONTH_MAP_ES_TO_EN.items():
        s = s.str.replace(rf"\b{es_month}\b", en_month, regex=True)

    date_iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    date_fallback = pd.to_datetime(s, errors="coerce", dayfirst=True)

    return date_iso.combine_first(date_fallback)


def normalize_country_group(series: pd.Series) -> pd.Series:
    """Group or standardize country values for analysis."""
    return series.replace(
        {
            "Country A": "Country Group A",
            "Country B": "Country Group A",
            "Germany": "Central Europe",
            "Netherlands": "Central Europe",
            "Alemania": "Central Europe",
            "Países Bajos": "Central Europe",
        }
    )


# ---------------------------------------------------------------------
# Loading and standardization
# ---------------------------------------------------------------------

def load_datasets() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all datasets used in the analysis."""
    product_views = load_csv(PRODUCT_VIEWS_FILE)
    sales_orders = load_excel(SALES_ORDERS_FILE)
    product_families = load_excel(PRODUCT_FAMILIES_FILE)
    valid_products = load_excel(VALID_PRODUCTS_FILE)
    warehouse_classification = load_csv(WAREHOUSE_CLASSIFICATION_FILE)

    datasets = [
        product_views,
        sales_orders,
        product_families,
        valid_products,
        warehouse_classification,
    ]

    standardized = [standardize_product_id_column(df) for df in datasets]

    return tuple(standardized)


def standardize_input_columns(
    product_views: pd.DataFrame,
    sales_orders: pd.DataFrame,
    product_families: pd.DataFrame,
    valid_products: pd.DataFrame,
    warehouse_classification: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Rename expected business columns to portfolio-safe names."""
    product_views = product_views.rename(
        columns={
            "event_date": "view_date",
            "ambito_pais": "country_group",
            "Tipo_Cliente": "customer_type",
            "event_view_item": "views",
        }
    ).copy()

    sales_orders = sales_orders.rename(
        columns={
            "order_date": "order_date",
            "grupo_pais": "country_group",
            "Tipo_Cliente": "customer_type",
            "Tipo_cliente": "customer_type",
            "id_order": "order_id",
            "evente_purchase": "orders",
            "Total_sale": "sales",
            "Total": "sales",
        }
    ).copy()

    product_families = product_families.rename(
        columns={
            "Family": "product_family",
            "familia": "product_family",
            "product_home": "product_group",
            "Spectrum": "product_spectrum",
        }
    ).copy()

    valid_products = valid_products.rename(
        columns={
            "2022_2025": "is_valid_product",
            "valid": "is_valid_product",
        }
    ).copy()

    warehouse_classification = warehouse_classification.rename(
        columns={
            "event_date": "classification_date",
            "Clasif. Almacen": "warehouse_classification",
            "clasif_almacen": "warehouse_classification",
            "event_view_item": "views",
        }
    ).copy()

    return product_views, sales_orders, product_families, valid_products, warehouse_classification


# ---------------------------------------------------------------------
# Warehouse classification logic
# ---------------------------------------------------------------------

def resolve_daily_warehouse_classification(group: pd.DataFrame) -> str:
    """
    Resolve conflicting warehouse classifications for the same product and date.

    Rule:
    - Select the classification with the highest number of views.
    - If there is a tie, prioritize the fast-delivery warehouse label if present.
    """
    summary = (
        group.groupby("warehouse_classification", dropna=False)["views"]
        .sum()
        .reset_index()
    )

    max_views = summary["views"].max()
    candidates = summary.loc[
        summary["views"] == max_views,
        "warehouse_classification",
    ]

    preferred_label = "FAST_DELIVERY"
    if preferred_label in candidates.values:
        return preferred_label

    return candidates.iloc[0]


def build_warehouse_reference(warehouse_classification: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create warehouse reference tables for as-of merging and fallback matching."""
    df = warehouse_classification.copy()

    required_columns = ["product_id", "classification_date", "warehouse_classification", "views"]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing warehouse classification columns: {missing}")

    df["classification_date"] = parse_date_es(df["classification_date"])
    df["views"] = pd.to_numeric(df["views"], errors="coerce").fillna(0)

    daily_reference = (
        df.groupby(["product_id", "classification_date"], dropna=False)
        .apply(resolve_daily_warehouse_classification)
        .reset_index(name="warehouse_classification")
    )

    asof_reference = (
        daily_reference
        .dropna(subset=["classification_date", "warehouse_classification"])
        .sort_values(["classification_date", "product_id"], kind="mergesort")
        .reset_index(drop=True)
    )

    fallback_reference = (
        asof_reference.groupby("product_id")["warehouse_classification"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "UNKNOWN")
        .reset_index()
    )

    return asof_reference, fallback_reference


def assign_warehouse_classification(
    df: pd.DataFrame,
    date_column: str,
    warehouse_reference: pd.DataFrame,
    fallback_reference: pd.DataFrame,
) -> pd.DataFrame:
    """Assign nearest warehouse classification by product and date."""
    df = df.copy()

    date_missing_mask = df[date_column].isna()
    df_missing_dates = df.loc[date_missing_mask].copy()

    df_with_dates = (
        df.loc[~date_missing_mask]
        .sort_values([date_column, "product_id"], kind="mergesort")
        .reset_index(drop=True)
    )

    classified = pd.merge_asof(
        df_with_dates,
        warehouse_reference,
        left_on=date_column,
        right_on="classification_date",
        by="product_id",
        direction="nearest",
    )

    classified = classified.merge(
        fallback_reference,
        on="product_id",
        how="left",
        suffixes=("", "_fallback"),
    )

    classified["warehouse_classification"] = (
        classified["warehouse_classification"]
        .fillna(classified["warehouse_classification_fallback"])
        .fillna("UNKNOWN")
    )

    df_missing_dates["warehouse_classification"] = "UNKNOWN"

    result = pd.concat([classified, df_missing_dates], ignore_index=True)

    if "classification_date" in result.columns:
        result = result.drop(columns=["classification_date"])

    return result


# ---------------------------------------------------------------------
# Monthly conversion table
# ---------------------------------------------------------------------

def build_monthly_conversion_table(
    product_views: pd.DataFrame,
    sales_orders: pd.DataFrame,
    product_families: pd.DataFrame,
    valid_products: pd.DataFrame,
    warehouse_classification: pd.DataFrame,
) -> pd.DataFrame:
    """Build monthly conversion table by product, warehouse, country and customer type."""
    product_views = product_views.copy()
    sales_orders = sales_orders.copy()

    warehouse_reference, fallback_reference = build_warehouse_reference(warehouse_classification)

    product_views["view_date"] = parse_date_es(product_views["view_date"])
    sales_orders["order_date"] = parse_date_es(sales_orders["order_date"])

    product_views["country_group"] = normalize_country_group(product_views["country_group"])
    sales_orders["country_group"] = normalize_country_group(sales_orders["country_group"])

    product_views["views"] = pd.to_numeric(product_views["views"], errors="coerce").fillna(0)
    sales_orders["sales"] = pd.to_numeric(sales_orders["sales"], errors="coerce").fillna(0)

    product_views = product_views.loc[
        product_views["views"] > 0,
        ["product_id", "view_date", "country_group", "customer_type", "views"],
    ].copy()

    product_views = assign_warehouse_classification(
        product_views,
        date_column="view_date",
        warehouse_reference=warehouse_reference,
        fallback_reference=fallback_reference,
    )

    sales_orders = assign_warehouse_classification(
        sales_orders,
        date_column="order_date",
        warehouse_reference=warehouse_reference,
        fallback_reference=fallback_reference,
    )

    product_views["year_month"] = product_views["view_date"].dt.to_period("M").astype(str)
    sales_orders["year_month"] = sales_orders["order_date"].dt.to_period("M").astype(str)

    views_month = (
        product_views
        .groupby(
            ["year_month", "product_id", "warehouse_classification", "country_group", "customer_type"],
            dropna=False,
        )
        .agg(views=("views", "sum"))
        .reset_index()
    )

    orders_month = (
        sales_orders
        .groupby(
            ["year_month", "product_id", "warehouse_classification", "country_group", "customer_type"],
            dropna=False,
        )
        .agg(
            orders=("order_id", "nunique"),
            sales=("sales", "sum"),
        )
        .reset_index()
    )

    monthly_conversion = views_month.merge(
        orders_month,
        on=["year_month", "product_id", "warehouse_classification", "country_group", "customer_type"],
        how="left",
    )

    monthly_conversion["orders"] = monthly_conversion["orders"].fillna(0).astype(int)
    monthly_conversion["sales"] = monthly_conversion["sales"].fillna(0)
    monthly_conversion["conversion_rate"] = np.where(
        monthly_conversion["views"] > 0,
        monthly_conversion["orders"] / monthly_conversion["views"],
        np.nan,
    )

    family_columns = [
        col for col in ["product_id", "product_family", "product_group", "product_spectrum"]
        if col in product_families.columns
    ]

    if len(family_columns) > 1:
        monthly_conversion = monthly_conversion.merge(
            product_families[family_columns].drop_duplicates("product_id"),
            on="product_id",
            how="left",
        )

    if "is_valid_product" in valid_products.columns:
        monthly_conversion = monthly_conversion.merge(
            valid_products[["product_id", "is_valid_product"]].drop_duplicates("product_id"),
            on="product_id",
            how="left",
        )

    for col in ["product_family", "product_group", "product_spectrum"]:
        if col in monthly_conversion.columns:
            monthly_conversion[col] = monthly_conversion[col].fillna("UNKNOWN")

    if "is_valid_product" in monthly_conversion.columns:
        monthly_conversion["is_valid_product"] = (
            monthly_conversion["is_valid_product"].fillna(0).astype(int)
        )

    return monthly_conversion


# ---------------------------------------------------------------------
# Data quality checks
# ---------------------------------------------------------------------

def detect_classification_conflicts(warehouse_classification: pd.DataFrame) -> pd.DataFrame:
    """Detect products with more than one warehouse classification on the same date."""
    df = warehouse_classification.copy()
    df["classification_date"] = parse_date_es(df["classification_date"])

    conflicts = (
        df.groupby(["product_id", "classification_date"])["warehouse_classification"]
        .nunique()
        .reset_index(name="different_classifications")
    )

    return conflicts[conflicts["different_classifications"] > 1]


def detect_frequent_warehouse_changes(warehouse_reference: pd.DataFrame, min_days: int = 5, max_ratio: float = 0.30) -> pd.DataFrame:
    """Detect products with frequent changes in warehouse classification."""
    df = (
        warehouse_reference
        .sort_values(["product_id", "classification_date"])
        .reset_index(drop=True)
        .copy()
    )

    df["previous_classification"] = df.groupby("product_id")["warehouse_classification"].shift(1)
    df["classification_changed"] = df["warehouse_classification"] != df["previous_classification"]

    summary = (
        df.groupby("product_id")
        .agg(
            total_days=("classification_date", "nunique"),
            total_changes=("classification_changed", "sum"),
        )
        .reset_index()
    )

    summary["change_ratio"] = summary["total_changes"] / summary["total_days"]

    return summary[
        (summary["total_days"] >= min_days)
        & (summary["change_ratio"] > max_ratio)
    ]


def build_order_warehouse_table(sales_orders: pd.DataFrame) -> pd.DataFrame:
    """Create one warehouse classification per order using the most frequent classification."""
    return (
        sales_orders.groupby("order_id")["warehouse_classification"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "UNKNOWN")
        .reset_index()
    )


# ---------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------

def run_pipeline() -> pd.DataFrame:
    """Run the full warehouse demand analysis pipeline."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    (
        product_views,
        sales_orders,
        product_families,
        valid_products,
        warehouse_classification,
    ) = load_datasets()

    (
        product_views,
        sales_orders,
        product_families,
        valid_products,
        warehouse_classification,
    ) = standardize_input_columns(
        product_views,
        sales_orders,
        product_families,
        valid_products,
        warehouse_classification,
    )

    monthly_conversion = build_monthly_conversion_table(
        product_views,
        sales_orders,
        product_families,
        valid_products,
        warehouse_classification,
    )

    monthly_conversion.to_excel(MONTHLY_CONVERSION_OUTPUT, index=False)

    warehouse_reference, _ = build_warehouse_reference(warehouse_classification)
    conflicts = detect_classification_conflicts(warehouse_classification)
    suspicious_changes = detect_frequent_warehouse_changes(warehouse_reference)

    print(f"Monthly conversion table saved to: {MONTHLY_CONVERSION_OUTPUT}")
    print(f"Warehouse classification conflicts detected: {len(conflicts)}")
    print(f"Products with frequent warehouse classification changes: {len(suspicious_changes)}")

    return monthly_conversion


if __name__ == "__main__":
    run_pipeline()
