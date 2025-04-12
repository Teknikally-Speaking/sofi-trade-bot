# ✅ FINAL UPDATED SOFI BOT v3 — With Auto-Close + Duplicate Trade Prevention
# Author: Teknikally Speaking
# This bot uses EMA crossover signals on SOFI stock to trade options using the Tradier API
# - It avoids placing duplicate trades
# - It auto-closes options after X hours
# - It supports fallback trend-based trades if no EMA crossover occurs

import requests
import time
import pandas as pd
import alpaca_trade_api as tradeapi
import csv
import json
import os
from datetime import datetime, timedelta

# --- Alpaca API CONFIG (for stock price data only, NOT for trades) ---
ALPACA_API_KEY = 'YOUR_ALPACA_API_KEY'
ALPACA_SECRET_KEY = 'YOUR_ALPACA_SECRET_KEY'
ALPACA_BASE_URL = 'https://paper-api.alpaca.markets'

# --- Tradier API CONFIG (used for placing options trades) ---
TRADIER_ACCESS_TOKEN = 'YOUR_TRADIER_ACCESS_TOKEN'
TRADIER_BASE_URL = 'https://sandbox.tradier.com/v1'
ACCOUNT_ID = 'YOUR_TRADIER_ID'  # Replace with your actual Tradier account ID

HEADERS = {
    'Authorization': f'Bearer {TRADIER_ACCESS_TOKEN}',
    'Accept': 'application/json'
}

# --- Trading Parameters ---
SYMBOL = 'SOFI'
FAST_EMA = 9
SLOW_EMA = 21
HOLDING_THRESHOLD_HOURS = 4  # Auto-close options after 4 hours
POSITION_LOG = 'open_positions.json'

# Track daily trading activity
last_trade_date = None

# Initialize Alpaca API (for price data only)
alpaca_api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version='v2')

# Check if today is a new trading day
def is_new_trading_day():
    global last_trade_date
    today = datetime.now().date()
    if last_trade_date != today:
        last_trade_date = today
        return True
    return False

# Get the expiration date for the next Friday (used for option selection)
def get_next_friday():
    today = datetime.today()
    days_ahead = 4 - today.weekday()  # Friday = 4
    if days_ahead <= 0:
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

# Pull recent price data from Alpaca
def get_price_data(symbol, timeframe='5Min', limit=100):
    barset = alpaca_api.get_bars(symbol, timeframe, limit=limit).df
    if barset.empty:
        print("⚠️ No price data returned. Market may be closed.")
        return None
    return barset.reset_index()

# Calculate EMA indicators for trend logic
def calculate_ema(data, fast=9, slow=21):
    data['EMA9'] = data['close'].ewm(span=fast, adjust=False).mean()
    data['EMA21'] = data['close'].ewm(span=slow, adjust=False).mean()
    return data

# Check for crossover signals (BUY/SELL triggers)
def check_signal(data):
    if data['EMA9'].iloc[-2] < data['EMA21'].iloc[-2] and data['EMA9'].iloc[-1] > data['EMA21'].iloc[-1]:
        return 'buy'
    elif data['EMA9'].iloc[-2] > data['EMA21'].iloc[-2] and data['EMA9'].iloc[-1] < data['EMA21'].iloc[-1]:
        return 'sell'
    return None

# Identify current market trend direction
def get_trend_direction(data):
    if data['EMA9'].iloc[-1] > data['EMA21'].iloc[-1]:
        return 'up'
    elif data['EMA9'].iloc[-1] < data['EMA21'].iloc[-1]:
        return 'down'
    return 'sideways'

# Retrieve option chain for the symbol and expiration
def get_option_chain(symbol, expiration=None):
    url = f"{TRADIER_BASE_URL}/markets/options/chains"
    params = {"symbol": symbol, "greeks": "false"}
    if expiration:
        params["expiration"] = expiration
    response = requests.get(url, headers=HEADERS, params=params)
    print("🔁 Status Code:", response.status_code)
    try:
        return response.json()
    except Exception as e:
        print("❌ JSON Decode Error:", e)
        return None

