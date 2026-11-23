
import os
import sqlite3
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone

# =========================
# AI INVESTMENT BOT V2
# Stocks + Crypto
# =========================

DB_NAME = "signals.db"

STOCKS = ["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "QQQ"]
CRYPTOS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def setup_database():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                market TEXT,
                price REAL,
                rsi REAL,
                score INTEGER,
                action TEXT,
                created_at TEXT
            )
        """)


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def analyze_data(symbol, market, df):
    if df is None or len(df) < 60:
        return None

    close = df["Close"].dropna()

    if len(close) < 60:
        return None

    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    rsi = calculate_rsi(close)

    latest_price = float(close.iloc[-1])
    latest_rsi = float(rsi.iloc[-1])
    score = 0

    if ema20.iloc[-1] > ema50.iloc[-1]:
        score += 2
    else:
        score -= 2

    if latest_rsi < 30:
        score += 2
    elif latest_rsi > 70:
        score -= 2

    if latest_price > ema20.iloc[-1]:
        score += 1
    else:
        score -= 1

    if score >= 3:
        action = "BUY WATCH"
    elif score <= -3:
        action = "SELL WATCH"
    else:
        action = "HOLD"

    return {
        "symbol": symbol,
        "market": market,
        "price": latest_price,
        "rsi": latest_rsi,
        "score": score,
        "action": action
    }


def get_stock_data(symbol):
    try:
        df = yf.download(
            symbol,
            period="6mo",
            interval="1h",
            progress=False,
            auto_adjust=True
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as error:
        print(f"Stock error {symbol}: {error}")
        return None


def get_crypto_data(symbol):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": "1h",
            "limit": 200
        }
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        rows = response.json()

        df = pd.DataFrame(rows, columns=[
            "time", "Open", "High", "Low", "Close", "Volume",
            "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])

        for column in ["Open", "High", "Low", "Close", "Volume"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        return df

    except Exception as error:
        print(f"Crypto error {symbol}: {error}")
        return None


def save_signal(signal):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            INSERT INTO signals
            (symbol, market, price, rsi, score, action, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            signal["symbol"],
            signal["market"],
            signal["price"],
            signal["rsi"],
            signal["score"],
            signal["action"],
            datetime.now(timezone.utc).isoformat()
        ))


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram nije konfigurisan.")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=20
        )
        response.raise_for_status()
    except Exception as error:
        print(f"Telegram notification error: {error}")


def send_email(message):
    # Email se dodaje u sljedećem koraku kroz GitHub Secrets.
    print("Email konfiguracija još nije dodana.")


def main():
    setup_database()
    results = []

    for symbol in STOCKS:
        df = get_stock_data(symbol)
        signal = analyze_data(symbol, "STOCK", df)
        if signal:
            results.append(signal)

    for symbol in CRYPTOS:
        df = get_crypto_data(symbol)
        signal = analyze_data(symbol, "CRYPTO", df)
        if signal:
            results.append(signal)

    if not results:
        print("Nema dostupnih podataka za analizu.")
        return

    for signal in results:
        save_signal(signal)

        message = (
            f"{signal['market']} | {signal['symbol']}\n"
            f"Cijena: {signal['price']:.6f}\n"
            f"RSI: {signal['rsi']:.2f}\n"
            f"Ocjena: {signal['score']}\n"
            f"Signal: {signal['action']}\n"
            "Informativna analiza, nije garancija profita."
        )

        print(message)
        send_telegram(message)

    print(f"Analiza završena. Ukupno signala: {len(results)}")


if __name__ == "__main__":
    main()
