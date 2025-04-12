
# ✅ Final updated SOFI bot with duplicate trade prevention and auto-close logic

import requests
import time
import pandas as pd
import alpaca_trade_api as tradeapi
import csv
import json
import os
from datetime import datetime, timedelta

# --- Alpaca Config (for price data only) ---
ALPACA_API_KEY = 'PK5Y7O0LXDMRYB5C89F1'
ALPACA_SECRET_KEY = 'N9VXrxRHdJtnehEXKGDNdxz2IW3PQcaTkyhmorfE'
ALPACA_BASE_URL = 'https://paper-api.alpaca.markets'

# --- Tradier Config (for options trading) ---
TRADIER_ACCESS_TOKEN = '4n5VzTUFF87ED2B9knP5cNTBCL7D'
TRADIER_BASE_URL = 'https://sandbox.tradier.com/v1'
ACCOUNT_ID = 'VA5782235'  # Replace with actual if in production

HEADERS = {
    'Authorization': f'Bearer {TRADIER_ACCESS_TOKEN}',
    'Accept': 'application/json'
}

SYMBOL = 'SOFI'
FAST_EMA = 9
SLOW_EMA = 21
HOLDING_THRESHOLD_HOURS = 4  # close trades after this many hours
POSITION_LOG = 'open_positions.json'

last_trade_date = None

alpaca_api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version='v2')

def is_new_trading_day():
    global last_trade_date
    today = datetime.now().date()
    if last_trade_date != today:
        last_trade_date = today
        return True
    return False

def get_next_friday():
    today = datetime.today()
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

def get_price_data(symbol, timeframe='5Min', limit=100):
    barset = alpaca_api.get_bars(symbol, timeframe, limit=limit).df
    if barset.empty:
        print("⚠️ No price data returned. Market may be closed.")
        return None
    return barset.reset_index()

def calculate_ema(data, fast=9, slow=21):
    data['EMA9'] = data['close'].ewm(span=fast, adjust=False).mean()
    data['EMA21'] = data['close'].ewm(span=slow, adjust=False).mean()
    return data

def check_signal(data):
    if data['EMA9'].iloc[-2] < data['EMA21'].iloc[-2] and data['EMA9'].iloc[-1] > data['EMA21'].iloc[-1]:
        return 'buy'
    elif data['EMA9'].iloc[-2] > data['EMA21'].iloc[-2] and data['EMA9'].iloc[-1] < data['EMA21'].iloc[-1]:
        return 'sell'
    return None

def get_trend_direction(data):
    if data['EMA9'].iloc[-1] > data['EMA21'].iloc[-1]:
        return 'up'
    elif data['EMA9'].iloc[-1] < data['EMA21'].iloc[-1]:
        return 'down'
    return 'sideways'

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

def log_trade(symbol, option_symbol, action, status="executed"):
    with open('sofi_trade_log.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, option_symbol, action, status])

def track_position(option_symbol, side):
    position = {"symbol": option_symbol, "side": side, "timestamp": datetime.now().isoformat()}
    data = []
    if os.path.exists(POSITION_LOG):
        with open(POSITION_LOG, 'r') as f:
            data = json.load(f)
    data.append(position)
    with open(POSITION_LOG, 'w') as f:
        json.dump(data, f, indent=2)

def is_duplicate_trade(option_symbol):
    if os.path.exists(POSITION_LOG):
        with open(POSITION_LOG, 'r') as f:
            data = json.load(f)
            for entry in data:
                if entry['symbol'] == option_symbol:
                    return True
    return False

def close_option_order(option_symbol):
    print(f"⏳ Closing expired position: {option_symbol} (simulated)")
    log_trade(SYMBOL, option_symbol, 'sell_to_close', 'auto-closed')

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
        close_expired_positions()
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

    time.sleep(300)  # 5 minutes
