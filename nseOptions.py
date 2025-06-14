import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Global session for NSE requests
nse_session = None

# Headers for NSE requests
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/equity-derivatives-watch",
}

# Initialize NSE session
def initialize_nse_session():
    global nse_session
    if nse_session is None:
        nse_session = requests.Session()
        try:
            response = nse_session.get("https://www.nseindia.com/", headers=headers)
            if response.status_code != 200:
                st.error(f"Failed to load homepage: {response.status_code}")
                return False
            time.sleep(2)
            response = nse_session.get("https://www.nseindia.com/market-data/equity-derivatives-watch", headers=headers)
            time.sleep(5)
            if response.status_code != 200:
                st.error(f"Failed to load derivatives page: {response.status_code}")
                return False
        except Exception as e:
            st.error(f"Session initialization failed: {str(e)}")
            return False
    return True

# Fetch historical data
def fetch_historical_data(from_date, to_date, symbol, year, expiry_date, option_type, strike_price, instrument_type="OPTIDX"):
    if not initialize_nse_session():
        return None
    from_date_str = from_date.strftime("%d-%m-%Y")
    to_date_str = to_date.strftime("%d-%m-%Y")
    expiry_date_str = expiry_date.strftime("%d-%b-%Y").upper()
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
    try:
        with st.spinner("Fetching historical data..."):
            response = nse_session.get(
                "https://www.nseindia.com/api/historicalOR/foCPV",
                params=params,
                headers=headers,
                cookies=nse_session.cookies.get_dict()
            )
            time.sleep(1)
            if response.status_code == 200:
                data = response.json()
                df = pd.DataFrame(data.get('data', []))
                if df.empty:
                    st.error(f"No historical data returned for strike {strike_price}.")
                    return None
                return df
            else:
                st.error(f"Failed to fetch historical data: {response.status_code}")
                return None
    except Exception as e:
        st.error(f"Error fetching historical data: {str(e)}")
        return None

# Calculate P/L
def calculate_credit_spread_pnl(sell_df, buy_df, sell_strike, buy_strike, quantity):
    close_col = next((col for col in ['FH_CLOSE', 'CLOSE', 'LAST', 'LTP'] if col in sell_df.columns and col in buy_df.columns), None)
    if not close_col:
        return None, "Missing close price column for P/L calculation"
    
    initial_sell_premium = sell_df[close_col].iloc[0]
    initial_buy_premium = buy_df[close_col].iloc[0]
    initial_net_premium = initial_sell_premium - initial_buy_premium
    
    final_sell_premium = sell_df[close_col].iloc[-1]
    final_buy_premium = buy_df[close_col].iloc[-1]
    final_net_premium = final_sell_premium - final_buy_premium
    
    pnl = (initial_net_premium - final_net_premium) * quantity
    return pnl, f"Initial Net Premium: {initial_net_premium:.2f}, Final Net Premium: {final_net_premium:.2f}, P/L: {pnl:.2f}"

# Create candlestick charts
def create_candlestick_charts(sell_df, buy_df, sell_strike, buy_strike, quantity):
    close_col = next((col for col in ['FH_CLOSE', 'CLOSE', 'LAST', 'LTP'] if col in sell_df.columns and col in buy_df.columns), None)
    if not close_col:
        return None
    
    # Map alternative columns
    for df in [sell_df, buy_df]:
        for col in ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'LAST', 'LTP']:
            if col in df.columns and 'FH_' + col not in df.columns:
                df['FH_' + col] = df[col]
    
    # Check for candlestick columns
    required_cols = ['FH_OPEN', 'FH_HIGH', 'FH_LOW', 'FH_CLOSE', 'FH_TIMESTAMP']
    if not all(col in sell_df.columns for col in required_cols) or not all(col in buy_df.columns for col in required_cols):
        st.warning("Missing required columns for candlestick charts.")
        return None
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            f"Sell Call ({sell_strike} CE) Candlestick",
            f"Buy Call ({buy_strike} CE) Candlestick",
            "Credit Spread P/L",
            "Open Interest"
        ],
        row_heights=[0.5, 0.5],
        specs=[[{"type": "candlestick"}, {"type": "candlestick"}], [{"type": "xy"}, {"type": "xy"}]]
    )
    
    # Sell Call Candlestick
    fig.add_trace(
        go.Candlestick(
            x=sell_df['FH_TIMESTAMP'],
            open=sell_df['FH_OPEN'],
            high=sell_df['FH_HIGH'],
            low=sell_df['FH_LOW'],
            close=sell_df['FH_CLOSE'],
            name=f"Sell {sell_strike} CE"
        ),
        row=1, col=1
    )
    
    # Buy Call Candlestick
    fig.add_trace(
        go.Candlestick(
            x=buy_df['FH_TIMESTAMP'],
            open=buy_df['FH_OPEN'],
            high=buy_df['FH_HIGH'],
            low=buy_df['FH_LOW'],
            close=buy_df['FH_CLOSE'],
            name=f"Buy {buy_strike} CE"
        ),
        row=1, col=2
    )
    
    # P/L
    net_premium = sell_df[close_col] - buy_df[close_col]
    fig.add_trace(
        go.Scatter(
            x=sell_df['FH_TIMESTAMP'],
            y=net_premium * quantity,
            name="Net Premium (P/L)",
            line=dict(color='blue')
        ),
        row=2, col=1
    )
    
    # Open Interest
    if 'FH_OPEN_INT' in sell_df.columns and 'FH_OPEN_INT' in buy_df.columns:
        fig.add_trace(
            go.Scatter(
                x=sell_df['FH_TIMESTAMP'],
                y=sell_df['FH_OPEN_INT'],
                name=f"Sell {sell_strike} OI",
                line=dict(color='orange')
            ),
            row=2, col=2
        )
        fig.add_trace(
            go.Scatter(
                x=buy_df['FH_TIMESTAMP'],
                y=buy_df['FH_OPEN_INT'],
                name=f"Buy {buy_strike} OI",
                line=dict(color='green')
            ),
            row=2, col=2
        )
    
    fig.update_layout(
        height=800,
        width=1200,
        showlegend=True,
        title_text="Credit Call Spread Backtest"
    )
    return fig

