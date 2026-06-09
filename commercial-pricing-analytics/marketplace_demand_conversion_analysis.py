"""
Marketplace Demand & Conversion Analysis
=======================================

Portfolio-safe version.

This script analyses sales, conversion and price behaviour across two sales channels:
- Web channel
- Marketplace channel

The original business-specific paths, credentials, property IDs and internal names have been
removed. The script expects already-exported CSV/Excel files in a local `data/` folder.

Suggested input files:
- data/web_sales.xlsx
- data/marketplace_sales.xlsx
- data/product_family_mapping.xlsx

Author: Adrián Soler
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")

WEB_SALES_FILE = DATA_DIR / "web_sales.xlsx"
MARKETPLACE_SALES_FILE = DATA_DIR / "marketplace_sales.xlsx"
PRODUCT_FAMILY_FILE = DATA_DIR / "product_family_mapping.xlsx"

OUTPUT_FILE = OUTPUT_DIR / "marketplace_demand_conversion_analysis.xlsx"


# ---------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------

def load_excel_file(path: Path, sheet_name: str | int = 0) -> pd.DataFrame:
    """Load an Excel file with a simple validation message."""
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}. "
            "Place the input file in the expected data folder or update the path."
        )
    return pd.read_excel(path, sheet_name=sheet_name)


def standardize_columns(df: pd.DataFrame, rename_map: dict[str, str]) -> pd.DataFrame:
    """Rename columns and standardize week/product identifiers."""
    df = df.rename(columns=rename_map).copy()

    if "product_id" in df.columns:
        df["product_id"] = df["product_id"].astype(str).str.strip()

    if "week" in df.columns:
        df["week"] = df["week"].astype(str).str.strip()

    return df


def load_datasets() -> tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
    """Load web, marketplace and optional product family mapping datasets."""
    web = load_excel_file(WEB_SALES_FILE)
    marketplace = load_excel_file(MARKETPLACE_SALES_FILE)

    product_family = None
    if PRODUCT_FAMILY_FILE.exists():
        product_family = load_excel_file(PRODUCT_FAMILY_FILE)

    web = standardize_columns(
        web,
        {
            "IDP-IDC": "product_id",
            "idp_idc": "product_id",
            "Semana": "week",
            "Sesiones": "web_sessions",
            "Unidades": "web_units",
            "Pedidos": "web_orders",
            "Ventas": "web_revenue",
            "Precio": "web_price",
            "Stock": "web_stock",
        },
    )

    marketplace = standardize_columns(
        marketplace,
        {
            "IDP-IDC": "product_id",
            "idp_idc": "product_id",
            "Semana": "week",
            "Sesiones": "marketplace_sessions",
            "Unidades encargadas": "marketplace_units",
            "Unidades": "marketplace_units",
            "Ventas": "marketplace_revenue",
            "Precio": "marketplace_price",
        },
    )

    if product_family is not None:
        product_family = standardize_columns(
            product_family,
            {
                "IDP-IDC": "product_id",
                "idp_idc": "product_id",
                "familia": "family",
                "Family": "family",
                "spectrum": "spectrum",
                "Spectrum": "spectrum",
            },
        )

    return web, marketplace, product_family


# ---------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------

def prepare_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Convert selected columns to numeric values."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def merge_channel_data(
    web: pd.DataFrame,
    marketplace: pd.DataFrame,
    product_family: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Merge web and marketplace data at product-week level."""
    df = marketplace.merge(
        web,
        on=["product_id", "week"],
        how="left",
        suffixes=("_marketplace", "_web"),
    )

    if product_family is not None and "product_id" in product_family.columns:
        family_cols = [col for col in ["product_id", "family", "spectrum"] if col in product_family.columns]
        df = df.merge(product_family[family_cols].drop_duplicates(), on="product_id", how="left")

    return df


