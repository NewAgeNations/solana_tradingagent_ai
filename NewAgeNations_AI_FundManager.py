import requests
import pandas as pd
import numpy as np
from numpy import nan
import psycopg2
from psycopg2.extras import execute_values
from sklearn.ensemble import IsolationForest
import time
import json
import streamlit as st
import pandas_ta as ta  # Use pandas_ta for technical indicators
import logging
from apify_client import ApifyClient  # Use ApifyClient for fetching trending tokens

# Load configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Constants
APIFY_API_TOKEN = config["apify_api_token"]  # Add Apify API token to config.json
RUGCHECK_API_URL = config["rugcheck_api_url"]
TELEGRAM_BOT_TOKEN = config["telegram_bot_token"]
TELEGRAM_CHAT_ID = config["telegram_chat_id"]
DATABASE_CONFIG = config["database_config"]
FILTERS = config["filters"]
BLACKLIST = config["blacklist"]
DEEPSEEK_API_URL = config["deepseek_api_url"]  # Add DeepSeek API URL to config.json
DEEPSEEK_API_KEY = config["deepseek_api_key"]  # Add DeepSeek API key to config.json

# Initialize session state for logs and token data
if "logs" not in st.session_state:
    st.session_state.logs = []
if "token_data" not in st.session_state:
    st.session_state.token_data = []

# Initialize ApifyClient
client = ApifyClient(APIFY_API_TOKEN)

# Fetch DeepSeek insights
def fetch_deepseek_insights(token_address):
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "token_address": token_address,
            "analysis_type": "predictive_analytics"  # Can be "sentiment_analysis" or "risk_management"
        }
        response = requests.post(f"{DEEPSEEK_API_URL}/insights", headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Failed to fetch DeepSeek insights: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Error fetching DeepSeek insights: {e}")
        return None

# Analyze sentiment using DeepSeek
def analyze_sentiment(token_address):
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "token_address": token_address,
            "analysis_type": "sentiment_analysis"
        }
        response = requests.post(f"{DEEPSEEK_API_URL}/sentiment", headers=headers, json=payload)
        if response.status_code == 200:
            sentiment_data = response.json()
            return sentiment_data.get("sentiment_score", 0)  # Return sentiment score (e.g., -1 to 1)
        else:
            logging.error(f"Failed to analyze sentiment: {response.status_code}")
            return 0
    except Exception as e:
        logging.error(f"Error analyzing sentiment: {e}")
        return 0

# Make trading decision with DeepSeek insights
def make_trading_decision(data, deepseek_insights):
    # Example logic: Buy if DeepSeek predicts price increase and sentiment is positive
    if (deepseek_insights.get("price_prediction", "neutral") == "increase" and
        deepseek_insights.get("sentiment_score", 0) > 0.5 and  # Positive sentiment
        data['rsi'].iloc[-1] < 30):  # RSI < 30 (oversold)
        return "buy"
    # Sell if DeepSeek predicts price decrease and sentiment is negative
    elif (deepseek_insights.get("price_prediction", "neutral") == "decrease" and
          deepseek_insights.get("sentiment_score", 0) < -0.5 and  # Negative sentiment
          data['rsi'].iloc[-1] > 70):  # RSI > 70 (overbought)
        return "sell"
    else:
        return "hold"

# Replace fetch_trending_tokens with a free alternative (e.g., CoinGecko API)
def fetch_trending_tokens():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/search/trending")
        if response.status_code == 200:
            trending_tokens = response.json().get("coins", [])
            logging.info(f"Fetched {len(trending_tokens)} trending tokens from CoinGecko.")
            return trending_tokens
        else:
            logging.error(f"Failed to fetch trending tokens from CoinGecko: {response.status_code}")
            return []
    except Exception as e:
        logging.error(f"Error fetching trending tokens: {e}")
        return []

