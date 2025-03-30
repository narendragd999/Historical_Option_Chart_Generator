import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import cloudscraper
import time

# Set up basic configuration
st.set_page_config(layout="wide")

# Create CloudScraper instance
scraper = cloudscraper.create_scraper()

# NSE API endpoint
url = "https://www.nseindia.com/api/historical/foCPV"

# Load ticker symbols from CSV
try:
    ticker_df = pd.read_csv("tickerS.csv")
    if "SYMBOL" not in ticker_df.columns:
        st.error("The 'tickerS.csv' file must contain a 'SYMBOL' column.")
        st.stop()
    STOCK_SYMBOLS = ticker_df["SYMBOL"].dropna().unique().tolist()
except FileNotFoundError:
    st.error("tickerS.csv file not found. Please ensure it exists in the same directory.")
    st.stop()
except Exception as e:
    st.error(f"Error loading tickerS.csv: {str(e)}")
    st.stop()

# Predefined expiry dates
PREDEFINED_EXPIRY_DATES = [
    "30-Jan-2025", "27-Feb-2025", "27-Mar-2025", "24-Apr-2025",
    "29-May-2025", "26-Jun-2025", "31-Jul-2025", "28-Aug-2025",
    "25-Sep-2025", "30-Oct-2025", "27-Nov-2025", "31-Dec-2025"
]

# Fixed typo in PREDEFINED_INSTRUMENTS_TYPE
PREDEFINED_INSTRUMENTS_TYPE = ["OPTSTK", "OPTIDX", "FUTIDX", "FUTSTK", "FUTIVX"]

def fetch_nse_data(from_date, to_date, symbol, year, expiry_date, option_type, strike_price, instrument_type):
    from_date_str = from_date.strftime("%d-%m-%Y")
    to_date_str = to_date.strftime("%d-%m-%Y")
    
    params = {
        "from": from_date_str,
        "to": to_date_str,
        "instrumentType": instrument_type,
        "symbol": symbol,
        "year": str(year),  # Ensure year is a string
        "expiryDate": expiry_date,
        "optionType": option_type,
        "strikePrice": str(strike_price)  # Convert strike price to string as per API
    }   
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest"
    }

    st.write("Visiting homepage...")
    response = scraper.get("https://www.nseindia.com/", headers=headers)
    if response.status_code != 200:
        st.error(f"Failed to load homepage: {response.status_code}")
        return None

    st.write("Visiting derivatives page...")
    scraper.get("https://www.nseindia.com/market-data/equity-derivatives-watch", headers=headers)
    time.sleep(2)

    try:
        response = scraper.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "data" in data and data["data"]:
            df = pd.DataFrame(data["data"])
            
            # Rename columns based on actual API response (verified with URL)
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
            st.error("No data found in the response.")
            return None
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None

def create_candlestick_chart(df, expiry, strike, symbol):
    try:
        # Avoid redundant filtering since API already filters by expiry and strike
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
    
    # Input fields
    col1, col2, col3 = st.columns(3)
    with col1:    	
        symbol = st.selectbox("Stock Symbol", options=STOCK_SYMBOLS, index=STOCK_SYMBOLS.index("ADANIENSOL") if "ADANIENSOL" in STOCK_SYMBOLS else 0)
        instrument_type = st.selectbox("Select Instrument Type", options=PREDEFINED_INSTRUMENTS_TYPE, index=0)  # Default to OPTSTK
        strike_price = st.number_input("Strike Price", value=840)  # Fixed typo and added default
    with col2:
        year = st.number_input("Year", min_value=2020, max_value=2030, value=2025)
        from_date = st.date_input("From Date", value=datetime(2024, 12, 30), format="DD-MM-YYYY")  # Adjusted to match URL
        option_type = st.selectbox("Option Type", options=["CE", "PE"], index=0)
    with col3:
        expiry_date = st.selectbox("Expiry Date (DD-MMM-YYYY)", options=PREDEFINED_EXPIRY_DATES, index=2)  # Default to 27-Mar-2025        
        to_date = st.date_input("To Date", value=datetime(2025, 3, 30), format="DD-MM-YYYY")  # Adjusted to match URL
    
    # Use session state to store fetched data
    if 'df' not in st.session_state:
        st.session_state.df = None

    if st.button("Fetch Data"):
        st.session_state.df = fetch_nse_data(from_date, to_date, symbol, year, expiry_date, option_type, strike_price, instrument_type)

    if st.session_state.df is not None and not st.session_state.df.empty:
        fig = create_candlestick_chart(st.session_state.df, expiry_date, strike_price, symbol)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
    elif st.session_state.df is not None:
        st.warning("No data available to display.")

if __name__ == "__main__":
    main()