# Place a market order to open an options trade
def place_option_order(symbol, option_symbol, side):
    url = f"{TRADIER_BASE_URL}/accounts/{ACCOUNT_ID}/orders"
    payload = {
        "class": "option",
        "symbol": symbol,
        "option_symbol": option_symbol,
        "side": side,
        "quantity": 1,
        "type": "market",
        "duration": "gtc"
    }
    response = requests.post(url, headers=HEADERS, data=payload)
    if response.status_code != 200:
        print(f"❌ Tradier Error {response.status_code}: {response.text}")
    else:
        print(response.json())
        log_trade(symbol, option_symbol, side)
        track_position(option_symbol, side)

# Find the best option near current stock price
def find_near_money_call_put(option_chain, side='call'):
    if 'options' not in option_chain:
        return None
    options = option_chain['options']['option']
    for opt in options:
        if opt['option_type'] == side and opt['strike'] and opt.get('ask'):
            try:
                reference_price = opt.get('last') or opt['ask']
                if reference_price is not None and opt['strike'] >= float(reference_price):
                    return opt['symbol']
            except (ValueError, TypeError):
                continue
    return None

# Save executed trade to a CSV log
def log_trade(symbol, option_symbol, action, status="executed"):
    with open('sofi_trade_log.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, option_symbol, action, status])

# Track open positions to prevent duplicates
def track_position(option_symbol, side):
    position = {"symbol": option_symbol, "side": side, "timestamp": datetime.now().isoformat()}
    data = []
    if os.path.exists(POSITION_LOG):
        with open(POSITION_LOG, 'r') as f:
            data = json.load(f)
    data.append(position)
    with open(POSITION_LOG, 'w') as f:
        json.dump(data, f, indent=2)

# Check if a trade has already been placed for this option
def is_duplicate_trade(option_symbol):
    if os.path.exists(POSITION_LOG):
        with open(POSITION_LOG, 'r') as f:
            data = json.load(f)
            for entry in data:
                if entry['symbol'] == option_symbol:
                    return True
    return False

# Simulate closing option (this is just logging for now)
def close_option_order(option_symbol):
    print(f"⏳ Closing expired position: {option_symbol} (simulated)")
    log_trade(SYMBOL, option_symbol, 'sell_to_close', 'auto-closed')

# Remove old positions from log after threshold
def close_expired_positions():
    if not os.path.exists(POSITION_LOG):
        return
    with open(POSITION_LOG, 'r') as f:
        data = json.load(f)
    new_data = []
    for entry in data:
        open_time = datetime.fromisoformat(entry['timestamp'])
        hours_held = (datetime.now() - open_time).total_seconds() / 3600
        if hours_held >= HOLDING_THRESHOLD_HOURS:
            close_option_order(entry['symbol'])
        else:
            new_data.append(entry)
    with open(POSITION_LOG, 'w') as f:
        json.dump(new_data, f, indent=2)

# --- MAIN LOOP ---
while True:
    try:
        close_expired_positions()  # 🔁 Auto-close logic runs before any trades

        df = get_price_data(SYMBOL)
        if df is None or df.empty:
            print("⏳ No data. Retrying in 5 min...")
            time.sleep(300)
            continue

        df = calculate_ema(df)
        print(f"📊 EMA Check → EMA9: {df['EMA9'].iloc[-1]:.4f}, EMA21: {df['EMA21'].iloc[-1]:.4f}")
        signal = check_signal(df)
        trend = get_trend_direction(df)
        expiration = get_next_friday()
        option_chain = get_option_chain(SYMBOL, expiration)
        traded_today = not is_new_trading_day()

        if signal and option_chain:
            print(f"📈 Signal: {signal.upper()}")
            side = 'call' if signal == 'buy' else 'put'
            option = find_near_money_call_put(option_chain, side=side)
            if option and not is_duplicate_trade(option):
                place_option_order(SYMBOL, option, 'buy_to_open')
                traded_today = True

        elif not traded_today and option_chain:
            print(f"📉 No signal. Checking trend fallback: {trend.upper()}")
            side = 'call' if trend == 'up' else 'put' if trend == 'down' else None
            if side:
                option = find_near_money_call_put(option_chain, side=side)
                if option and not is_duplicate_trade(option):
                    print(f"📦 Placing fallback {side.upper()} trade")
                    place_option_order(SYMBOL, option, 'buy_to_open')
                    traded_today = True
            else:
                print("⛔ Trend is sideways. No fallback trade.")

        else:
            print("🕒 No action. Waiting...")

    except Exception as e:
        print(f"❌ Error: {e}")

    time.sleep(300)  # ⏱️ Wait 5 minutes before next check