# Main app
st.title("Nifty 50 Credit Call Spread Backtester")

# Full-page inputs
st.header("Backtest Parameters")
col1, col2, col3 = st.columns(3)
with col1:
    start_date = st.date_input("Start Date", value=datetime(2025, 4, 15), max_value=datetime(2025, 5, 15))
with col2:
    expiry_date = st.date_input("Expiry Date", value=datetime(2025, 5, 15), min_value=start_date)
with col3:
    quantity = st.number_input("Quantity (Lots)", min_value=1, value=50)

col4, col5 = st.columns(2)
with col4:
    sell_strike = st.number_input("Sell Call Strike", min_value=1000.0, max_value=30000.0, value=23000.0, step=50.0)
with col5:
    default_buy_strike = max(sell_strike + 100.0, 23100.0)
    buy_strike = st.number_input("Buy Call Strike", min_value=sell_strike, max_value=30000.0, value=default_buy_strike, step=50.0)

if st.button("Run Backtest"):
    with st.spinner("Running backtest..."):
        sell_df = fetch_historical_data(start_date, expiry_date, "NIFTY", 2025, expiry_date, "CE", sell_strike)
        buy_df = fetch_historical_data(start_date, expiry_date, "NIFTY", 2025, expiry_date, "CE", buy_strike)
        if sell_df is not None and buy_df is not None:
            # P/L Calculation
            pnl, message = calculate_credit_spread_pnl(sell_df, buy_df, sell_strike, buy_strike, quantity)
            if pnl is not None:
                st.subheader("Profit/Loss Analysis")
                st.write(message)
            else:
                st.error(message)
            
            # Charts
            fig = create_candlestick_charts(sell_df, buy_df, sell_strike, buy_strike, quantity)
            if fig:
                st.plotly_chart(fig)
            
            # Data Tables
            st.subheader("Sell Call Data")
            st.dataframe(sell_df)
            st.subheader("Buy Call Data")
            st.dataframe(buy_df)
            
            # Debug Columns
            st.write("Sell Data Columns:", sell_df.columns.tolist())
            st.write("Buy Data Columns:", buy_df.columns.tolist())
        else:
            st.error("Failed to fetch historical data.")

# Instructions
st.markdown("""
### How to Use
1. **Set Parameters**:
   - **Start Date**: Choose the start date for backtesting (e.g., 15-Apr-2025).
   - **Expiry Date**: Select the expiry date (e.g., 15-May-2025).
   - **Quantity**: Enter lots (default 50).
   - **Sell Call Strike**: Lower strike for the credit spread (e.g., 23000).
   - **Buy Call Strike**: Higher strike (e.g., 23100, auto-adjusted).
2. **Run Backtest**:
   - Click 'Run Backtest' to fetch data from NSE for the specified period.
3. **View Results**:
   - **P/L**: Shows initial/final net premium and profit/loss.
   - **Charts**: Side-by-side candlestick charts for both strikes, P/L, and Open Interest.
   - **Data Tables**: Full data for both options.
4. **Debugging**:
   - Check column names below tables if charts are missing.
   - Ensure strikes are multiples of 50/100.
   - Verify expiry date is a valid Nifty expiry.
""")