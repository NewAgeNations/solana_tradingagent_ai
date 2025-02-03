import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import time
import json
import streamlit as st
from threading import Thread
from solana.publickey import PublicKey
from decimal import Decimal  # Import Decimal for precise price handling

# Load configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Validate configuration required_keys
required_keys = ["rugcheck_api_url", "database_config"]
for key in required_keys:
    if key not in config:
        raise ValueError(f"Missing required configuration key: {key}")

# Constants
RUGCHECK_API_URL = config["rugcheck_api_url"]
DATABASE_CONFIG = config["database_config"]

# Initialize session state for token data
if "token_data" not in st.session_state:
    st.session_state.token_data = []

# Validate Solana token address format
def is_valid_solana_address(address):
    try:
        PublicKey(address)  # Using Solana's PublicKey to validate
        return True
    except Exception:
        return False

# Fetch token data from the dexscreener table in the database
def fetch_token_data():
    try:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(""" SELECT token_address, token_name FROM dexscreener; """)
                tokens = cursor.fetchall()
                return [{"address": token[0], "name": token[1]} for token in tokens]
    except Exception as e:
        st.error(f"Error fetching token data: {str(e)}")
        return []

# Fetch entry price for a given token address from dexscreener database
def fetch_token_prices(mint_address):
    try:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(""" SELECT entry_price FROM dexscreener WHERE token_address = %s; """, (mint_address,))
                result = cursor.fetchone()
                if result and result[0] is not None:  # Check if result is not None
                    return Decimal(result[0])  # Convert price to Decimal
                return Decimal("0.0")  # Return a default value if price is None
    except Exception as e:
        st.error(f"Error fetching token prices: {e}")
        return Decimal("0.0")  # Return a default value in case of an error

# Check token on RugCheck.xyz with enhanced error handling and retry mechanism
def check_token_on_rugcheck(token_address):
    retries = 3
    for attempt in range(retries):
        try:
            response = requests.get(f"{RUGCHECK_API_URL}/v1/tokens/{token_address}/report/summary", timeout=10)
            response.raise_for_status()
            data = response.json()
            if 'risks' in data and data['risks']:
                return "Sell"
            return "Buy"
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 404:
                return None  # Token not found, return None
            else:
                st.error(f"HTTP error occurred: {http_err}")
                return None
        except requests.exceptions.RequestException as req_err:
            if attempt < retries - 1:
                time.sleep(2)  # Wait before retrying
            else:
                st.error(f"Request error occurred: {req_err}")
                return None

# Save data to PostgreSQL database with DECIMAL for entry_price
def save_to_db(data):
    try:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS token_data (
                        timestamp TIMESTAMP,
                        token_address TEXT PRIMARY KEY,
                        token_name TEXT,
                        trade_signal TEXT,
                        entry_price DECIMAL(18, 8)
                    );
                """)
                execute_values(cursor, """
                    INSERT INTO token_data (timestamp, token_address, token_name, trade_signal, entry_price)
                    VALUES %s ON CONFLICT (token_address) DO UPDATE SET 
                    timestamp = excluded.timestamp,
                    token_name = excluded.token_name,
                    trade_signal = excluded.trade_signal,
                    entry_price = excluded.entry_price;
                """, data)
                conn.commit()
    except Exception as e:
        st.error(f"Error saving to database: {str(e)}")

# Fetch historical data from the database with pagination support
def fetch_historical_data(page_size=10, page_number=1):
    try:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT timestamp, token_address, token_name, trade_signal, entry_price 
                    FROM token_data 
                    ORDER BY timestamp DESC;
                """)
                historical_data = cursor.fetchall()
                
                start_index = (page_number - 1) * page_size
                end_index = start_index + page_size
                
                results = [
                    {
                        "timestamp": row[0],
                        "token_address": row[1],
                        "token_name": row[2],
                        "trade_signal": row[3],
                        "entry_price": row[4] if row[4] is not None else Decimal("0.0")  # Handle None values for entry_price
                    }
                    for row in historical_data[start_index:end_index]
                ]
                
                return results
    except Exception as e:
        st.error(f"Error fetching historical data: {str(e)}")
        return []

# Main function to run the bot in a separate thread to avoid blocking Streamlit dashboard
def main():
    while True:
        trending_tokens = fetch_token_data()
        for token in trending_tokens:
            token_address = token.get("address")
            if not token_address or not is_valid_solana_address(token_address):
                continue
            
            trade_signal = check_token_on_rugcheck(token_address)
            if trade_signal is None:
                continue
            
            entry_price = fetch_token_prices(token_address)
            
            timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            
            data_to_save = [(timestamp, token_address, token.get("name"), trade_signal, entry_price)]
            
            save_to_db(data_to_save)

        time.sleep(300)

# Streamlit dashboard to display historical data and current prices
def display_dashboard():
    st.title("NewAge Nations AI")
    
    st.subheader("DCA Trading Signals: NFA. DYOR")
    
    page_size = st.slider("Page Size", min_value=5, max_value=50, value=10)
    page_number = st.number_input("Page Number", min_value=1, step=1, value=1)
    
    historical_data = fetch_historical_data(page_size=page_size, page_number=page_number)
    
    if historical_data:
        df = pd.DataFrame(historical_data)
        st.dataframe(df)
    else:
        st.write("No historical data available.")

if __name__ == "__main__":
    Thread(target=main).start()
    display_dashboard()
