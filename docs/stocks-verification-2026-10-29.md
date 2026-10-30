# Stocks / Alpaca IEX implementation verification — 2026-10-29

Version 0.6.0 implements the authorized **M10A local Stocks slice**. **Real Alpaca account/feed capability verification remains pending**: the user has no Alpaca account/keys yet. No provider account, subscription, trade, bank link or prediction model was created. Portfolio construction remains the next implementation slice.

## Changes

- Investments → Growth / Stocks navigation, preserving the Finance Studio UI and sidebar order. Stock search, stable listing identity, latest eligible IEX trade, raw completed daily-close mode and split-adjusted daily IEX history (30/90/365 days).
- Explicit USD, provider/feed, trade/bar/session versus retrieval times, live/stale/no-trade/closed/missing/error states. Charts and tables show price-only history; missing bars remain missing. Day change is unavailable until comparable previous-close share basis is verified. Current-day bars are excluded; same-day close is pending until the next New York day.
- Fixed-host HTTPS GET transport for market data, assets and the pinned legacy U.S. calendar. No orders, balances, account/position sync, arbitrary URLs, key-bearing browser requests or automatic paid fallback.
- Signed-in owner and both CSRF boundaries before data requests. Bounded response sizes, normalization, pagination, request budget, in-memory caching, same-origin polling coordination, cooldown and credential-failure latch.
- User-operated local setup with hidden key prompts, existing account UUID binding, mode-0600 private profile and explicit replacement. No provider call during setup. [Instructions](alpaca-setup.md).
- Clearly fictional DEMO-A preview available without an account, keys or external request. No stock observation saving/export/public redistribution in this release.

## Automated verification

**506 tests passed** (425 prior + 81 market/setup/API checks), using temporary account databases, synthetic credentials and mocked transports only. No real user account/database contents, financial records, keys or live responses were used as test fixtures.

New checks include exact source-price preservation and half-even display, price and timestamp bounds, wrong feed/currency, unsupported/malformed listings, stable identity, zero/no/missing data, current-day/duplicate/impossible bars, DST/holiday/weekend/early-close calendar fixtures, original retrieval age, cache coalescing, pagination failure, rate/cooldown behavior, access-failure latch, owner isolation before network, request CSRF/origin/content/size/overposting guards, end-to-end search/detail/daily-close/logout, endpoint allowlist, verified-HTTPS construction, redirect refusal, transport timeout/error sanitization, JSON precision/duplicate/nonfinite/size guards, key redaction, private profile permissions and isolated setup-command behavior, including safe keyring-failure handling.

Python compilation, changed JavaScript syntax, installed dependency consistency, whitespace checks and static-showcase build passed. Runtime dependency truststore was already pinned in requirements.lock and is now declared in package metadata; package/app metadata agree at 0.6.0.

## Browser verification

Reviewed normal setup/anonymous and synthetic preview states, Finance branding, navigation, source labels, price chart and daily table. At 1440px desktop the document client and scroll widths both measured 1440px; at 390px phone they both measured 390px, including the expanded daily table. Keyboard Enter opened history details; all twelve fictional price rows appeared. No browser warning/error entries were observed in the reviewed tabs. Fresh reload testing found an early-click race on the example button; it now stays disabled until its event handlers are installed, and immediate reload/click was rechecked successfully.

A separate loopback QA service used a disposable account and mocked provider, with an explicit synthetic-server banner. Browser sign-in, keyboard symbol search, resolved listing selection, source/retrieval labels, old-observation labeling, daily-close switch, 90-day range keyboard selection and sign-out worked. The QA tab was closed, its server stopped and temporary account storage automatically cleaned. The actual local workspace remains at http://127.0.0.1:8004/stocks with setup pending. Screenshots are retained with chat outputs, outside the public asset allowlist.

## Limits and outstanding gate

- **STK-AC-01 remains pending:** user onboarding, actual paper-key access, representative stock/ETF catalog coverage and subtype gaps, real IEX timestamps/delays/history, actual entitlement/quota behavior and permitted local display/cache rights. Synthetic tests cannot prove these. No successful real integration is claimed.
- No independent security audit, exhaustive accessibility/cross-browser matrix, fresh-environment installation, concurrent-browser load benchmark or real-provider reliability measurement.
- Legacy calendar contract is bounded by its documented coverage through 2029; further coverage needs review. History and metadata caches are temporary and do not establish a provider retention/export license.
- No prediction accuracy, investment performance, recommendation suitability, regulatory status or liability waiver is asserted. Future modeling requires the user's statistics review; any public advice feature has a separate assessment.

## Follow-up: real-account endpoint smoke check — 2026-10-29 evening, America/Chicago

After the user configured paper keys and authorized restart/verification, the app loaded the owner-bound profile and successfully queried Alpaca's asset catalog. Initial search exposed a valid long instrument name beyond the original 200-character bound. Raised the bounded plain-text name limit to 512 without truncation, retained identity/control-character guards and added three fictional regression cases. **509 tests passed** after this correction; no real provider rows or credentials were added to fixtures.

Authenticated browser checks then succeeded for AAPL and SPY: resolved listing search, eligible IEX latest-trade access, completed daily-close mode and split-adjusted daily history. Each returned 22 observations in the selected 30-day range; SPY's one-year range returned 251 observations without a history error. Observation/retrieval times and IEX coverage remained visible. Both latest-trade views correctly showed **Market closed / last observation** during the evening check. Daily-close mode used the previous completed session and labeled the current day's close pending under the existing publication rule. Browser warning/error review returned no entries after correction. The actual page had equal client/scroll widths (628px) and was left open on SPY for the user.

This establishes working credentials and read-only endpoint access for representative stock/ETF listings. It does **not** verify open-session recency/polling, provider reliability under load, every instrument/subtype, rate-limit behavior against the actual account, export/redistribution rights or legal classification. Personal-display confirmation came from the user's local setup; no additional rights or public feed is asserted. No trading/account-position/banking endpoint was accessed. Keys were consumed by the adapter without being displayed. Raw provider responses were not saved to disk or committed; the private chat screenshot stays outside the public repository/Pages allowlist.
