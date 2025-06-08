import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import cloudscraper
import time

# Set up basic configuration
st.set_page_config(layout="wide")

# Create CloudScraper instance
scraper = cloudscraper.create_scraper()

# NSE API endpoint for historical data
historical_url = "https://www.nseindia.com/api/historical/foCPV"

# Load ticker symbols from CSV
try:
    ticker_df = pd.read_csv("tickers.csv")
    if "SYMBOL" not in ticker_df.columns:
        st.error("The 'tickers.csv' file must contain a 'SYMBOL' column.")
        st.stop()
    STOCK_SYMBOLS = ticker_df["SYMBOL"].dropna().unique().tolist()
except FileNotFoundError:
    st.error("tickers.csv file not found. Please ensure it exists in the same directory.")
    st.stop()
except Exception as e:
    st.error(f"Error loading tickers.csv: {str(e)}")
    st.stop()

# Predefined instrument types
PREDEFINED_INSTRUMENTS_TYPE = ["OPTSTK", "OPTIDX", "FUTIDX", "FUTSTK", "FUTIVX"]

def fetch_strike_prices(symbol, expiry_date, instrument_type):
    """Fetch available strike prices from historical data for the given symbol, expiry date, and instrument type."""
    # Calculate date range: 3 months before expiry to expiry
    from_date = expiry_date - timedelta(days=90)
    to_date = expiry_date
    from_date_str = from_date.strftime("%d-%m-%Y")
    to_date_str = to_date.strftime("%d-%m-%Y")
    expiry_date_str = expiry_date.strftime("%d-%b-%Y")
    year = to_date.year
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest"
    }

    strike_prices = set()
    option_types = ["CE", "PE"]  # Fetch for both CE and PE to get all strike prices
    
    try:
        # Visit homepage to set cookies
        scraper.get("https://www.nseindia.com/", headers=headers)
        time.sleep(1)
        # Visit derivatives page
        scraper.get("https://www.nseindia.com/market-data/equity-derivatives-watch", headers=headers)
        time.sleep(1)

        for option_type in option_types:
            params = {
                "from": from_date_str,
                "to": to_date_str,
                "instrumentType": instrument_type,
                "symbol": symbol,
                "year": str(year),
                "expiryDate": expiry_date_str,
                "optionType": option_type
            }
            
            response = scraper.get(historical_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "data" in data and data["data"]:
                df = pd.DataFrame(data["data"])
                if "FH_STRIKE_PRICE" in df.columns:
                    df["FH_STRIKE_PRICE"] = pd.to_numeric(df["FH_STRIKE_PRICE"], errors='coerce')
                    strike_prices.update(df["FH_STRIKE_PRICE"].dropna().tolist())
            
            time.sleep(1)  # Avoid rate limiting
        
        strike_prices = sorted(list(strike_prices))  # Sort and convert to list
        return strike_prices if strike_prices else [0]  # Fallback to [0] if none found
    except Exception as e:
        st.error(f"Error fetching historical strike prices: {str(e)}")
        return [0]

def fetch_nse_data(from_date, to_date, symbol, expiry_date, option_type, strike_price, instrument_type):
    """Fetch historical options data from NSE."""
    from_date_str = from_date.strftime("%d-%m-%Y")
    to_date_str = to_date.strftime("%d-%m-%Y")
    expiry_date_str = expiry_date.strftime("%d-%b-%Y")
    year = to_date.year
    
    params = {
        "from": from_date_str,
        "to": to_date_str,
        "instrumentType": instrument_type,
        "symbol": symbol,
        "year": str(year),
        "expiryDate": expiry_date_str,
        "optionType": option_type,
        "strikePrice": str(strike_price)
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        # Visit homepage
        scraper.get("https://www.nseindia.com/", headers=headers)
        time.sleep(1)
        # Visit derivatives page
        scraper.get("https://www.nseindia.com/market-data/equity-derivatives-watch", headers=headers)
        time.sleep(1)

        response = scraper.get(historical_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "data" in data and data["data"]:
            df = pd.DataFrame(data["data"])
            df = df.rename(columns={
                "FH_TIMESTAMP": "Date",
                "FH_OPENING_PRICE": "Open",
                "FH_TRADE_HIGH_PRICE": "High",
                "FH_TRADE_LOW_PRICE": "Low",
                "FH_CLOSING_PRICE": "Close",
                "FH_LAST_TRADED_PRICE": "LTP",
                "FH_STRIKE_PRICE": "Strike Price",
                "FH_EXPIRY_DT": "Expiry",
                "FH_OPTION_TYPE": "Option Type",
                "FH_UNDERLYING_VALUE": "Underlying"
            })
            
            numeric_columns = ['Open', 'High', 'Low', 'Close', 'LTP', 'Strike Price']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df.replace('-', pd.NA, inplace=True)
            df.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True)
            return df
        else:
            st.error("No historical data found for the selected criteria.")
            return None
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None

def create_candlestick_chart(df, expiry, strike, symbol):
    """Create a candlestick chart using Plotly."""
    try:
        if df.empty:
            st.warning("No data available for the selected criteria.")
            return None
        
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], format='%d-%b-%Y', errors='coerce')
            df.sort_values(by='Date', inplace=True)
        
        fig = go.Figure()
        if all(col in df.columns for col in ['Open', 'High', 'Low', 'Close']):
            fig.add_trace(go.Candlestick(
                x=df['Date'],
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='Candlestick Chart',
                increasing=dict(line=dict(color='#26a69a')),
                decreasing=dict(line=dict(color='#ef5350'))
            ))
        
        fig.update_layout(
            title=f'{symbol} - Option Chart<br>Strike Price: {strike}<br>Expiry: {expiry}',
            xaxis_title='Date',
            yaxis_title='Price',
            plot_bgcolor='#1e1e1e',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            xaxis=dict(gridcolor='#333', rangeslider_visible=False, showspikes=True),
            yaxis=dict(gridcolor='#333'),
            dragmode='pan',
            autosize=True,
            height=600
        )
        return fig
    except Exception as e:
        st.error(f"Error creating chart: {str(e)}")
        return None

