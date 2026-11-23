import os, sqlite3, smtplib, json
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import requests
import yfinance as yf
import pandas as pd

DB = Path("signals.db")
BINANCE = "https://api.binance.com/api/v3/klines"

STOCKS = [x.strip() for x in os.getenv("STOCK_SYMBOLS", "AAPL,MSFT,NVDA,TSLA,SPY,QQQ").split(",") if x.strip()]
CRYPTOS = [x.strip().upper() for x in os.getenv("CRYPTO_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT").split(",") if x.strip()]

def indicators(df):
    close = df["close"]
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    return float(rsi.iloc[-1]), float(macd.iloc[-1]), float(signal.iloc[-1]), float(ema20.iloc[-1]), float(ema50.iloc[-1])

def assess(symbol, market, df):
    if df is None or len(df) < 60:
        return None
    rsi, macd, macd_sig, ema20, ema50 = indicators(df)
    price = float(df["close"].iloc[-1])
    volume = float(df["volume"].iloc[-1])
    avgvol = float(df["volume"].tail(20).mean())
    score = 0
    reasons = []
    if price > ema20 > ema50:
        score += 2; reasons.append("cijena iznad EMA20 i EMA50")
    elif price < ema20 < ema50:
        score -= 2; reasons.append("cijena ispod EMA20 i EMA50")
    if macd > macd_sig:
        score += 1; reasons.append("MACD iznad signalne linije")
    else:
        score -= 1; reasons.append("MACD ispod signalne linije")
    if 50 <= rsi <= 68:
        score += 1; reasons.append(f"RSI {rsi:.1f}: pozitivan momentum")
    elif rsi >= 75:
        score -= 1; reasons.append(f"RSI {rsi:.1f}: moguć prekupljen nivo")
    elif rsi <= 30:
        score += 1; reasons.append(f"RSI {rsi:.1f}: moguć preprodan nivo")
    if avgvol and volume > avgvol * 1.3:
        reasons.append("volumen iznad prosjeka")
        score += 1 if score > 0 else 0

    if score >= 3:
        action = "BUY WATCH"
    elif score <= -3:
        action = "SELL / AVOID"
    else:
        action = "HOLD"
    # This is a transparent indicator score, NOT a calibrated probability.
    confidence = min(85, 50 + abs(score) * 7)
    return {
        "symbol": symbol, "market": market, "price": price,
        "action": action, "score": score, "confidence": confidence,
        "rsi": rsi, "reasons": "; ".join(reasons)
    }

def get_crypto(symbol):
    r = requests.get(BINANCE, params={"symbol": symbol, "interval": "1h", "limit": 120}, timeout=20)
    r.raise_for_status()
    rows = r.json()
    df = pd.DataFrame(rows, columns=["open_time","open","high","low","close","volume","close_time","quote_volume","trades","taker_base","taker_quote","ignore"])
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def get_stock(symbol):
    raw = yf.download(symbol, period="60d", interval="1h", progress=False, auto_adjust=True, threads=False)
    if raw is None or raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = raw.rename(columns={"Close":"close","Volume":"volume"})
    return df[["close","volume"]].dropna()

def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY, ts TEXT, symbol TEXT, market TEXT,
            action TEXT, score INTEGER, price REAL, confidence INTEGER,
            UNIQUE(symbol, market, action, score)
        )""")

def notify_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": message}, timeout=20).raise_for_status()

def notify_email(subject, body):
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_APP_PASSWORD")
    recipient = os.getenv("EMAIL_TO")
    if not all([user, password, recipient]):
        return
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, recipient
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)

def main():
    init_db()
    results = []
    errors = []
    for symbol in STOCKS:
        try:
            item = assess(symbol, "DIONICE / ETF", get_stock(symbol))
            if item: results.append(item)
        except Exception as e:
            errors.append(f"{symbol}: {e}")
    for symbol in CRYPTOS:
        try:
            item = assess(symbol, "KRIPTO", get_crypto(symbol))
            if item: results.append(item)
        except Exception as e:
            errors.append(f"{symbol}: {e}")

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    lines = [f"AI INVESTMENT BOT — {now}", "Satni pregled; signali su informativni, ne nalog za trgovanje.", ""]
    new_signals = []
    with sqlite3.connect(DB) as con:
        for x in results:
            lines.append(f"{x['market']} | {x['symbol']} | {x['action']} | cijena {x['price']:.6g} | score {x['score']} | RSI {x['rsi']:.1f}")
            lines.append(f"  Razlozi: {x['reasons']}")
            exists = con.execute("SELECT 1 FROM signals WHERE symbol=? AND market=? AND action=? AND score=?",
                                 (x["symbol"], x["market"], x["action"], x["score"])).fetchone()
            if not exists and x["action"] != "HOLD":
                new_signals.append(x)
            con.execute("INSERT OR IGNORE INTO signals(ts,symbol,market,action,score,price,confidence) VALUES(?,?,?,?,?,?,?)",
                        (now, x["symbol"], x["market"], x["action"], x["score"], x["price"], x["confidence"]))
    if errors:
        lines += ["", "GREŠKE / NEDOSTUPNI PODACI:"] + errors
    report = "\n".join(lines)
    print(report)

    # Send the full hourly report by email; Telegram only sends new non-HOLD signals.
    try:
        notify_email("AI Investment Bot — satni izvještaj", report)
    except Exception as e:
        print("Email slanje nije uspjelo:", e)
    if new_signals:
        msg = "NOVI INVESTICIJSKI SIGNALI\n" + "\n".join(
            f"{x['symbol']} ({x['market']}): {x['action']} | cijena {x['price']:.6g} | score {x['score']}\n{x['reasons']}"
            for x in new_signals
        )
        try:
            notify_telegram(msg)
        except Exception as e:
            print("Telegram slanje nije uspjelo:", e)

if __name__ == "__main__":
    main()