# Fetch token data from Apify results
def fetch_token_data(token):
    try:
        # Extract relevant data from the Apify result
        token_data = {
            "pairs": [
                {
                    "baseToken": {"address": token.get("address")},
                    "priceUsd": token.get("priceUsd"),
                    "high": token.get("high"),
                    "low": token.get("low"),
                    "volume": {"h24": token.get("volumeH24")},
                    "liquidity": {"usd": token.get("liquidityUsd")},
                    "fdv": token.get("fdv"),
                    "developerAddress": token.get("developerAddress"),
                }
            ]
        }
        logging.info(f"Successfully fetched data for token: {token.get('address')}")
        return token_data
    except Exception as e:
        logging.error(f"Failed to fetch data for token: {e}")
        st.session_state.logs.append(f"Failed to fetch data for token: {token.get('address')}")
        return None

# Check token on RugCheck.xyz
def check_token_on_rugcheck(token_address):
    response = requests.get(f"{RUGCHECK_API_URL}/{token_address}")
    if response.status_code == 200:
        return response.json()
    else:
        st.session_state.logs.append(f"Failed to check token on RugCheck: {token_address}")
        return None

# Calculate MACD using pandas_ta
def calculate_macd(data):
    macd = ta.macd(data['close'], fast=12, slow=26, signal=9)
    data = pd.concat([data, macd], axis=1)
    return data

# Calculate ATR using pandas_ta
def calculate_atr(data):
    atr = ta.atr(data['high'], data['low'], data['close'], length=14)
    data['atr'] = atr
    return data

# Calculate OBV using pandas_ta
def calculate_obv(data):
    obv = ta.obv(data['close'], data['volume'])
    data['obv'] = obv
    return data

# Calculate RSI using pandas_ta
def calculate_rsi(data):
    rsi = ta.rsi(data['close'], length=14)
    data['rsi'] = rsi
    return data

# Check if token is marked as "Good" on RugCheck
def is_token_good(rugcheck_result):
    if not rugcheck_result:
        return False
    return rugcheck_result.get("status", "").lower() == "good"

# Check if token supply is bundled
def is_supply_bundled(token_data):
    supply_distribution = token_data.get("supply_distribution", [])
    top_wallets_share = sum(wallet["share"] for wallet in supply_distribution[:5])
    return top_wallets_share > 90  # Adjust threshold as needed

