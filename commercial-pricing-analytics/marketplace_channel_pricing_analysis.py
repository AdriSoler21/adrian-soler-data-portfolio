"""
Marketplace vs Web Channel Pricing Analysis
-------------------------------------------
Portfolio-safe version.

Purpose:
    Compare product performance between a web channel and a marketplace channel,
    focusing on price differences, conversion rate and revenue behaviour.

Expected input files in data/:
    web_sessions.csv       -> product_id, week, sessions
    web_sales.csv          -> product_id, week, units, revenue
    marketplace_sales.csv  -> product_id, week, sessions, units, revenue
"""

from pathlib import Path
import numpy as np
import pandas as pd


def load_channel_data(data_dir: str | Path = "data") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data_dir = Path(data_dir)
    web_sessions = pd.read_csv(data_dir / "web_sessions.csv")
    web_sales = pd.read_csv(data_dir / "web_sales.csv")
    marketplace = pd.read_csv(data_dir / "marketplace_sales.csv")
    return web_sessions, web_sales, marketplace


def prepare_channel_dataset(web_sessions: pd.DataFrame, web_sales: pd.DataFrame, marketplace: pd.DataFrame) -> pd.DataFrame:
    """Merge web and marketplace datasets and calculate core KPIs."""
    for df in [web_sessions, web_sales, marketplace]:
        df["product_id"] = df["product_id"].astype(str)
        df["week"] = df["week"].astype(int)

    web = web_sessions.merge(web_sales, on=["product_id", "week"], how="left")
    web = web.rename(columns={"sessions": "sessions_web", "units": "units_web", "revenue": "revenue_web"})

    marketplace = marketplace.rename(columns={
        "sessions": "sessions_marketplace",
        "units": "units_marketplace",
        "revenue": "revenue_marketplace",
    })

    df = web.merge(marketplace, on=["product_id", "week"], how="inner")
    numeric_cols = [c for c in df.columns if c not in {"product_id"}]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=[
        "sessions_web", "units_web", "revenue_web",
        "sessions_marketplace", "units_marketplace", "revenue_marketplace",
    ])
    df = df[(df["sessions_web"] > 0) & (df["sessions_marketplace"] > 0)]
    df = df[(df["units_web"] > 0) & (df["units_marketplace"] > 0)]

    df["price_web"] = df["revenue_web"] / df["units_web"]
    df["price_marketplace"] = df["revenue_marketplace"] / df["units_marketplace"]
    df["cr_web"] = df["units_web"] / df["sessions_web"]
    df["cr_marketplace"] = df["units_marketplace"] / df["sessions_marketplace"]

    df["price_diff"] = df["price_marketplace"] - df["price_web"]
    df["price_diff_pct"] = (df["price_marketplace"] / df["price_web"]) - 1
    df["cr_diff"] = df["cr_marketplace"] - df["cr_web"]
    df["cr_ratio"] = df["cr_marketplace"] / df["cr_web"].replace(0, np.nan)

    return remove_outliers(df, ["price_diff_pct", "cr_diff", "cr_ratio"])


def remove_outliers(df: pd.DataFrame, columns: list[str], lower_q: float = 0.01, upper_q: float = 0.99) -> pd.DataFrame:
    result = df.copy()
    for col in columns:
        low, high = result[col].quantile([lower_q, upper_q])
        result = result[(result[col] >= low) & (result[col] <= high)]
    return result


def summarize_channel_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Create an executive summary of channel performance."""
    metrics = {
        "avg_web_price": df["price_web"].mean(),
        "avg_marketplace_price": df["price_marketplace"].mean(),
        "avg_price_diff_pct": df["price_diff_pct"].mean(),
        "avg_web_cr": df["cr_web"].mean(),
        "avg_marketplace_cr": df["cr_marketplace"].mean(),
        "avg_cr_ratio": df["cr_ratio"].mean(),
        "products_weeks_analyzed": len(df),
    }
    return pd.DataFrame([metrics])


if __name__ == "__main__":
    web_sessions_df, web_sales_df, marketplace_df = load_channel_data("data")
    analysis_df = prepare_channel_dataset(web_sessions_df, web_sales_df, marketplace_df)
    summary = summarize_channel_performance(analysis_df)
    print(summary.T)
