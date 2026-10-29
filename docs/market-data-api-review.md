# Market-data API review — 2026-10-29

Status: specification research only. User selected **free tier**, preferably **live information**, with daily closing prices acceptable if free live data is unsuitable. No account was created, key supplied, entitlement tested, subscription purchased or API integration implemented.

## Proposed provider order

1. **Alpaca Basic as the live-data candidate**, using an explicit IEX feed. This provides limited-venue live observations, not consolidated U.S. quotes. Personal paper-only credentials are a documented route to data access; the app would use market data and narrowly allowed instrument metadata only. No bank funding, live brokerage connection, account-position reading, or paper/live orders are part of this application.
2. **Completed daily bars as the fallback**, preferably through the same provider if that account permits the required historical feed; otherwise review Massive Basic as a separate free EOD provider. Switching mode changes the entire valuation and its visible source label, never just one missing holding.
3. Do not build against a marketing claim alone. First prove the actual free account's data, timestamps, coverage, quotas and permitted local display/storage with a small read-only integration check.

This is an engineering recommendation for the prototype, not an executed provider selection or assurance of the user's eligibility.

## Comparison of official sources

| Candidate | Published free access observed on review date | Fit / limitation |
| --- | --- | --- |
| Alpaca Basic | U.S. stocks/ETFs, live IEX coverage; 30 streaming symbols; 200 historical requests/minute listed | Best documented candidate for limited-venue live information. API credentials/account required; SIP latest endpoints are not free, while older historical SIP queries have different eligibility. Explicitly request the feed instead of relying on the provider default. [Plan](https://docs.alpaca.markets/us/docs/about-market-data-api), [feed FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) |
| Massive Stocks Basic | $0, EOD, 5 calls/minute, two years of history; individual use | Clear EOD alternative, rather than a free live feed. Previous-day bars document Basic access and an explicit split-adjustment option. [Product/pricing](https://massive.com/stocks), [previous-day endpoint](https://massive.com/docs/rest/stocks/aggregates/previous-day-bar) |
| Twelve Data Basic | $0; 8 credits/minute and 800/day; advertised U.S. equity/ETF real-time access | Candidate remains conditional: the pricing page labels Basic internal non-display use, so a UI's display entitlement must be clarified. Credit weights vary by endpoint/symbol, and personal access does not establish public redistribution rights. [Pricing](https://twelvedata.com/pricing), [usage](https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage), [terms](https://twelvedata.com/terms) |
| Alpha Vantage standard free | 25 requests/day for most datasets; real-time and 15-minute-delayed U.S. data described as premium | Low default quota makes repeated portfolio refreshes a poor initial fit. No verified educational/open-source exception is assumed. [Support](https://www.alphavantage.co/support/) |

The Massive pricing page rendered incompletely in the research browser; the provider's product page and endpoint documentation supplied the cited limits. Twelve Data's top-level documentation exceeded the browser fetch limit; focused official support pages were used. Finnhub's pricing page exposed no readable plan details in this check, so no Finnhub pricing/coverage assertion or recommendation is made. No authenticated response was inspected for any candidate.

## Alpaca capability check required before implementation completion

- User reviews its own provider onboarding/terms and supplies credentials through local server configuration, never this chat or browser JavaScript. Paper-only access is documented in [Paper Trading](https://docs.alpaca.markets/us/v1.4.2/docs/paper-trading) and [data-access setup](https://alpaca.markets/learn/access-free-market-data); no funded account or trading integration is proposed.
- Prove symbol identification, exchange/type/currency handling, permitted search/catalog metadata, live `feed=iex`, and UTC trade timestamps for representative supported stock/ETF symbols. Day change additionally needs a comparable previous-close baseline.
- Use the [latest-trades endpoint](https://docs.alpaca.markets/us/reference/stocklatesttrades-1) as a candidate for the price observation. It filters trades for eligibility; it is not every last print or a consolidated bid/ask quote.
- Check exact REST limits and response handling. [Alpaca support](https://alpaca.markets/support/usage-limit-api-calls) describes account throttling and 429 responses. Our smaller local request budget is a project rule, not an increased entitlement.
- Verify completed historical bars with explicit feed, adjustment and timestamp parameters. The [historical-data guide](https://alpaca.markets/learn/fetch-historical-data) lists raw/split/dividend adjustment choices. A bar timestamp is not necessarily the time of its closing trade.
- Verify local display, temporary caching, normalized snapshot retention and personal export permissions against the actual account's current agreements. Public display/redistribution is a separate gate; the [terms](https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf) describe personal/non-commercial content use. This research is not a license grant.

If a capability or right cannot be established, expose it as unavailable and use the approved free EOD alternative where possible. Do not pay, scrape substitute prices, silently switch feeds or infer zero from an empty response.

## Implementation status — 2026-10-29

The user approved M10A with Alpaca free IEX. [Local adapter/UI and synthetic verification](stocks-verification-2026-10-29.md) are implemented. The user has no Alpaca account/keys yet; this does not complete the real capability, catalog subtype, timestamp/entitlement or display-rights checks above. [User-operated setup](alpaca-setup.md) is provided. No paid or public live-data activation occurred.
