import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# Set up basic configuration
st.set_page_config(layout="wide")

# Create uploads directory
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def load_and_process_data(filepath):
    # Read and process CSV file
    df = pd.read_csv(filepath, header=None, dtype=str)
    headers = df.iloc[0].astype(str).str.strip()
    df = df[1:].reset_index(drop=True)
    df.columns = headers
    
    # Clean and convert data
    df.replace('-', pd.NA, inplace=True)
    df.dropna(inplace=True)
    numeric_columns = ['Open', 'High', 'Low', 'Close', 'LTP', 'Strike Price']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

def create_candlestick_chart(df, expiry, strike, instrument):
    # Filter data
    if 'Expiry' in df.columns and 'Strike Price' in df.columns:
        df = df[(df['Expiry'] == expiry) & (df['Strike Price'] == float(strike))]
    
    # Process dates
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df.sort_values(by='Date', inplace=True)
    
    # Create candlestick chart
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
    
    # Update layout
    fig.update_layout(
        title=f'{instrument} - Option Chart<br>Strike Price: {strike}<br>Expiry: {expiry}',
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

def main():
    st.title("Option Chart Generator")
    
    # File upload
    uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
    
    if uploaded_file is not None:
        # Save uploaded file
        filepath = os.path.join(UPLOAD_FOLDER, uploaded_file.name)
        with open(filepath, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        
        # Load and process data
        df = load_and_process_data(filepath)
        
        # Get instrument name from filename
        instrument = uploaded_file.name.split('_')[1].split('.')[0]
        
        # Selection options
        col1, col2 = st.columns(2)
        with col1:
            expiry_dates = df['Expiry'].unique() if 'Expiry' in df.columns else []
            selected_expiry = st.selectbox("Select Expiry Date", options=expiry_dates)
        
        with col2:
            strike_prices = df['Strike Price'].unique() if 'Strike Price' in df.columns else []
            selected_strike = st.selectbox("Select Strike Price", options=strike_prices)
        
        # Generate and display chart
        if selected_expiry and selected_strike:
            fig = create_candlestick_chart(df, selected_expiry, selected_strike, instrument)
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

if __name__ == '__main__':
    main()