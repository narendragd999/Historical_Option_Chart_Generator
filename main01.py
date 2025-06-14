import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import cloudscraper
import time
import os
import urllib.parse

# Set up basic configuration
st.set_page_config(layout="wide")

# Create CloudScraper instance
scraper = cloudscraper.create_scraper()

# NSE API endpoints
historical_url = "https://www.nseindia.com/api/historicalOR/foCPV"  # Options data for charts
historical_or_url = "https://www.nseindia.com/api/historicalOR/foCPV"  # Strike prices

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

def fetch_strike_prices(symbol, expiry_date, instrument_type, date_range_days=30, to_date=None):
    """Fetch available strike prices from historicalOR/foCPV API, with CSV fallback."""
    from_date = to_date - timedelta(days=date_range_days)
    if to_date is None:
        to_date = expiry_date
    from_date_str = from_date.strftime("%d-%m-%Y")
    to_date_str = to_date.strftime("%d-%m-%Y")
    expiry_date_str = expiry_date.strftime("%d-%b-%Y").upper()
    year = to_date.year
    csv_date_str = expiry_date.strftime("%Y%b%d").upper()
    csv_file = f"fo_eq_security_{csv_date_str}.csv"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest"
    }

    strike_prices = set()
    option_types = ["CE", "PE"]
    
    # Try API first
    try:
        scraper.get("https://www.nseindia.com/", headers=headers)
        time.sleep(1)
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
            
            # Log the full API URL
            url = f"{historical_or_url}?{urllib.parse.urlencode(params)}"
            st.write(f"Fetching strike prices for {symbol} {option_type} with URL: {url}")
            
            for attempt in range(3):
                try:
                    response = scraper.get(historical_or_url, params=params, headers=headers, timeout=10)
                    #st.write(f"API attempt {attempt + 1} for {option_type} returned status code: {response.status_code}")
                    response.raise_for_status()
                    data = response.json()
                    
                    if "data" in data and data["data"]:
                        df = pd.DataFrame(data["data"])
                        #st.write(f"API returned {len(df)} records for {symbol} {option_type} with expiry {expiry_date_str} over {date_range_days} days")
                        if "FH_STRIKE_PRICE" in df.columns:
                            df["FH_STRIKE_PRICE"] = pd.to_numeric(df["FH_STRIKE_PRICE"], errors='coerce')
                            # Prioritize recent strikes by filtering for the latest trading day
                            if "FH_TIMESTAMP" in df.columns:
                                df["FH_TIMESTAMP"] = pd.to_datetime(df["FH_TIMESTAMP"], format='%d-%b-%Y', errors='coerce')
                                latest_date = df["FH_TIMESTAMP"].max()
                                recent_df = df[df["FH_TIMESTAMP"] == latest_date]
                                valid_strikes = recent_df["FH_STRIKE_PRICE"].dropna().tolist()
                            else:
                                valid_strikes = df["FH_STRIKE_PRICE"].dropna().tolist()
                            strike_prices.update(valid_strikes)
                            #st.write(f"Fetched {len(valid_strikes)} strike prices for {option_type} via API")
                            if len(df) >= 500:
                                st.warning(f"API returned {len(df)} records for {option_type}; may be capped. Try a shorter date range or CSV fallback.")
                        else:
                            st.warning(f"No FH_STRIKE_PRICE column in API response for {symbol} {option_type}")
                    else:
                        st.warning(f"No API data for {symbol} {option_type} with expiry {expiry_date_str}. Response: {data}")
                    
                    time.sleep(1)
                    break
                except Exception as e:
                    st.warning(f"API attempt {attempt + 1} failed for {option_type}: {str(e)}")
                    time.sleep(2)
                    if attempt == 2:
                        st.error(f"Failed to fetch strike prices for {option_type} via API after 3 attempts")
        
        if strike_prices:
            st.write(f"Total unique strike prices from API: {len(strike_prices)}")
            return sorted(list(strike_prices))
        
        st.warning("No strike prices from API. Falling back to CSV.")
    except Exception as e:
        st.error(f"API error: {str(e)}. Falling back to CSV.")
    
    # Fallback to CSV
    try:
        if not os.path.exists(csv_file):
            st.error(f"CSV file {csv_file} not found. Please download from https://www.nseindia.com/report-detail/fo_eq_security.")
            return [0]
        
        df = pd.read_csv(csv_file)
        df.columns = df.columns.str.strip().str.replace(' ', '_').str.upper()
        
        if instrument_type in ["OPTSTK", "OPTIDX"]:
            df_filtered = df[
                (df['SYMBOL'] == symbol) &
                (df['INSTRUMENT'] == instrument_type) &
                (df['EXPIRY_DT'] == expiry_date_str) &
                (df['OPTION_TYP'].isin(['CE', 'PE']))
            ]
        else:
            st.warning(f"Instrument type {instrument_type} not supported for CSV strike prices.")
            return [0]
        
        if df_filtered.empty:
            st.error(f"No CSV data for {symbol}, {instrument_type}, expiry {expiry_date_str}.")
            return [0]
        
        if 'STRIKE_PR' in df_filtered.columns:
            df_filtered['STRIKE_PR'] = pd.to_numeric(df_filtered['STRIKE_PR'], errors='coerce')
            strike_prices = sorted(df_filtered['STRIKE_PR'].dropna().unique().tolist())
            st.write(f"Fetched {len(strike_prices)} strike prices from CSV")
            
            return strike_prices if strike_prices else [0]
        else:
            st.error("STRIKE_PR column not found in CSV.")
            return [0]
            
    except Exception as e:
        st.error(f"CSV error: {str(e)}")
        return [0]

