"""
Cross-Channel Price & Conversion Analysis
========================================

Portfolio-safe version.

This script compares pricing and conversion performance between two sales channels:
- Web channel
- Marketplace channel

It calculates:
- Average price by channel
- Conversion rate by channel
- Price difference between channels
- Conversion rate difference between channels
- Outlier filtering using percentile thresholds
- Product-level and weekly summaries

All company-specific paths, internal folder names and private dataset references have been removed.

Expected input files:
- data/web_sessions.xlsx
- data/web_sales.xlsx
- data/marketplace_sales.xlsx

Author: Adrián Soler
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")

WEB_SESSIONS_FILE = DATA_DIR / "web_sessions.xlsx"
WEB_SALES_FILE = DATA_DIR / "web_sales.xlsx"
MARKETPLACE_SALES_FILE = DATA_DIR / "marketplace_sales.xlsx"

SUMMARY_OUTPUT_FILE = OUTPUT_DIR / "cross_channel_price_conversion_summary.xlsx"
PRODUCT_OUTPUT_FILE = OUTPUT_DIR / "product_level_price_conversion_summary.xlsx"


# ---------------------------------------------------------------------
# Loading and preparation
# ---------------------------------------------------------------------

def load_excel(path: Path) -> pd.DataFrame:
    """Load an Excel file and validate that it exists."""
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}. Place the file in the `data/` folder or update the path."
        )
    return pd.read_excel(path)


def standardize_input_tables(
    web_sessions: pd.DataFrame,
    web_sales: pd.DataFrame,
    marketplace_sales: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Standardize column names for channel comparison."""
    web_sessions = web_sessions.rename(
        columns={
            "idp_idc": "product_id",
            "IDP-IDC": "product_id",
            "Semana": "week",
            "Sesiones": "web_sessions",
        }
    ).copy()

    web_sales = web_sales.rename(
        columns={
            "idp_idc": "product_id",
            "IDP-IDC": "product_id",
            "Semana": "week",
            "Artículos_comprados": "web_units",
            "Artículos comprados": "web_units",
            "Ingresos_brutos_del_artículo": "web_revenue",
            "Ingresos brutos del artículo": "web_revenue",
        }
    ).copy()

    marketplace_sales = marketplace_sales.rename(
        columns={
            "idp_idc": "product_id",
            "IDP-IDC": "product_id",
            "Semana": "week",
            "Sesiones": "marketplace_sessions",
            "Artículos_comprados": "marketplace_units",
            "Artículos comprados": "marketplace_units",
            "Ingresos_brutos_del_artículo": "marketplace_revenue",
            "Ingresos brutos del artículo": "marketplace_revenue",
        }
    ).copy()

    for df in [web_sessions, web_sales, marketplace_sales]:
        df["product_id"] = df["product_id"].astype(str).str.strip()
        df["week"] = df["week"].astype(int)

    return web_sessions, web_sales, marketplace_sales


def convert_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Convert selected columns to numeric values."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def build_channel_dataset() -> pd.DataFrame:
    """Load, standardize and merge channel datasets."""
    web_sessions = load_excel(WEB_SESSIONS_FILE)
    web_sales = load_excel(WEB_SALES_FILE)
    marketplace_sales = load_excel(MARKETPLACE_SALES_FILE)

    web_sessions, web_sales, marketplace_sales = standardize_input_tables(
        web_sessions,
        web_sales,
        marketplace_sales,
    )

    web_sessions = convert_numeric_columns(web_sessions, ["web_sessions"])
    web_sales = convert_numeric_columns(web_sales, ["web_units", "web_revenue"])
    marketplace_sales = convert_numeric_columns(
        marketplace_sales,
        ["marketplace_sessions", "marketplace_units", "marketplace_revenue"],
    )

    web = web_sessions.merge(web_sales, on=["product_id", "week"], how="left")

    df = web.merge(
        marketplace_sales,
        on=["product_id", "week"],
        how="inner",
    )

    return df


# ---------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------

def calculate_channel_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate price, conversion rate and differences between channels."""
    df = df.copy()

    required_cols = [
        "web_sessions",
        "web_units",
        "web_revenue",
        "marketplace_sessions",
        "marketplace_units",
        "marketplace_revenue",
    ]
    df = df.dropna(subset=required_cols)

    df = df[
        (df["web_sessions"] > 0)
        & (df["marketplace_sessions"] > 0)
        & (df["web_units"] > 0)
        & (df["marketplace_units"] > 0)
    ].copy()

    df["web_price"] = df["web_revenue"] / df["web_units"]
    df["marketplace_price"] = df["marketplace_revenue"] / df["marketplace_units"]

    df["web_conversion_rate"] = df["web_units"] / df["web_sessions"]
    df["marketplace_conversion_rate"] = df["marketplace_units"] / df["marketplace_sessions"]

    df["price_difference"] = df["marketplace_price"] - df["web_price"]
    df["price_difference_pct"] = (df["marketplace_price"] / df["web_price"]) - 1

    df["conversion_rate_difference"] = (
        df["marketplace_conversion_rate"] - df["web_conversion_rate"]
    )
    df["conversion_rate_ratio"] = (
        df["marketplace_conversion_rate"] / df["web_conversion_rate"]
    )

    return df.replace([np.inf, -np.inf], np.nan)


def filter_outliers(
    df: pd.DataFrame,
    columns: list[str],
    lower_quantile: float = 0.01,
    upper_quantile: float = 0.99,
) -> pd.DataFrame:
    """Filter extreme values using percentile thresholds."""
    df = df.copy()

    for col in columns:
        if col not in df.columns:
            continue

        lower = df[col].quantile(lower_quantile)
        upper = df[col].quantile(upper_quantile)
        df = df[(df[col] >= lower) & (df[col] <= upper)]

    return df


def build_weekly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Create weekly summary comparing price and units between channels."""
    weekly = (
        df.groupby("week")
        .agg(
            web_price_mean=("web_price", "mean"),
            marketplace_price_mean=("marketplace_price", "mean"),
            web_units_mean=("web_units", "mean"),
            marketplace_units_mean=("marketplace_units", "mean"),
            web_revenue_mean=("web_revenue", "mean"),
            marketplace_revenue_mean=("marketplace_revenue", "mean"),
            web_conversion_rate_mean=("web_conversion_rate", "mean"),
            marketplace_conversion_rate_mean=("marketplace_conversion_rate", "mean"),
        )
        .reset_index()
    )

    weekly["price_difference"] = (
        weekly["marketplace_price_mean"] - weekly["web_price_mean"]
    )
    weekly["units_difference"] = (
        weekly["marketplace_units_mean"] - weekly["web_units_mean"]
    )
    weekly["conversion_rate_difference"] = (
        weekly["marketplace_conversion_rate_mean"] - weekly["web_conversion_rate_mean"]
    )

    return weekly


