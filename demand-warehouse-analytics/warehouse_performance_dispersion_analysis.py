"""
Warehouse Performance Dispersion Analysis
=========================================

Portfolio-safe version.

This script analyses the performance dispersion between two warehouse / fulfilment
classifications by comparing conversion rates, total sales and order volume.

It supports:
- Product-level aggregation
- Conversion rate comparison between two fulfilment groups
- Delta calculation between fulfilment groups
- Filtering by country, customer type, product family and product attributes
- Scatter / density / hexbin visualizations

All company-specific paths, internal labels and private dataset references have been removed.

Expected input file:
- data/warehouse_performance_table.xlsx

Expected columns:
- product_id
- warehouse_classification
- country_group
- customer_type
- product_family
- product_spectrum
- product_group
- views
- orders
- sales
- months_group_a
- months_group_b

Author: Adrián Soler
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from scipy.stats import gaussian_kde


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")

INPUT_FILE = DATA_DIR / "warehouse_performance_table.xlsx"
OUTPUT_FILE = OUTPUT_DIR / "warehouse_dispersion_product_metrics.xlsx"

WAREHOUSE_GROUP_A = "GROUP_A"
WAREHOUSE_GROUP_B = "GROUP_B"


# ---------------------------------------------------------------------
# Loading and preparation
# ---------------------------------------------------------------------

def load_dataset(path: Path = INPUT_FILE) -> pd.DataFrame:
    """Load the warehouse performance dataset."""
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}. Place the dataset in the `data/` folder or update INPUT_FILE."
        )

    df = pd.read_excel(path)

    rename_map = {
        "idp_idc": "product_id",
        "IDP-IDC": "product_id",
        "clasif_almacen": "warehouse_classification",
        "Clasif. Almacen": "warehouse_classification",
        "grupo_pais": "country_group",
        "ambito_pais": "country_group",
        "tipo_cliente": "customer_type",
        "Tipo_Cliente": "customer_type",
        "Tipo_cliente": "customer_type",
        "Family": "product_family",
        "Spectrum": "product_spectrum",
        "product_home": "product_group",
        "view_item": "views",
        "event_view_item": "views",
        "Meses ALF": "months_group_a",
        "Meses ALM": "months_group_b",
    }

    df = df.rename(columns=rename_map)

    required_columns = [
        "product_id",
        "warehouse_classification",
        "views",
        "orders",
        "sales",
    ]

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    return df


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize numeric and categorical columns."""
    df = df.copy()

    numeric_columns = [
        "views",
        "orders",
        "sales",
        "months_group_a",
        "months_group_b",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    categorical_columns = [
        "warehouse_classification",
        "country_group",
        "customer_type",
        "product_family",
        "product_spectrum",
        "product_group",
        "product_id",
    ]

    for col in categorical_columns:
        if col in df.columns:
            df[col] = df[col].astype("string").fillna("UNKNOWN")

    # Map original internal labels to generic labels if present
    df["warehouse_classification"] = df["warehouse_classification"].replace(
        {
            "ALF": WAREHOUSE_GROUP_A,
            "ALM": WAREHOUSE_GROUP_B,
        }
    )

    df = df[
        df["warehouse_classification"].isin([WAREHOUSE_GROUP_A, WAREHOUSE_GROUP_B])
    ].copy()

    return df


# ---------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------

def filter_dataset(
    df: pd.DataFrame,
    country_groups: Optional[Iterable[str]] = None,
    customer_types: Optional[Iterable[str]] = None,
    product_families: Optional[Iterable[str]] = None,
    product_groups: Optional[Iterable[str]] = None,
    product_spectrums: Optional[Iterable[str]] = None,
    min_months_group_a: int = 0,
    min_months_group_b: int = 0,
) -> pd.DataFrame:
    """Apply optional categorical filters and minimum month coverage filters."""
    filtered = df.copy()

    filter_map = {
        "country_group": country_groups,
        "customer_type": customer_types,
        "product_family": product_families,
        "product_group": product_groups,
        "product_spectrum": product_spectrums,
    }

    for column, values in filter_map.items():
        if values and column in filtered.columns:
            filtered = filtered[filtered[column].isin(list(values))]

    month_columns_present = {"months_group_a", "months_group_b"}.issubset(filtered.columns)
    if month_columns_present:
        product_months = (
            filtered.groupby("product_id", as_index=True)[["months_group_a", "months_group_b"]]
            .max()
        )

        valid_product_ids = product_months[
            (product_months["months_group_a"] >= min_months_group_a)
            & (product_months["months_group_b"] >= min_months_group_b)
        ].index

        filtered = filtered[filtered["product_id"].isin(valid_product_ids)]

    return filtered


# ---------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------

def compute_product_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate product-level conversion rate delta and total business metrics."""
    grouped = (
        df.groupby(["product_id", "warehouse_classification"], as_index=True)
        .agg(
            orders=("orders", "sum"),
            views=("views", "sum"),
            sales=("sales", "sum"),
        )
    )

    orders = grouped["orders"].unstack("warehouse_classification")
    views = grouped["views"].unstack("warehouse_classification")
    sales = grouped["sales"].unstack("warehouse_classification")

    for group in [WAREHOUSE_GROUP_A, WAREHOUSE_GROUP_B]:
        if group not in orders.columns:
            orders[group] = np.nan
        if group not in views.columns:
            views[group] = np.nan
        if group not in sales.columns:
            sales[group] = 0.0

    valid_mask = (views[WAREHOUSE_GROUP_A] > 0) & (views[WAREHOUSE_GROUP_B] > 0)

    orders = orders[valid_mask]
    views = views[valid_mask]
    sales = sales.loc[orders.index]

    conversion_rate_a = orders[WAREHOUSE_GROUP_A] / views[WAREHOUSE_GROUP_A]
    conversion_rate_b = orders[WAREHOUSE_GROUP_B] / views[WAREHOUSE_GROUP_B]

    conversion_rate_delta = conversion_rate_a - conversion_rate_b

    total_sales = sales[WAREHOUSE_GROUP_A].fillna(0) + sales[WAREHOUSE_GROUP_B].fillna(0)
    total_orders = orders[WAREHOUSE_GROUP_A].fillna(0) + orders[WAREHOUSE_GROUP_B].fillna(0)

    result = pd.DataFrame(
        {
            "product_id": orders.index.astype(str),
            "conversion_rate_delta": conversion_rate_delta.values.astype(float),
            "total_sales": total_sales.values.astype(float),
            "total_orders": total_orders.values.astype(float),
            "conversion_rate_group_a": conversion_rate_a.values.astype(float),
            "conversion_rate_group_b": conversion_rate_b.values.astype(float),
        }
    )

    return result.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["conversion_rate_delta", "total_sales"]
    )


def filter_product_metrics(
    metrics: pd.DataFrame,
    sales_range: Optional[tuple[float, float]] = None,
    orders_range: Optional[tuple[float, float]] = None,
) -> pd.DataFrame:
    """Filter product metrics by total sales and total orders ranges."""
    filtered = metrics.copy()

    if sales_range is not None:
        sales_min, sales_max = sales_range
        filtered = filtered[
            (filtered["total_sales"] >= sales_min)
            & (filtered["total_sales"] <= sales_max)
        ]

    if orders_range is not None:
        orders_min, orders_max = orders_range
        filtered = filtered[
            (filtered["total_orders"] >= orders_min)
            & (filtered["total_orders"] <= orders_max)
        ]

    return filtered


# ---------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------

def plot_sales_vs_conversion_delta(
    metrics: pd.DataFrame,
    mode: str = "density",
    log_y: bool = False,
) -> None:
    """
    Plot total sales vs conversion rate delta.

    Parameters:
    - mode='density': point density using gaussian KDE
    - mode='hexbin': hexbin aggregation
    - mode='scatter': simple alpha scatter
    """
    if metrics.empty:
        print("No data available after applying filters.")
        return

    x = metrics["conversion_rate_delta"].to_numpy()
    y = metrics["total_sales"].to_numpy()

    max_abs_x = np.nanmax(np.abs(x))
    if not np.isfinite(max_abs_x) or max_abs_x == 0:
        max_abs_x = 0.05

    xlim = (-max_abs_x * 1.15, max_abs_x * 1.15)

    fig, ax = plt.subplots(figsize=(11, 6))

    if mode == "density":
        y_for_kde = np.log10(np.where(y > 0, y, np.nan)) if log_y else y
        valid = np.isfinite(x) & np.isfinite(y_for_kde)

        if valid.sum() > 1 and valid.sum() <= 8000:
            xy = np.vstack([x[valid], y_for_kde[valid]])
            density = gaussian_kde(xy)(xy)
            order = np.argsort(density)

            scatter = ax.scatter(
                x[valid][order],
                y[valid][order],
                c=density[order],
                s=22,
            )
            colorbar = plt.colorbar(scatter, ax=ax)
            colorbar.set_label("Point density")
        else:
            ax.scatter(x, y, s=18, alpha=0.15)

    elif mode == "hexbin":
        hexbin = ax.hexbin(x, y, gridsize=40, mincnt=1)
        colorbar = plt.colorbar(hexbin, ax=ax)
        colorbar.set_label("Count")

    else:
        ax.scatter(x, y, s=18, alpha=0.15)

    ax.set_xlim(*xlim)

    if np.nanmax(y) > 0:
        ax.set_ylim(0, np.nanmax(y) * 1.08)

    ax.xaxis.set_major_formatter(PercentFormatter(1.0))

    ax.axvline(0, linewidth=1)
    ax.axhline(0, linewidth=1)

    ax.set_xlabel("Conversion rate delta")
    ax.set_ylabel("Total sales")
    ax.set_title("Total Sales vs Conversion Rate Delta by Product")

    if log_y:
        ax.set_yscale("log")

    ax.grid(False)
    plt.tight_layout()

    print(f"Products plotted: {len(metrics):,}")
    print(
        "Delta min/max: "
        f"{np.nanmin(metrics['conversion_rate_delta']):.4f} / "
        f"{np.nanmax(metrics['conversion_rate_delta']):.4f}"
    )

    plt.show()


# ---------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------

def run_analysis(
    country_groups: Optional[Iterable[str]] = None,
    customer_types: Optional[Iterable[str]] = None,
    product_families: Optional[Iterable[str]] = None,
    product_groups: Optional[Iterable[str]] = None,
    product_spectrums: Optional[Iterable[str]] = None,
    min_months_group_a: int = 0,
    min_months_group_b: int = 0,
    sales_range: Optional[tuple[float, float]] = None,
    orders_range: Optional[tuple[float, float]] = None,
    generate_plot: bool = True,
) -> pd.DataFrame:
    """Run the full warehouse dispersion analysis."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_dataset(INPUT_FILE)
    df = clean_dataset(df)

    filtered = filter_dataset(
        df,
        country_groups=country_groups,
        customer_types=customer_types,
        product_families=product_families,
        product_groups=product_groups,
        product_spectrums=product_spectrums,
        min_months_group_a=min_months_group_a,
        min_months_group_b=min_months_group_b,
    )

    metrics = compute_product_metrics(filtered)
    metrics = filter_product_metrics(
        metrics,
        sales_range=sales_range,
        orders_range=orders_range,
    )

    metrics.to_excel(OUTPUT_FILE, index=False)
    print(f"Product metrics saved to: {OUTPUT_FILE}")

    if generate_plot:
        plot_sales_vs_conversion_delta(metrics, mode="density", log_y=False)

    return metrics


if __name__ == "__main__":
    run_analysis(generate_plot=True)
