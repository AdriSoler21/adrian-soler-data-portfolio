# Commercial Pricing Analytics

## Overview

This project contains a set of business analytics scripts focused on pricing, marketplace performance, conversion rate analysis and price elasticity.

The goal is to understand how product pricing and channel behaviour affect sales, conversion and commercial performance across web and marketplace environments.

All scripts have been anonymized and adapted for portfolio purposes. Company-specific paths, credentials, internal dataset names and sensitive business references have been removed.

## Business Context

In ecommerce and marketplace environments, the same product can behave differently depending on the sales channel. Price differences, traffic quality, conversion rates and product visibility can all influence commercial performance.

This project analyses those relationships to support better decisions around:

- Channel pricing strategy
- Marketplace vs web performance
- Conversion rate behaviour
- Product-level price sensitivity
- Price optimization opportunities

## Project Files

### `marketplace_demand_conversion_analysis.py`

Analyses marketplace demand and conversion behaviour by combining web, marketplace and product metadata.

Main features:

- Web vs marketplace data integration
- Product-week level analysis
- Price imputation
- Demand elasticity indicators
- Stock and conversion behaviour analysis
- Final export for business review

---

### `cross_channel_price_conversion_analysis.py`

Compares pricing and conversion performance between web and marketplace channels.

Main features:

- Average price calculation by channel
- Conversion rate calculation
- Price difference analysis
- Conversion rate difference analysis
- Outlier filtering using percentile thresholds
- Product-level and weekly summaries
- Correlation and scatter visualizations

---

### `price_elasticity_optimization.py`

Builds a price elasticity and optimization model based on product traffic, sales, conversion rate and purchase cost.

Main features:

- Product performance segmentation
- Price normalization
- Sales and conversion elasticity indicators
- Margin-based price pre-optimization
- Linear and polynomial price optimization
- Recommended price calculation
- Model evaluation using MAE

## Technologies Used

- Python
- pandas
- numpy
- scipy
- scikit-learn
- matplotlib
- Excel-based input/output

## Example Input Structure

The scripts expect anonymized input files in a local `data/` folder, for example:

```txt
data/
├─ web_sales.xlsx
├─ marketplace_sales.xlsx
├─ web_sessions.xlsx
├─ product_family_mapping.xlsx
└─ product_pricing_periods.xlsx
