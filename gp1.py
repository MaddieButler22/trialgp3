# %%
import streamlit as st
import requests
import json
import pandas as pd
import time
from datetime import datetime
from sec_api import QueryApi
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Constants
api_key = '24e131521ec416575de4f3b9221711bde8dab9ac6e00afc189cad610949d2754'
xbrl_converter_api_endpoint = 'https://api.sec-api.io/xbrl-to-json'

# Streamlit user input for ticker symbol
ticker = st.text_input("Enter Ticker Symbol", "AAPL")  # Default ticker is AAPL

# Streamlit layout - Container for displaying results
results_container = st.container()

xbrl_converter_api_endpoint = 'https://api.sec-api.io/xbrl-to-json'

# Function to get XBRL-JSON for a given accession number with retry logic
def get_xbrl_json(accession_no, retry=0):
    request_url = f"{xbrl_converter_api_endpoint}?accession-no={accession_no}&token={api_key}"
    try:
        response = requests.get(request_url)
        return json.loads(response.text)
    except:
        if retry > 5:
            raise Exception('API error')
        time.sleep(0.5)
        return get_xbrl_json(accession_no, retry + 1)

# Function to extract balance sheet data from XBRL-JSON
def get_balance_sheet(xbrl_json):
    balance_sheet_store = {}
    for usGaapItem in xbrl_json['BalanceSheets']:
        values, indices = [], []
        for fact in xbrl_json['BalanceSheets'][usGaapItem]: 
            if 'segment' not in fact:
                index = fact['period']['instant']
                if index not in indices:
                    value = fact['value'] if "value" in fact else 0
                    values.append(value)
                    indices.append(index)
        balance_sheet_store[usGaapItem] = pd.Series(values, index=indices)
    return pd.DataFrame(balance_sheet_store).T

# Function to clean the balance sheet DataFrame
def clean_balance_sheet(balance_sheet):
    balance_sheet = balance_sheet.dropna(axis=1, thresh=5)  # Drop columns with more than 5 NaNs
    balance_sheet.columns = pd.to_datetime(balance_sheet.columns).date  # Convert index to datetime
    return balance_sheet.sort_index(axis=1)  # Sort by date

# Function to convert XBRL-JSON of income statement to pandas dataframe
def get_income_statement(xbrl_json):
    income_statement_store = {}
    for usGaapItem in xbrl_json['StatementsOfIncome']:
        values, indices = [], []
        for fact in xbrl_json['StatementsOfIncome'][usGaapItem]:
            if 'segment' not in fact:
                index = fact['period']['startDate'] + '-' + fact['period']['endDate']
                if index not in indices:
                    values.append(fact['value'])
                    indices.append(index)
        income_statement_store[usGaapItem] = pd.Series(values, index=indices)
    return pd.DataFrame(income_statement_store).T


# Fetching all 10-Q and 10-K filings for a company and building comprehensive balance sheet
def fetch_and_process_financial_statements(ticker):
    query_api = QueryApi(api_key=api_key)
    query = {
        "query": {
            "query_string": {
                "query": f"(formType:\"10-Q\" OR formType:\"10-K\") AND ticker:{ticker}"
            }
        },
        "from": "0",
        "size": "20",
        "sort": [{"filedAt": {"order": "desc"}}]
    }

    query_result = query_api.get_filings(query)
    accession_numbers = [filing['accessionNo'] for filing in query_result['filings']]

    balance_sheet_final = pd.DataFrame()
    income_statement_final = pd.DataFrame()

    for accession_no in accession_numbers:
        xbrl_json_data = get_xbrl_json(accession_no)
        
        # Process Balance Sheet
        balance_sheet = get_balance_sheet(xbrl_json_data)
        balance_sheet_cleaned = clean_balance_sheet(balance_sheet)
        balance_sheet_final = balance_sheet_final.combine_first(balance_sheet_cleaned)
        
        # Process Income Statement
        income_statement = get_income_statement(xbrl_json_data)
        income_statement_final = income_statement_final.combine_first(income_statement)

    return balance_sheet_final, income_statement_final