def build_product_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Create product-level summary comparing price and conversion between channels."""
    product_summary = (
        df.groupby("product_id")
        .agg(
            web_price_mean=("web_price", "mean"),
            marketplace_price_mean=("marketplace_price", "mean"),
            web_units_total=("web_units", "sum"),
            marketplace_units_total=("marketplace_units", "sum"),
            web_sessions_total=("web_sessions", "sum"),
            marketplace_sessions_total=("marketplace_sessions", "sum"),
            web_revenue_total=("web_revenue", "sum"),
            marketplace_revenue_total=("marketplace_revenue", "sum"),
        )
        .reset_index()
    )

    product_summary["price_difference"] = (
        product_summary["marketplace_price_mean"] - product_summary["web_price_mean"]
    )

    product_summary["web_conversion_rate"] = (
        product_summary["web_units_total"] / product_summary["web_sessions_total"]
    )
    product_summary["marketplace_conversion_rate"] = (
        product_summary["marketplace_units_total"]
        / product_summary["marketplace_sessions_total"]
    )
    product_summary["conversion_rate_difference"] = (
        product_summary["marketplace_conversion_rate"]
        - product_summary["web_conversion_rate"]
    )

    return product_summary.replace([np.inf, -np.inf], np.nan)


# ---------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------

def plot_price_vs_conversion(df: pd.DataFrame) -> None:
    """Scatter plot showing the relationship between price and conversion rate."""
    plt.figure(figsize=(10, 6))
    plt.scatter(df["web_price"], df["web_conversion_rate"], alpha=0.5, label="Web")
    plt.scatter(
        df["marketplace_price"],
        df["marketplace_conversion_rate"],
        alpha=0.5,
        label="Marketplace",
    )
    plt.title("Price vs Conversion Rate by Channel")
    plt.xlabel("Price")
    plt.ylabel("Conversion Rate")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_price_difference_vs_conversion_difference(product_summary: pd.DataFrame) -> None:
    """Scatter plot showing product-level price difference vs conversion difference."""
    plt.figure(figsize=(10, 6))
    plt.scatter(
        product_summary["price_difference"],
        product_summary["conversion_rate_difference"],
        alpha=0.6,
    )
    plt.axhline(0, linestyle="--")
    plt.axvline(0, linestyle="--")
    plt.title("Price Difference vs Conversion Rate Difference")
    plt.xlabel("Price Difference: Marketplace - Web")
    plt.ylabel("Conversion Rate Difference: Marketplace - Web")
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_correlation_matrix(df: pd.DataFrame) -> None:
    """Plot a simple correlation matrix using matplotlib only."""
    cols = [
        "web_price",
        "marketplace_price",
        "price_difference",
        "price_difference_pct",
        "web_conversion_rate",
        "marketplace_conversion_rate",
        "conversion_rate_difference",
    ]

    corr = df[cols].corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    cax = ax.imshow(corr, interpolation="nearest")
    fig.colorbar(cax)

    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right")
    ax.set_yticklabels(cols)

    for i in range(len(cols)):
        for j in range(len(cols)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center")

    plt.title("Correlation Matrix")
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------

def run_analysis(generate_plots: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run full cross-channel price and conversion analysis."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    raw = build_channel_dataset()
    analysed = calculate_channel_metrics(raw)

    analysed = filter_outliers(
        analysed,
        columns=[
            "price_difference_pct",
            "conversion_rate_difference",
            "conversion_rate_ratio",
        ],
    )

    weekly_summary = build_weekly_summary(analysed)
    product_summary = build_product_summary(analysed)

    analysed.to_excel(SUMMARY_OUTPUT_FILE, index=False)
    product_summary.to_excel(PRODUCT_OUTPUT_FILE, index=False)

    if generate_plots:
        plot_price_vs_conversion(analysed)
        plot_price_difference_vs_conversion_difference(product_summary)
        plot_correlation_matrix(analysed)

    print(f"Detailed analysis saved to: {SUMMARY_OUTPUT_FILE}")
    print(f"Product summary saved to: {PRODUCT_OUTPUT_FILE}")

    return analysed, weekly_summary, product_summary


if __name__ == "__main__":
    run_analysis(generate_plots=True)
