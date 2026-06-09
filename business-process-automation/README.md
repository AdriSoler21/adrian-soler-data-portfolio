# Business Process Automation

## Overview

This project contains a Google Apps Script automation designed to support customer tier analysis directly inside Google Sheets.

The goal is to automate a manual commercial process by analysing customer revenue, order frequency and current tier status over a 12-month period.

The script has been anonymized and adapted for portfolio purposes. Company-specific names, internal labels and sensitive business references have been removed.

## Business Context

Commercial and CRM teams often need to review customer tiers, identify top customers and detect accounts that qualify for upgrades based on purchasing behaviour.

Doing this manually in spreadsheets can be repetitive, error-prone and time-consuming.

This project automates that workflow by reading order data, applying business rules and generating structured outputs for decision-making.

## Project File

### `customer_tier_automation.gs`

Google Apps Script automation for customer tier analysis in Google Sheets.

Main features:

- Reads order data from a Google Sheet
- Uses a configurable cutoff date
- Analyses the previous 12 months of customer activity
- Calculates customer revenue and number of unique orders
- Applies tier upgrade rules
- Prevents automatic downgrades
- Handles excluded customers
- Handles special tier customers
- Generates a results sheet
- Generates a top customers sheet
- Generates a movement summary sheet
- Adds a custom Google Sheets menu
- Includes instruction and legend modals

## Technologies Used

- Google Apps Script
- JavaScript
- Google Sheets
- Spreadsheet automation
- Business rule automation

## Example Google Sheets Structure

The script expects a Google Sheet with these tabs:

```txt
Orders
Config
Excluded Customers
Special Tiers
