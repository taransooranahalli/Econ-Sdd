# Personal Alpaca data setup

Finance's Stocks workspace is at http://127.0.0.1:8004/stocks (Investments → Stocks). **Try synthetic example** works immediately without an account or external requests. DEMO-A is fictional. Real search, prices and history require the steps below.

1. Create a local Finance account from Sign in. This account owns the provider profile; other local accounts cannot use its feed.
2. Create your own Alpaca account with paper access, using the provider's site. Review its current agreement and confirm your access permits personal local display. Finance does not create the provider account, accept terms, fund it or place any order. Account availability and permissions depend on Alpaca.
3. Generate **paper** API keys through Alpaca. Keep both the key and secret private. Do not send them through chat or add them to source control.
4. Run this in your own interactive terminal, replacing the username with your existing Finance username:

   ```sh
   cd /Users/saint/Econ-Sdd
   .venv/bin/python -m econ_sdd.market setup --username YOUR_FINANCE_USERNAME
   ```

   The command asks for confirmation of personal display access and prompts for keys with hidden input. It resolves the local username to its stable account UUID. It writes a mode-0600 profile beside the app keyring, in the ignored private directory. It makes no provider requests and does not verify credentials yet. It refuses piped/noninteractive input and implicit replacement. Use `--replace` only when deliberately replacing this profile.
5. Stop the running app with Ctrl-C in its terminal, then start `.venv/bin/python -m econ_sdd` or open `Start Econ.command`. Sign in, open Stocks, search a ticker/company, and choose a listing. This checks the actual catalog and data permissions.

## What the integration requests

Only HTTPS GET requests to fixed Alpaca hosts are implemented: market-data latest trades and historical daily bars, plus paper-host asset metadata and the U.S. market calendar. All price requests explicitly specify **IEX** and **USD**. Alpaca's current [Basic plan](https://docs.alpaca.markets/us/docs/about-market-data-api) documents free limited-venue IEX access. No paid upgrade, trading/account-balance endpoint, arbitrary provider URL, browser key or public live feed is implemented.

Provider requests reveal selected symbols, request timing and the server IP. They do not include Finance account passwords, portfolio names, financial holdings, cash or cost basis. Retrieved data stays in bounded temporary server memory; restarting clears it. No live-price download/export or disk snapshot is provided in this slice. The private API profile is protected by local filesystem permissions; the app's financial saved plans retain their existing authenticated encryption.

## Read the labels

- **Live IEX feed · limited exchange coverage:** recent eligible trade during the supported open regular session. The screen polls every 15 seconds; this is not consolidated pricing or a tick-by-tick feed.
- **No recent IEX trade:** the most recent IEX event is too old for the live badge. Trading elsewhere may continue.
- **Market closed / last observation:** retain its observation time. Weekends, holidays and early closes use Alpaca's calendar, not weekday guesses.
- **Daily close:** latest required completed session before the current New York day, explicitly labeled provider IEX close. Same-day closes remain pending until the next New York day in this conservative first version. No silent carry-forward when a required close is absent.
- **History:** split-adjusted daily IEX closing prices, excluding current-day bars. Missing sessions remain visible, with gaps in the line. It excludes dividend income and is not total return.
- **Day change unavailable:** a verified comparable previous-close share basis is not established yet. It is never manufactured from incompatible prices.

If Alpaca rejects access, check paper keys/permissions locally and restart Finance. A 429 response pauses requests; respect its wait time. No automatic paid fallback occurs. Real-provider verification is pending until the user completes setup; passing synthetic tests does not establish real-feed access, complete instrument subtype coverage or redistribution rights. Public GitHub Pages stays a synthetic project showcase. Prediction statistics and any future public investment-guidance feature require their own review.