def fetch_nse_data(from_date, to_date, symbol, expiry_date, option_type, strike_price, instrument_type):
    """Fetch historical options data from NSE."""
    from_date_str = from_date.strftime("%d-%m-%Y")
    to_date_str = to_date.strftime("%d-%m-%Y")
    expiry_str = expiry_date.strftime("%d-%b-%Y").upper()
    year = to_date.year
    #print(f'strike_price====={strike_price}')
    params = {
        "from": from_date_str,
        "to": to_date_str,
        "instrumentType": instrument_type,
        "symbol": symbol,
        "year": str(year),
        "expiryDate": expiry_str,
        "optionType": option_type,
        "strikePrice": str(strike_price)
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest"
    }

    # Log the full API URL
    #urll = f"{historical_url}?{urllib.parse.urlencode(params)}"
    #st.write(f"Fetching strike prices for {symbol} {option_type} with URL: {urll}")

    try:
        scraper.get("https://www.nseindia.com/", headers=headers)
        time.sleep(1)
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
                "FH_UNDERLYING_VALUE": "Underlying",
                "FH_TOT_TRADED_QTY": "Volume",
                "FH_OPEN_INT": "Open Interest"
            })
            
            numeric_columns = ['Open', 'High', 'Low', 'Close', 'LTP', 'Strike Price', 'Underlying', 'Volume', 'Open Interest']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df.replace('-', pd.NA, inplace=True)
            df.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True)
            return df
        else:
            st.error("No historical options data found for the selected criteria.")
            return None
    except Exception as e:
        st.error(f"Error fetching options data: {str(e)}")
        return None

def create_candlestick_chart(df, expiry, strike, symbol, chart_type="Option"):
    """Create a candlestick chart using Plotly for options data."""
    try:
        if df.empty:
            st.warning(f"No {chart_type.lower()} data available for the selected criteria.")
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
                name=f'{chart_type} Candlestick',
                increasing=dict(line=dict(color='#26a69a')),
                decreasing=dict(line=dict(color='#ef5350'))
            ))
        
        title = f'{symbol} - {chart_type} Chart'
        if chart_type == "Option":
            title += f'<br>Strike Price: {strike}<br>Expiry: {expiry.strftime("%d-%b-%Y")}'
        
        fig.update_layout(
            title=title,
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
        st.error(f"Error creating {chart_type.lower()} chart: {str(e)}")
        return None

def display_data_table(df):
    """Display a searchable and sortable table of the options data."""
    if df is None or df.empty:
        st.warning("No data available to display in the table.")
        return
    
    st.subheader("Options Data Table")
    
    search_term = st.text_input("Search Table", placeholder="Enter search term...")
    
    filtered_df = df.copy()
    if search_term:
        search_term = search_term.lower()
        filtered_df = filtered_df[
            filtered_df.apply(lambda row: row.astype(str).str.lower().str.contains(search_term).any(), axis=1)
        ]
    
    display_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'LTP', 'Strike Price', 'Option Type', 'Underlying', 'Volume', 'Open Interest']
    display_df = filtered_df[display_columns].copy()
    
    for col in ['Open', 'High', 'Low', 'Close', 'LTP', 'Strike Price', 'Underlying']:
        if col in display_df.columns:
            display_df[col] = display_df[col].round(2)
    
    if 'Date' in display_df.columns:
        display_df['Date'] = pd.to_datetime(display_df['Date'], format='%d-%b-%Y', errors='coerce').dt.strftime('%d-%b-%Y')
    
    st.dataframe(
        display_df,
        use_container_width=True,
        height=400,
        column_config={
            "Date": st.column_config.DateColumn("Date"),
            "Open": st.column_config.NumberColumn("Open", format="%.2f"),
            "High": st.column_config.NumberColumn("High", format="%.2f"),
            "Low": st.column_config.NumberColumn("Low", format="%.2f"),
            "Close": st.column_config.NumberColumn("Close", format="%.2f"),
            "LTP": st.column_config.NumberColumn("LTP", format="%.2f"),
            "Strike Price": st.column_config.NumberColumn("Strike Price", format="%.2f"),
            "Underlying": st.column_config.NumberColumn("Underlying", format="%.2f"),
            "Volume": st.column_config.NumberColumn("Volume", format="%d"),
            "Open Interest": st.column_config.NumberColumn("Open Interest", format="%d")
        }
    )

