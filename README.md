# 📈 SOFI EMA Crossover Options Trading Bot

This bot monitors **SOFI stock price** using the **Alpaca API**, detects **EMA crossover signals**, and places **sandbox options trades** via the **Tradier API**.

It is designed for:
- Beginner to intermediate traders
- Automated execution of buy signals (calls or puts)
- Logging trades locally for review

---

## ✅ Features
- Pulls real-time SOFI stock price data from Alpaca
- Calculates 9-EMA and 21-EMA
- Detects bullish and bearish EMA crossovers
- Executes options trades in Tradier sandbox (buy call/put)
- Logs trades to a local CSV file for tracking
- Built-in error handling for market closures and missing data

---

## 🔧 Requirements
- Python 3.7+
- Alpaca Paper Trading Account
- Tradier Developer Account (Sandbox Mode)

### 📦 Python Libraries
```bash
pip install alpaca-trade-api pandas requests
```

---

## ⚙️ Setup Instructions

### 1. Configure Your Keys
Open the bot file and replace the following placeholders:
```python
ALPACA_API_KEY = 'YOUR_ALPACA_KEY'
ALPACA_SECRET_KEY = 'YOUR_ALPACA_SECRET'
TRADIER_ACCESS_TOKEN = 'YOUR_TRADIER_SANDBOX_TOKEN'
```
For Tradier, use:
```python
TRADIER_BASE_URL = 'https://sandbox.tradier.com/v1'
```

### 2. Create Tradier Developer App
- Visit: [https://developer.tradier.com](https://developer.tradier.com)
- Create a new application (select Sandbox)
- Copy your sandbox access token

### 3. Run the Bot
```bash
python SOFI-bot-v1.py
```

The bot will:
- Check SOFI price every 5 minutes
- Detect buy/sell signals
- Place a simulated call or put order in Tradier Sandbox
- Log the trade to `sofi_trade_log.csv`

---

## 📁 Output Files
- `sofi_trade_log.csv`: Logs all executed trades with timestamp, symbol, option, action, and status.

---

## 🚀 Next Upgrades (Optional)
- Add email or Discord alerts
- Connect to real trading account once approved
- Track option PnL using open/high/close prices
- Deploy 24/7 via a cloud server (like AWS or DigitalOcean)

---

## 📩 Support
If you want help building on this bot — adding alerts, logging, or more advanced strategies — just ask!