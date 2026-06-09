# Customer Revenue Risk Prediction

## Overview

This project focuses on predicting customers at risk of revenue decline using historical purchasing behaviour and customer-level features.

The goal is to identify customers who may require commercial attention based on their recent activity, order frequency, sales evolution and behavioural indicators.

The script has been anonymized and adapted for portfolio purposes. Company-specific paths, internal dataset names and sensitive business references have been removed.

## Business Context

In B2B and ecommerce environments, customer revenue can decrease before a customer fully stops purchasing. Detecting this risk early allows commercial teams to prioritize accounts, design retention actions and protect recurring revenue.

This project uses historical order data to build a customer-level dataset and train a machine learning model that predicts revenue risk.

## Project File

### `customer_revenue_risk_prediction.py`

Machine Learning pipeline designed to identify customers with a high probability of revenue decline.

Main features:

- Customer-level data aggregation
- Recency, frequency and monetary value features
- Sales evolution over 3, 6 and 12 month windows
- Feature engineering for customer behaviour
- Categorical encoding
- Random Forest classification model
- Custom probability threshold
- Confusion matrix and classification report
- Feature importance analysis
- Export of customers at risk for business review

## Technologies Used

- Python
- pandas
- numpy
- scikit-learn
- matplotlib
- joblib
- Excel-based input/output

## Example Input Structure

The script expects an anonymized input file in a local `data/` folder, for example:

```txt
data/
└─ customer_orders_dataset.xlsx