def main():
    st.title("NSE Option Chart Generator")
    
    col1, col2 = st.columns(2)
    
    with col1:
        symbol = st.selectbox("Stock Symbol *", options=STOCK_SYMBOLS, index=0, key="symbol")
        instrument_type = st.selectbox("Instrument Type *", options=PREDEFINED_INSTRUMENTS_TYPE, index=0, key="instrument_type")
        date_range_option = st.selectbox(
            "Date Range for Strike Prices *",
            options=["Short (7 days)", "10 days", "15 days", "20 days", "Medium (30 days)", "Long (90 days)"],
            index=2,  # Default to 15 days
            key="date_range"
        )
    
    with col2:
        expiry_date = st.date_input("Expiry Date (DD-MM-YYYY) *", value=datetime(2025, 6, 26), format="DD-MM-YYYY", min_value=datetime(2000, 1, 1), key="expiry_date")
        to_date = st.date_input("To Date (DD-MM-YYYY) *", value=datetime(2025, 6, 26), format="DD-MM-YYYY", min_value=datetime(2000, 1, 1), key="to_date")
        option_type = st.selectbox("Option Type *", options=["CE", "PE"], index=0, key="option_type")
    
    # Map date range option to days
    date_range_days = {
        "Short (7 days)": 7,
        "10 days": 10,
        "15 days": 15,
        "20 days": 20,
        "Medium (30 days)": 30,
        "Long (90 days)": 90
    }
    selected_date_range_days = date_range_days[date_range_option]
    
    # Initialize session state for strike prices
    if 'strike_prices' not in st.session_state:
        st.session_state.strike_prices = [0]
    
    # Fetch strike prices when inputs change
    if symbol and instrument_type and expiry_date and to_date:
        try:
            st.session_state.strike_prices = fetch_strike_prices(symbol, expiry_date, instrument_type, selected_date_range_days, to_date)
        except Exception as e:
            st.error(f"Error fetching strike prices: {str(e)}")
            st.session_state.strike_prices = [0]
    
    strike_price = st.selectbox("Strike Price *", options=st.session_state.strike_prices, index=0, key="strike_price")
    
    # Validate date range
    from_date = to_date - timedelta(days=selected_date_range_days)
    if to_date < from_date:
        st.error("To Date must be on or after From Date (Expiry Date - 90 days).")
        return
    
    all_fields_filled = (
        symbol is not None and
        instrument_type is not None and
        expiry_date is not None and
        to_date is not None and
        option_type is not None and
        strike_price is not None and
        strike_price > 0
    )

    if not all_fields_filled:
        st.warning("Please fill all required fields marked with *. If strike prices are not loading, try a different symbol, expiry date, or date range.")
    
    fetch_button = st.button("Fetch Data", disabled=not all_fields_filled)

    if 'df_option' not in st.session_state:
        st.session_state.df_option = None

    if fetch_button and all_fields_filled:
        try:
            st.session_state.df_option = fetch_nse_data(from_date, to_date, symbol, expiry_date, option_type, strike_price, instrument_type)
        except Exception as e:
            st.error(f"Error fetching data: {str(e)}")
            st.session_state.df_option = None

    if st.session_state.df_option is not None and not st.session_state.df_option.empty:
        fig_option = create_candlestick_chart(st.session_state.df_option, expiry_date, strike_price, symbol, chart_type="Option")
        if fig_option:
            st.subheader(f"{symbol} - Option Chart")
            st.plotly_chart(fig_option, use_container_width=True, config={"scrollZoom": True})
            display_data_table(st.session_state.df_option)
    elif st.session_state.df_option is not None:
        st.warning("No option data available to display.")

if __name__ == "__main__":
    main()