# Save data to PostgreSQL database
def save_to_db(data):
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        cursor = conn.cursor()

        logging.info(f"Inserting data into database: {data}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_data (
                timestamp TIMESTAMP,
                token_address TEXT PRIMARY KEY,
                price_usd FLOAT,
                volume_usd FLOAT,
                liquidity_usd FLOAT,
                market_cap_usd FLOAT,
                developer_address TEXT,
                is_fake_volume BOOLEAN,
                is_good_token BOOLEAN,
                is_supply_bundled BOOLEAN,
                macd FLOAT,
                signal FLOAT,
                histogram FLOAT,
                atr FLOAT,
                obv FLOAT,
                rsi FLOAT,
                trading_signal TEXT,
                deepseek_prediction TEXT,
                sentiment_score FLOAT
            )
        """)

        execute_values(cursor, """
            INSERT INTO token_data (timestamp, token_address, price_usd, volume_usd, liquidity_usd, market_cap_usd, developer_address, is_fake_volume, is_good_token, is_supply_bundled, macd, signal, histogram, atr, obv, rsi, trading_signal, deepseek_prediction, sentiment_score)
            VALUES %s
            ON CONFLICT (token_address) DO UPDATE 
            SET timestamp = excluded.timestamp,
                price_usd = excluded.price_usd,
                volume_usd = excluded.volume_usd,
                liquidity_usd = excluded.liquidity_usd,
                market_cap_usd = excluded.market_cap_usd,
                developer_address = excluded.developer_address,
                is_fake_volume = excluded.is_fake_volume,
                is_good_token = excluded.is_good_token,
                is_supply_bundled = excluded.is_supply_bundled,
                macd = excluded.macd,
                signal = excluded.signal,
                histogram = excluded.histogram,
                atr = excluded.atr,
                obv = excluded.obv,
                rsi = excluded.rsi,
                trading_signal = excluded.trading_signal,
                deepseek_prediction = excluded.deepseek_prediction,
                sentiment_score = excluded.sentiment_score
        """, data)

        conn.commit()
        logging.info("Database updated successfully.")
        cursor.execute("SELECT COUNT(*) FROM token_data;")
        result = cursor.fetchone()
        print(f"Database connection successful. Number of records: {result[0]}")

    except Exception as e:
        logging.error(f"Database save error: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

# Detect anomalies using Isolation Forest
def detect_anomalies(prices):
    model = IsolationForest(contamination=0.01)
    prices = np.array(prices).reshape(-1, 1)
    anomalies = model.fit_predict(prices)
    return anomalies

# Send Telegram alert
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        st.session_state.logs.append("Failed to send Telegram alert")

# Check if token or developer is blacklisted
def is_blacklisted(token_address, developer_address):
    if token_address in BLACKLIST["tokens"]:
        return True
    if developer_address in BLACKLIST["developers"]:
        return True
    return False

# Apply filters to token data
def apply_filters(token_data):
    pair_data = token_data.get('pairs', [{}])[0]
    liquidity_usd = float(pair_data.get('liquidity', {}).get('usd', 0))
    volume_usd = float(pair_data.get('volume', {}).get('h24', 0))
    market_cap_usd = float(pair_data.get('fdv', 0))
    
    if (liquidity_usd < FILTERS["min_liquidity_usd"] or
        volume_usd < FILTERS["min_volume_usd"] or
        market_cap_usd < FILTERS["min_market_cap_usd"]):
        return False
    return True

# Fetch historical data from the database
def fetch_historical_data():
    try:
        conn = psycopg2.connect(**DATABASE_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                timestamp, token_address, price_usd, volume_usd, liquidity_usd, 
                market_cap_usd, developer_address, is_fake_volume, is_good_token, 
                is_supply_bundled, macd, signal, histogram, atr, obv, rsi, 
                trading_signal, deepseek_prediction, sentiment_score
            FROM token_data
        """)
        data = cursor.fetchall()
        cursor.close()
        conn.close()

        # Ensure all columns are present, even if some data is missing
        return [
            row if len(row) == 19 else row + (None,) * (19 - len(row))
            for row in data
        ]
    except Exception as e:
        st.session_state.logs.append(f"Error fetching historical data: {e}")
        return []

# Streamlit Dashboard
def display_dashboard():
    st.title("NewAge Nations AI Agent")

    # Display analyzed tokens
    st.subheader("Analyzed Tokens")
    token_df = pd.DataFrame(st.session_state.token_data)
    if not token_df.empty:
        st.dataframe(token_df)
    else:
        st.write("No tokens analyzed yet.")

    # Display logs
    st.subheader("Logs")
    for log in st.session_state.logs:
        st.write(log)

    # Display historical data
    st.subheader("Historical Token Data")
    historical_data = fetch_historical_data()
    if historical_data:
        st.dataframe(pd.DataFrame(historical_data, columns=["timestamp", "token_address", "price_usd", "volume_usd", "liquidity_usd", "market_cap_usd", "developer_address", "is_fake_volume", "is_good_token", "is_supply_bundled", "macd", "signal", "histogram", "atr", "obv", "rsi", "trading_signal", "deepseek_prediction", "sentiment_score"]))
    else:
        st.write("No historical data found.")

