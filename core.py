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

# NSE API endpoint
url = "https://www.nseindia.com/api/historical/foCPV"

# Load ticker symbols from CSV
try:
    ticker_df = pd.read_csv("tickers.csv")
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

PREDEFINED_INSTRUMENTS_TYPE = ["OPTSTK", "OPTIDX", "FUTIDX", "FUTSTK", "FUTIVX"]

# Predefined durations (optional)
PREDEFINED_DURATIONS = ["Custom", "1D", "1W", "1M", "1.5M", "3M"]  # Custom as default

def calculate_from_date(to_date, duration):
    """Calculate from_date based on the selected duration and to_date."""
    if duration == "1D":
        return to_date - timedelta(days=1)
    elif duration == "1W":
        return to_date - timedelta(weeks=1)
    elif duration == "1M":
        return to_date - timedelta(days=30)  # Approximate 1 month
    elif duration == "1.5M":
        return to_date - timedelta(days=45)  # Approximate 1.5 month
    elif duration == "3M":
        return to_date - timedelta(days=90)  # Approximate 3 months
    else:  # Custom
        return None  # Let user set manually

def fetch_nse_data(from_date, to_date, symbol, year, expiry_date, option_type, strike_price, instrument_type):
    from_date_str = from_date.strftime("%d-%m-%Y")
    to_date_str = to_date.strftime("%d-%m-%Y")
    expiry_date_str = expiry_date.strftime("%d-%b-%Y")
    #print(f"expiry_date---{expiry_date_str}")
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
    
    # Create 3 columns to distribute filters horizontally
    col1, col2, col3 = st.columns(3)
    
    # Column 1: First 3 filters
    with col1:
        symbol = st.selectbox("Stock Symbol *", options=STOCK_SYMBOLS, index=1)
        instrument_type = st.selectbox("Instrument Type *", options=PREDEFINED_INSTRUMENTS_TYPE, index=0)
        year = st.number_input("Year *", min_value=1995, max_value=2050, value=2025)
    
    # Column 2: Next 3 filters
    with col2:        
        duration = st.selectbox("For Past", options=PREDEFINED_DURATIONS, index=0)  # Default to Custom
        # From Date comes first to set the min_value for To Date
        calculated_from_date = calculate_from_date(datetime(2025, 3, 30), duration) if duration != "Custom" else None
        if duration != "Custom" and calculated_from_date is not None:
            from_date = st.date_input("From Date *", value=calculated_from_date, format="DD-MM-YYYY", disabled=True, min_value=datetime(2000, 1, 1))
        else:
            from_date = st.date_input("From Date *", value=datetime(2024, 12, 30), format="DD-MM-YYYY", min_value=datetime(2000, 1, 1))
        # To Date must be after From Date
        to_date = st.date_input("To Date *", value=datetime(2025, 3, 30), min_value=from_date + timedelta(days=1), format="DD-MM-YYYY")
    
    # Column 3: Last 3 filters
    with col3:        
        expiry_date = st.date_input("Expiry Date (DD-MMM-YYYY) *", value=datetime(2024, 12, 30), format="DD-MM-YYYY", min_value=datetime(2000, 1, 1))
        option_type = st.selectbox("Option Type *", options=["CE", "PE"], index=0)
        strike_price = st.number_input("Strike Price *", min_value=0)
    
    # Validation: Check if all required fields are filled and valid
    all_fields_filled = (
        instrument_type is not None and
        symbol is not None and
        year is not None and
        expiry_date is not None and
        to_date is not None and
        from_date is not None and
        from_date < to_date and  # Ensure To Date is strictly after From Date
        option_type is not None and
        strike_price > 0
    )

    if not all_fields_filled:
        if from_date >= to_date:
            st.error("To Date must be after From Date.")
        else:
            st.warning("Please fill all required fields marked with *.")
    
    # Disable button if required fields are not filled or dates are invalid
    fetch_button = st.button("Fetch Data", disabled=not all_fields_filled)

    # Use session state to store fetched data
    if 'df' not in st.session_state:
        st.session_state.df = None

    if fetch_button and all_fields_filled:
        st.session_state.df = fetch_nse_data(from_date, to_date, symbol, year, expiry_date, option_type, strike_price, instrument_type)

    if st.session_state.df is not None and not st.session_state.df.empty:
        fig = create_candlestick_chart(st.session_state.df, expiry_date, strike_price, symbol)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
    elif st.session_state.df is not None:
        st.warning("No data available to display.")

if __name__ == "__main__":
    main()