def main():
    st.title("NSE Option Chart Generator")
    
    # Create 2 columns for filters
    col1, col2 = st.columns(2)
    
    # Column 1: Symbol and Instrument Type
    with col1:
        symbol = st.selectbox("Stock Symbol *", options=STOCK_SYMBOLS, index=1)
        instrument_type = st.selectbox("Instrument Type *", options=PREDEFINED_INSTRUMENTS_TYPE, index=0)
    
    # Column 2: Expiry Date and Option Type
    with col2:
        expiry_date = st.date_input("Expiry Date (DD-MMM-YYYY) *", value=datetime(2025, 12, 31), format="DD-MM-YYYY", min_value=datetime(2000, 1, 1))
        option_type = st.selectbox("Option Type *", options=["CE", "PE"], index=0)
    
    # Fetch historical strike prices
    strike_prices = fetch_strike_prices(symbol, expiry_date, instrument_type)
    strike_price = st.selectbox("Strike Price *", options=strike_prices, index=0)
    
    # Validation
    all_fields_filled = (
        symbol is not None and
        instrument_type is not None and
        expiry_date is not None and
        option_type is not None and
        strike_price > 0
    )

    if not all_fields_filled:
        st.warning("Please fill all required fields marked with *.")
    
    # Disable button if required fields are not filled
    fetch_button = st.button("Fetch Data", disabled=not all_fields_filled)

    # Use session state to store fetched data
    if 'df' not in st.session_state:
        st.session_state.df = None

    if fetch_button and all_fields_filled:
        # Calculate date range: 3 months before expiry to expiry
        from_date = expiry_date - timedelta(days=90)
        to_date = expiry_date
        st.session_state.df = fetch_nse_data(from_date, to_date, symbol, expiry_date, option_type, strike_price, instrument_type)

    if st.session_state.df is not None and not st.session_state.df.empty:
        fig = create_candlestick_chart(st.session_state.df, expiry_date, strike_price, symbol)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
    elif st.session_state.df is not None:
        st.warning("No data available to display.")

if __name__ == "__main__":
    main()