# Update the main function to handle Streamlit warnings
def main():
    while True:
        # Fetch trending tokens
        trending_tokens = fetch_trending_tokens()
        if not trending_tokens:
            logging.warning("No trending tokens found. Retrying in 5 minutes...")
            time.sleep(300)  # Wait 5 minutes before retrying
            continue

        # Analyze each token
        for token in trending_tokens:
            token_address = token.get("item", {}).get("id")  # Adjust for CoinGecko's response structure
            if not token_address:
                continue

            # Fetch token data
            token_data = fetch_token_data(token)
            if not token_data:
                continue

            # Extract relevant data
            pair_data = token_data.get('pairs', [{}])[0]
            developer_address = pair_data.get('developerAddress', 'unknown')

            # Check if token or developer is blacklisted
            if is_blacklisted(token_address, developer_address):
                logging.info(f"Token or developer blacklisted: {token_address}, {developer_address}")
                continue

            # Apply filters
            if not apply_filters(token_data):
                logging.info(f"Token does not meet filter criteria: {token_address}")
                continue

            # Check token on RugCheck
            rugcheck_result = check_token_on_rugcheck(token_address)
            is_good_token = is_token_good(rugcheck_result)

            if not is_good_token:
                logging.info(f"Token is not marked as 'Good' on RugCheck: {token_address}")
                BLACKLIST["tokens"].append(token_address)  # Add to blacklist
                BLACKLIST["developers"].append(developer_address)  # Add developer to blacklist
                continue

            # Check if supply is bundled
            if is_supply_bundled(token_data):
                logging.info(f"Token supply is bundled: {token_address}")
                BLACKLIST["tokens"].append(token_address)  # Add to blacklist
                BLACKLIST["developers"].append(developer_address)  # Add developer to blacklist
                continue

            # Fetch DeepSeek insights
            deepseek_insights = fetch_deepseek_insights(token_address)
            sentiment_score = analyze_sentiment(token_address)

            # Prepare data for technical analysis
            data = pd.DataFrame({
                'close': [float(pair_data.get('priceUsd', 0))],
                'high': [float(pair_data.get('high', 0))],
                'low': [float(pair_data.get('low', 0))],
                'volume': [float(pair_data.get('volume', {}).get('h24', 0))]
            })

            # Calculate indicators
            data = calculate_macd(data)
            data = calculate_atr(data)
            data = calculate_obv(data)
            data = calculate_rsi(data)

            # Make trading decision with DeepSeek insights
            decision = make_trading_decision(data, deepseek_insights)

            # Send Telegram alert for trading signal
            if decision != "hold":
                send_telegram_alert(f"🚀 Trading Signal: {decision.upper()} for token: {token_address}")

            # Save data to database
            timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            price_usd = float(pair_data.get('priceUsd', 0))
            volume_usd = float(pair_data.get('volume', {}).get('h24', 0))
            liquidity_usd = float(pair_data.get('liquidity', {}).get('usd', 0))
            market_cap_usd = float(pair_data.get('fdv', 0))

            data = [(timestamp, token_address, price_usd, volume_usd, liquidity_usd, market_cap_usd, developer_address, False, is_good_token, is_supply_bundled, data['MACD_12_26_9'].iloc[-1], data['MACDs_12_26_9'].iloc[-1], data['MACDh_12_26_9'].iloc[-1], data['atr'].iloc[-1], data['obv'].iloc[-1], data['rsi'].iloc[-1], decision, deepseek_insights.get("price_prediction", "neutral"), sentiment_score)]
            save_to_db(data)

            # Detect anomalies
            prices = [price_usd]  # In a real-world scenario, fetch historical prices from the database
            anomalies = detect_anomalies(prices)
            if -1 in anomalies:
                send_telegram_alert(f"🚨 Anomaly detected for token: {token_address}")

        # Wait for 5 minutes before the next iteration
        time.sleep(300)

# Helper function to check if running with Streamlit
def is_running_with_streamlit():
    try:
        return st.runtime.exists()
    except AttributeError:
        return False

# Run the Streamlit dashboard only when using `streamlit run`
if __name__ == "__main__":
    try:
        if is_running_with_streamlit():
            display_dashboard()
        else:
            main()
    except Exception as e:
        logging.error(f"Error running the application: {e}")