def impute_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Replace zero prices with NaN and impute prices by product using forward/backward fill."""
    df = df.copy()

    for col in ["marketplace_price", "web_price"]:
        if col in df.columns:
            df[col] = df[col].replace(0, np.nan)
            df[col] = (
                df.sort_values(["product_id", "week"])
                .groupby("product_id")[col]
                .transform(lambda x: x.ffill().bfill())
            )

    return df


# ---------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------

def calculate_elasticities(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate demand, stock and price elasticity indicators.

    Notes:
    - Elasticities are calculated using percentage changes over time by product.
    - The result should be interpreted as an analytical indicator, not as a causal model.
    """
    required = [
        "product_id",
        "week",
        "web_revenue",
        "web_units",
        "web_stock",
        "marketplace_revenue",
        "marketplace_price",
        "web_price",
    ]

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    df = df.dropna(
        subset=[
            "web_revenue",
            "web_units",
            "web_stock",
            "marketplace_revenue",
            "marketplace_price",
            "web_price",
        ]
    ).copy()

    df = df.sort_values(["product_id", "week"])

    # Web demand changes
    df["pct_change_web_revenue"] = df.groupby("product_id")["web_revenue"].pct_change()
    df["pct_change_web_units"] = df.groupby("product_id")["web_units"].pct_change()
    df["pct_change_web_stock"] = df.groupby("product_id")["web_stock"].pct_change()

    # Marketplace price / revenue changes
    df["pct_change_marketplace_revenue"] = df.groupby("product_id")["marketplace_revenue"].pct_change()
    df["pct_change_marketplace_price"] = df.groupby("product_id")["marketplace_price"].pct_change()

    # Elasticity indicators
    df["demand_elasticity_units"] = df["pct_change_web_revenue"] / df["pct_change_web_units"]
    df["demand_elasticity_stock"] = df["pct_change_web_revenue"] / df["pct_change_web_stock"]
    df["marketplace_price_elasticity"] = (
        df["pct_change_marketplace_revenue"] / df["pct_change_marketplace_price"]
    )

    # Simplified cross-elasticity proxy
    df["cross_elasticity_proxy"] = (
        df["pct_change_marketplace_revenue"] / df["pct_change_marketplace_price"]
    )

    # Clean infinite values
    elasticity_cols = [
        "demand_elasticity_units",
        "demand_elasticity_stock",
        "marketplace_price_elasticity",
        "cross_elasticity_proxy",
    ]
    df[elasticity_cols] = df[elasticity_cols].replace([np.inf, -np.inf], np.nan)

    return df


def classify_demand_elasticity(value: float) -> str:
    """Classify demand elasticity."""
    if pd.isna(value):
        return "Unknown"
    if value <= 0:
        return "Low"
    if value <= 1:
        return "Moderate"
    return "High"


def classify_price_elasticity(value: float) -> str:
    """Classify price elasticity."""
    if pd.isna(value):
        return "Unknown"
    if value < 0:
        return "Inelastic"
    if value <= 1:
        return "Low sensitivity"
    return "Elastic"


def classify_cross_elasticity(value: float) -> str:
    """Classify simplified cross-elasticity behaviour."""
    if pd.isna(value):
        return "Unknown"
    if value > 0:
        return "Substitute behaviour"
    if value < 0:
        return "Complementary behaviour"
    return "Independent behaviour"


def add_classifications(df: pd.DataFrame) -> pd.DataFrame:
    """Add categorical classifications for elasticity indicators."""
    df = df.copy()

    df["demand_units_class"] = df["demand_elasticity_units"].apply(classify_demand_elasticity)
    df["demand_stock_class"] = df["demand_elasticity_stock"].apply(classify_demand_elasticity)
    df["marketplace_price_class"] = df["marketplace_price_elasticity"].apply(classify_price_elasticity)
    df["cross_elasticity_class"] = df["cross_elasticity_proxy"].apply(classify_cross_elasticity)

    return df


def build_output_table(df: pd.DataFrame) -> pd.DataFrame:
    """Select final columns for reporting."""
    columns = [
        "product_id",
        "week",
        "family",
        "spectrum",
        "web_revenue",
        "marketplace_revenue",
        "web_price",
        "marketplace_price",
        "web_stock",
        "demand_elasticity_units",
        "demand_elasticity_stock",
        "marketplace_price_elasticity",
        "cross_elasticity_proxy",
        "demand_units_class",
        "demand_stock_class",
        "marketplace_price_class",
        "cross_elasticity_class",
    ]

    existing_columns = [col for col in columns if col in df.columns]
    return df[existing_columns].copy()


# ---------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------

def run_pipeline() -> pd.DataFrame:
    """Run the complete analysis pipeline."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    web, marketplace, product_family = load_datasets()

    numeric_cols_web = ["web_sessions", "web_units", "web_orders", "web_revenue", "web_price", "web_stock"]
    numeric_cols_marketplace = ["marketplace_sessions", "marketplace_units", "marketplace_revenue", "marketplace_price"]

    web = prepare_numeric_columns(web, numeric_cols_web)
    marketplace = prepare_numeric_columns(marketplace, numeric_cols_marketplace)

    merged = merge_channel_data(web, marketplace, product_family)
    merged = impute_prices(merged)

    analysed = calculate_elasticities(merged)
    analysed = add_classifications(analysed)
    output = build_output_table(analysed)

    output.to_excel(OUTPUT_FILE, index=False)
    print(f"Analysis completed. Output saved to: {OUTPUT_FILE}")

    return output


if __name__ == "__main__":
    run_pipeline()
