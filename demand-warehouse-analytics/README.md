# Demand & Warehouse Analytics

## Overview

This project focuses on demand and warehouse performance analysis using product views, sales orders, warehouse classification data and product metadata.

The goal is to understand how demand, conversion and sales performance vary depending on fulfilment or warehouse classification, customer type, country group and product attributes.

All scripts have been anonymized and adapted for portfolio purposes. Company-specific paths, internal labels and sensitive dataset references have been removed.

## Business Context

In ecommerce and supply chain environments, product availability and fulfilment structure can affect conversion and sales performance.

This project helps analyse whether different warehouse or fulfilment classifications show different behaviour in terms of:

- Product views
- Orders
- Sales
- Conversion rate
- Product families
- Country groups
- Customer types

## Project Files

### `warehouse_demand_conversion_analysis.py`

Builds a monthly conversion table by combining product views, sales orders, warehouse classification history and product metadata.

Main features:

- Product view and order data integration
- Warehouse classification assignment using nearest-date matching
- Conflict resolution for warehouse classification changes
- Monthly conversion rate calculation
- Enrichment with product family and validity flags
- Exportable monthly conversion table

---

### `warehouse_performance_dispersion_analysis.py`

Analyses performance dispersion between two fulfilment or warehouse groups.

Main features:

- Product-level aggregation
- Conversion rate comparison between fulfilment groups
- Total sales and order volume analysis
- Conversion rate delta calculation
- Filtering by country, customer type and product attributes
- Scatter, density and hexbin visualizations

## Technologies Used

- Python
- pandas
- numpy
- scipy
- matplotlib
- Excel / CSV input-output

## Example Input Structure

The scripts expect anonymized input files in a local `data/` folder, for example:

```txt
data/
├─ product_views.csv
├─ sales_orders.xlsx
├─ product_families.xlsx
├─ valid_products.xlsx
├─ warehouse_classification.csv
└─ warehouse_performance_table.xlsx
