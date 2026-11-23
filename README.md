# AI Investment Bot 1.0

Besplatan početni Python projekat za satno praćenje dionica/ETF-ova i kriptovaluta.

## Šta radi
- Kripto: Binance javni API, svijeće od 1 sata.
- Dionice/ETF: Yahoo Finance podaci preko `yfinance`, satni interval (samo tokom dostupnih trgovačkih sesija).
- Indikatori: RSI(14), MACD, EMA20/EMA50 i relativni volumen.
- Klasifikacija: BUY WATCH / SELL-AVOID / HOLD.
- SQLite evidencija signala.
- Email izvještaj i Telegram poruka za novi signal.
- GitHub Actions workflow pokreće provjeru približno svakog sata.

## Važna ograničenja
Ovo je početni sistem zasnovan na pravilima indikatora, a ne samostalni prediktivni AI model. Broj `confidence` je samo interni indikator jačine signala, nije statistički dokazana vjerovatnoća profita. Ne izvršava kupovinu/prodaju i ne daje garanciju zarade.
Besplatni izvori mogu kasniti, mijenjati dostupnost ili imati ograničenja. GitHub rasporedi nisu garantovano tačni u minutu; besplatni kvotni limiti i deaktivacija neaktivnih workflow-a mogu uticati na rad.

## Pokretanje lokalno
1. Instaliraj Python 3.11+.
2. `pip install -r requirements.txt`
3. Kopiraj `.env.example` u `.env` i postavi varijable okruženja (npr. preko terminala ili `.env` loadera koji sam dodaš).
4. Pokreni `python main.py`.

## GitHub Actions
1. Napravi privatni GitHub repository i postavi ove fajlove.
2. U Settings → Secrets and variables → Actions dodaj:
   `STOCK_SYMBOLS`, `CRYPTO_SYMBOLS`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SMTP_USER`, `SMTP_APP_PASSWORD`, `EMAIL_TO`.
3. U Actions omogući workflow.
4. `workflow_dispatch` omogućava ručno testiranje.

## Telegram podešavanje
1. U Telegramu otvori `@BotFather`, napravi bot i kopiraj token.
2. Otvori razgovor sa svojim botom i pošalji `/start`.
3. Dobavi svoj chat ID preko Telegram Bot API `getUpdates`, pa ga unesi u GitHub Secret.

## Gmail podešavanje
Koristi Google App Password ako je dostupan na tvom Google računu. Nikad ne šalji običnu Gmail lozinku i ne stavljaj tajne u kod.

## Sljedeća faza
Prije stvarnog korištenja dodati backtest, provjeru kvaliteta podataka, volatilnost/ATR za stop-loss, upravljanje rizikom i izvještaj o historijskoj uspješnosti. Prvo testirati u paper-trading režimu.