# This part goes in the main body of your Streamlit app script
if st.button('Fetch Financial Statements'):
    with results_container:
        try:
            balance_sheet_final, income_statement_final = fetch_and_process_financial_statements(ticker)

            # Display Balance Sheet
            st.write(f"Balance Sheet for {ticker}:")
            if not balance_sheet_final.empty:
                st.dataframe(balance_sheet_final)
            else:
                st.write("No balance sheet data available.")

            # Display Income Statement
            st.write(f"Income Statement for {ticker}:")
            if not income_statement_final.empty:
                st.dataframe(income_statement_final)
            else:
                st.write("No income statement data available.")

        except Exception as e:
            st.error(f"An error occurred: {e}")



# Function definitions (like fetch_and_process_financial_statements, get_balance_sheet, etc.) go here

# Function to convert string values to numeric
def convert_to_numeric(value):
    try:
        return float(value)
    except ValueError:
        return value


# Assuming you've already defined the 'results_container' and 'ticker' input earlier in your Streamlit app
with results_container:
    if st.button('Fetch Financial Statements'):
        balance_sheet, income_statement = fetch_and_process_financial_statements(ticker)

        if balance_sheet.empty:
            st.write(f'No financial statements found for {ticker}')
        else:
            # Find the most recent date in the balance sheet and income statement
            balance_sheet_date = balance_sheet.columns[-1]
            income_statement_date = income_statement.columns[-1]

            # Display the Most Recent Balance Sheet
            st.write(f"Balance Sheet as of {balance_sheet_date}:")
            st.dataframe(balance_sheet[balance_sheet_date])

            # Display the Most Recent Income Statement
            st.write(f"Income Statement for the period ending on {income_statement_date}:")
            st.dataframe(income_statement[income_statement_date])

# Assuming this code is part of the main interactive block after fetching the financial statements

with results_container:
    if st.button('Fetch and Analyze Financial Statements'):
        balance_sheet, income_statement = fetch_and_process_financial_statements(ticker)

        if not balance_sheet.empty and not income_statement.empty:
            # Convert string values to numeric in the DataFrames
            balance_sheet = balance_sheet.apply(pd.to_numeric, errors='coerce', axis=1)
            income_statement = income_statement.apply(pd.to_numeric, errors='coerce', axis=1)

            latest_balance_date = balance_sheet.columns[-1]
            latest_income_date = income_statement.columns[-1]

            # Ratio Calculations
            # Liquidity Ratios
            current_ratio = balance_sheet.loc['AssetsCurrent', latest_balance_date] / balance_sheet.loc['LiabilitiesCurrent', latest_balance_date]
            quick_ratio = (balance_sheet.loc['AssetsCurrent', latest_balance_date] - balance_sheet.loc['InventoryNet', latest_balance_date]) / balance_sheet.loc['LiabilitiesCurrent', latest_balance_date]

            # Profitability Ratios
            net_income = income_statement.loc['NetIncomeLoss', latest_income_date]
            revenue = income_statement.loc['RevenueFromContractWithCustomerExcludingAssessedTax', latest_income_date]
            net_profit_margin = net_income / revenue
            return_on_equity = net_income / balance_sheet.loc['StockholdersEquity', latest_balance_date]

            # Solvency Ratio
            debt_to_equity_ratio = balance_sheet.loc['Liabilities', latest_balance_date] / balance_sheet.loc['StockholdersEquity', latest_balance_date]

            # Efficiency Ratio
            asset_turnover_ratio = revenue / balance_sheet.loc['Assets', latest_balance_date]

            # Displaying Ratios
            st.write("Financial Ratios as of latest dates:")
            st.write(f"Current Ratio: {current_ratio:.2f}")
            st.write(f"Quick Ratio: {quick_ratio:.2f}")
            st.write(f"Net Profit Margin: {net_profit_margin:.2%}")
            st.write(f"Return on Equity: {return_on_equity:.2%}")
            st.write(f"Debt to Equity Ratio: {debt_to_equity_ratio:.2f}")
            st.write(f"Asset Turnover Ratio: {asset_turnover_ratio:.2f}")

        else:
            st.write(f'No financial statements found for {ticker}')

# %%
