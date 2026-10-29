# Stocks and portfolios — draft specification

Status: **draft for review**, 2026-10-29. The user requested this specification, the existing Studio UI, free API access with live information if feasible, daily-price fallback if needed, and bank linking deferred. This document proposes the first implementation contract; no stock/portfolio engine or provider connection has been built.

## 1. First milestone and decisions

Build three bounded slices: **stock discovery and prices**, **manual holdings portfolios**, and **budget/target-weight allocation plans**. Start with U.S.-listed equities and ETFs denominated in USD. This market/currency boundary is a proposed first-release assumption based on the user's response to the scope choices; international instruments/FX require their own extension.

| Topic | Contract / status |
| --- | --- |
| API cost | User selected $0 initial tier; no paid upgrade or overage authorization |
| Freshness | User prefers live information; accepts daily closing prices as fallback |
| Provider | Proposed Alpaca Basic / IEX for limited-venue live data; documented free EOD alternative if unsuitable. [Research and capability gates](market-data-api-review.md) |
| UI | Accepted Studio: dark surfaces, local Poppins, purple accents, assumptions and focused results |
| Inputs | Manual portfolio definitions and user-selected instruments; API prices/reference data |
| Saving | Existing authenticated, encrypted SQLite library; explicit saves only |
| Banking | Explicitly deferred; no credentials, bank data, transfers or account linking |
| Other non-goals | Trade execution, brokerage account/position sync, optimizer/recommendations, options, shorts/leverage, transaction/tax-lot accounting, historical portfolio performance, forecasts/ML |

An API price is an observation. A portfolio value combines observations and user-entered holdings. An allocation is an illustration under entered weights. None is a forecast, recommendation or executable order.

## 2. Journeys and Studio layout

Keep sidebar order **Savings → Cash flow → Investments → Saved plans**. Within Investments add a consistent **Growth / Stocks / Portfolios** navigation on desktop and phone. Preserve /investments for the existing growth tool; proposed new routes are /stocks and /portfolios. Saved plans remains the shared library.

**Stocks:** search a symbol/company, resolve its listing, inspect the latest eligible price and source/timestamp/coverage, view a labeled price-history chart and available day change, and add the resolved instrument to a portfolio. Search is explicit or debounced and bounded; it must not issue one provider request per keystroke. No company-logo requests or external UI assets are needed.

**Holdings:** name a portfolio, add shares and optional aggregate cost basis per instrument, enter cash, choose a pricing mode, then value it. Use the Studio input/result layout; put the holdings table below the summary when space requires it. Show total/known subtotal, holding weights, cash and available gain measures. Missing data must remain visible in the same table.

**Plan allocation:** enter an available budget and your own target percentages, select Whole shares / Fractional shares with Studio segmented buttons, and calculate illustrative quantities, notionals, actual resulting weights and unallocated budget. No automatic investment selection or rebalance orders.

Keep numeric labels, keyboard focus, clear errors, empty/loading/stale states, price-age labels, sample provenance, local JSON controls and explicit account saves. Never overwrite edited share quantities or weights when prices refresh. New price observations show **New prices available — Revalue**; the current valuation remains tied to its captured inputs and prices until the user revalues it.

**Currency:** source USD prices remain USD. On Stocks/Portfolios the currency control shows USD with an explanation that FX is not yet supported; it cannot reinterpret a USD quote as EUR/INR/etc. Existing hypothetical calculator selectors retain their accepted behavior unchanged.

## 3. Market-data modes, identity and freshness

### Live preference

Proposed source is the provider's latest eligible **IEX trade**, with an explicit IEX feed. Label it **Live IEX feed · limited exchange coverage**, show the trade time, fetch time and refresh cadence, and explain that it is not the consolidated market price or NBBO. Free live availability is a capability to verify, not a completed integration result.

Initial delivery uses server REST polling every **15 seconds**, only while the signed-in market-data view is visible and during the supported regular session. Batch selected symbols where supported. WebSockets are deferred; a live source does not imply tick-by-tick screen updates. Proposed active price universe: at most **20 distinct instruments** across the open stock/portfolio view.

Project freshness rules (not provider SLAs): a newly captured live valuation requires fetch age ≤30 seconds and each trade age ≤120 seconds, no more than 5 seconds of future clock skew, and a supported open regular session. Store the rules/configuration version. If an IEX trade is older, say **No recent IEX trade**; do not infer that the stock has stopped trading elsewhere. Outside the session show **Market closed / last observation**, not a fresh live value.

Live observations have different event times. A common fetch generation is not an atomic market snapshot. Show the earliest/latest included trade times and label the value indicative. A fully priced but aged bundle may be inspected as **Last observed value — contains older prices**; it cannot carry a current/live badge.

### EOD fallback

Offer a visible, whole-portfolio switch to **Daily close** when live entitlement, coverage or reliability is unsuitable. Prefer a supported completed historical feed from the chosen provider; Massive Basic is the researched separate-provider alternative. Do not silently mix a live IEX price, another provider and a daily close within one valuation.

Daily valuations require the **same completed session date, provider/feed and adjustment basis** for every holding. Display **Provider daily close for DATE**, not a live price or an asserted official exchange auction close. Bar-start timestamps are retained as such; do not invent an exact closing-trade time. Incomplete current-day bars are excluded. Awaiting publication, holiday, weekend and missing-data states must differ. An older common session is a user-visible historical selection, never a silent carry-forward.

Use a validated exchange calendar with timezone-aware America/New_York sessions, DST, holidays and early closes. Do not use weekdays or elapsed 24-hour age as the market calendar. The implementation must pin and validate its calendar source; [NYSE's schedule](https://www.nyse.com/markets/hours-calendars) is a primary check for NYSE sessions. Publication windows/coverage must be verified for the chosen feed rather than guessed.

### Instrument and observation contracts

Instrument identity includes an internal ID, provider identity, provider symbol/asset ID, listing venue, supported asset class and quote currency. Symbol/company text alone is not unique. Retain a provider's stable asset ID where supplied; aliases, ticker reuse, renames and delisting must not silently reassign a holding. Require explicit listing resolution for ambiguous input.

Only the reviewed U.S. equity/ETF universe is supported. Options, crypto, OTC and unverified listings are unavailable. Corporate/type/currency classification gaps remain explicit; never invent metadata. A provider price of 0, negative/nonfinite values, missing times, wrong feed/currency, malformed payload or an empty result does not become a usable price.

A normalized price record contains instrument ID, decimal-string price, USD, provider/feed, price_kind, adjustment basis, event timestamp or session date as appropriate, fetched_at_utc, market/session status, entitlement/delay label, validation status and cache age. Keep bar timestamps separate from event timestamps. In-memory source IDs/hash/retrieval parameters identify the capture without retaining a secret URL or credential.

## 4. Inputs, valuation and accounting

### STK-M01: change from previous close

A stock's optional day change uses the latest selected-mode price p and previous completed session close p0 from the same currency/feed and comparable split share basis: change=p−p0; percent_change=100(p−p0)/p0 when p0>0. If that baseline or its share basis is unavailable, show unavailable rather than comparing incompatible feeds or treating it as zero. It is a price change, excludes dividend income and is not the user's investment gain. A pending split/basis review suppresses this metric. Synthetic p0=$100 and p=$120.40 yield +$20.40 and +20.40%; Decimal presentation follows the policy below.

### Bounds and conventions

| Input | Proposed range / behavior |
| --- | --- |
| Name | 1–80 plain-text characters for named saves |
| Holdings | 0–20 unique resolved instruments; reject duplicates with an actionable message |
| Shares q_i | Decimal string, >0 to 1,000,000,000; up to 6 fractional places; no shorts |
| Cash C | USD decimal string, 0 to 1,000,000,000,000; ≤2 fractional places |
| Optional cost K_i | Total entered cost basis for the currently entered shares, same USD bounds/precision; missing is unknown, distinct from 0 |
| Quantity as-of | User-confirmed position basis/date for the valuation; not imported from a brokerage |
| Allocation budget B | USD decimal string, >0 to 1,000,000,000,000; ≤2 fractional places |
| Targets | 1–20 instruments plus optional cash; each percent 0–100 in 0.01-point increments; exactly 100% in integer basis points |
| Share quantum s | 1 for Whole shares (default), 0.000001 for Fractional; a modeling choice, not a broker capability assertion |
| Provider prices p_i | Finite positive Decimal, at most 24 fractional places and ≤1,000,000,000,000 as a defensive application bound; do not round to cents before calculation |

API strings and saved financial inputs use fixed-point notation and strict schema/version checks. Empty required values never become zero. Zero holdings with cash are allowed; zero holdings and zero cash form an empty portfolio with undefined weights. Limits are application constraints, not market or investment recommendations.

### PORT-M01: holdings value

For a complete captured price bundle:

- Holding value v_i = q_i × p_i.
- Securities value S = Σv_i; total portfolio value V = S + C.
- Holding weight w_i = 100v_i/V and cash weight w_cash = 100C/V when V>0; otherwise null, never NaN.
- Where K_i is supplied, unrealized gain g_i = v_i − K_i; gain percent = 100g_i/K_i only when K_i>0.
- Aggregate unrealized gain Σg_i is available only if **all** held positions have entered cost basis. Otherwise show known per-holding gains and missing-basis coverage; do not treat unknown cost as zero. Cash is excluded from the gain denominator. These are entered-cost comparisons, not verified tax gains or time-weighted/money-weighted portfolio returns.

Cost basis is user supplied and may include acquisition costs if the user includes them; no commissions, ongoing charges, taxes, dividends or cash interest are inferred. Prices are unadjusted observations on the relevant share basis. The UI explains that these values exclude future sale costs, spread/slippage and taxes.

A missing holding price means **no complete portfolio total or portfolio-wide weights**. Show priced-holding count and a clearly named known subtotal instead. An empty-price cash-only portfolio remains valid. Never substitute zero, silently drop a holding or combine incompatible dates/feeds.

### PORT-M02: budget allocation

Let b_i be entered target basis points, including b_cash, with Σb=10,000. For each security:

- Desired amount a_i = B × b_i/10,000.
- Illustrative shares q_i = floor(a_i/(p_i × s)) × s.
- Estimated notional n_i = q_i × p_i.
- Unallocated budget R = B − Σn_i, so R ≥ B × b_cash/10,000 and Σn_i + R = B exactly at working precision.
- Actual resulting weights are 100n_i/B and 100R/B; show their difference from entered target percentages.

Do not renormalize incorrect targets or spend leftover cash automatically. A stock too expensive for a positive whole-share allocation gets 0 shares and an explanation. Fractional quantities are estimates; brokerage minimums and broker-specific currency rounding are not modeled. R may contain fractional cents internally. Display it as **Unallocated budget estimate**, not an actual bank/cash balance. There is no claim that a plan can execute at these prices or within budget after trading costs. Saving an allocation does not create real holdings or place orders.

### Corporate actions and history

Manual quantities must match the price share basis and user-confirmed as-of date. If a split, merger, symbol change or other action makes that uncertain, mark the position **Needs quantity review** and withhold a current complete valuation until confirmed. Do not multiply current shares by a historically adjusted price. Do not auto-adjust shares/cash/basis or book dividends in this first version.

A stock history chart may show explicitly labeled split-adjusted daily price history when the feed/entitlement supports it, retaining its adjustment setting. It is **not total return**, and backcasting today's holdings over past prices is not historical portfolio performance. Dividend reinvestment, a transaction ledger, TWR/IRR and rebalancing existing holdings require later contracts.

### Precision and independently checked examples

Use isolated Python Decimal precision 80. Calculate from unrounded source prices; USD presentation uses half-even cents and displayed percentages use half-even two places. Share sizing rounds downward to s. Retain full working values; independently rounded rows can differ from a rounded total. Nonfinite/unreliable results are unavailable rather than fabricated.

Synthetic **DEMO-A/DEMO-B** are fictional fixtures, not real listings or fetched quotes:

| Holdings reference | Result |
| --- | --- |
| A: 10.5 shares × $120.40; entered cost $1,100 | Value $1,264.20; unrealized gain $164.20 |
| B: 4 shares × $80; entered cost $360 | Value $320.00; unrealized gain −$40.00 |
| Cash $415.80 | V=$2,000.00; A/B/cash weights 63.21% / 16.00% / 20.79%; aggregate unrealized gain $124.20 |

For B=$1,000 with targets A 60%, B 30%, cash 10%, the same fictional prices give:

| Share mode | A shares / notional | B shares / notional | Unallocated budget |
| --- | --- | --- | --- |
| Whole | 4 / $481.60 | 3 / $240.00 | $278.40 |
| Fractional 6 places | 4.983388 / 599.9999152 USD | 3.75 / 300 USD | 100.0000848 USD, displayed $100.00 |

Preparation verified these examples and exact conservation independently with Fraction arithmetic. This is reference checking, not a passing implementation test. Future mathematical tests compare exact rational references; for nonterminating ratios use an independent ≥100-digit reference and relative/absolute tolerance 1e−65, with separate exact presentation-tie checks.

## 5. Persistence, privacy and API boundary

Proposed models are portfolio-holdings-v1 and portfolio-allocation-v1, schema_version=1, with account kinds portfolio_holdings and portfolio_allocation. A holding definition stores resolved identity, shares, entered cost, cash, as-of confirmation and source provenance; an allocation stores identities, budget, targets and share quantum. Model/input bounds above are authoritative. Source prices are not accepted as authoritative just because a browser/import supplies them.

Save definitions explicitly to the existing owner-scoped AES-GCM SQLite library with revisions, quotas and unsupported-version rejection. Reopening works offline: restore validated definitions as **Unpriced — refresh from API**. It does not automatically call a provider or trust old totals. New portfolio kinds may save a valid unpriced definition; existing calculator save/stale behavior stays unchanged.

Price refresh and valuation use a server-owned capture ID bound to the signed-in owner/profile and input revision. Keep original financial definitions separate from market observations and derived totals. Persist normalized market snapshots or export market-price/result data **only after retention/export rights are established**; default is temporary memory caching and definition-only JSON. An export must say when source prices were intentionally omitted. Imported derived values are ignored. Existing 1 MiB JSON cap, duplicate-key rejection, no executable formats and formula-safe CSV text apply.

Data-backed features require authentication and an explicitly configured licensed owner/provider profile. For the first local instance, proposed credentials are server environment/secrets configuration bound to that owner; another app account cannot consume or view that profile's feed. Never put keys in browser code, Git, exported plans, console messages or logs. The current anonymous calculators continue working without a provider.

The provider receives the server's IP, requested symbols and request timing, not portfolio names, quantities, cash, cost basis, account credentials or saved-plan IDs. Cached price data is separate from private financial inputs. No user-entered financial values enter a shared cache.

Proposed backend routes: POST /api/market/search, /api/market/prices and /api/market/history; POST /api/portfolios/validate, /api/portfolios/value and /api/portfolios/allocate; existing /api/plans CRUD dispatches the new definition kinds. Provider-triggering reads use the existing same-origin JSON/process-CSRF and account-session boundaries. Backend Python owns all financial results; JavaScript only renders them and chart coordinates.

Use fixed HTTPS provider hosts, verified certificates, bounded responses/timeouts/pagination and normalized safe errors. Alpaca candidates are data.alpaca.markets read endpoints and, if required/confirmed for listing metadata, **GET /v2/assets only** on the paper host. No orders, positions, account balances, funding or trading client. Do not assume a credential is technically read-only; enforce the app's endpoint/method allowlist independently. Never follow arbitrary user URLs or unchecked provider pagination URLs.

Proposed traffic policy: ≤60 provider requests/minute for the instance, or the lower actual entitlement; coalesce duplicate symbol requests and share one polling scheduler across tabs. Credit-weighted providers must enforce endpoint/symbol credit costs as well as raw call counts. Refresh only selected data; stop on hidden/signed-out views. Honor Retry-After/429 and authentication/entitlement failures; bounded retry/backoff, no retry storm. Cache TTLs (subject to permitted retention) start at 10 seconds for live observations, 30 minutes for completed daily bars and 24 hours for reference metadata. TTL does not redefine the observation's market age.

## 6. Acceptance criteria

- **STK-AC-01 — Provider reality:** A read-only live-account capability check proves supported stock/ETF identity, explicit feed, timestamp/delay behavior, free-tier limits and applicable local display/storage/export rights. Live unavailable means an explained free EOD choice, not a paid upgrade or invented quote. No successful integration is claimed before credentials/entitlement testing.
- **STK-AC-02 — Data states:** Test ambiguity, unsupported/delisted symbols, no trade, zero/nonfinite prices, wrong currency/feed, future/old times, pagination, 401/403/429, timeout and provider errors. Calendar/session/DST/holiday/early-close cases and published versus incomplete daily bars have explicit outcomes. Source and age survive every render.
- **PORT-AC-01 — Valuation:** Independent references, zero/cash-only cases, missing price/basis, signed losses, duplicate holdings, amount/share bounds and Decimal isolation pass. Complete/aged/partial states never masquerade as one another; no full total for unpriced holdings.
- **PORT-AC-02 — Allocation:** Exact target sums, Whole/Fractional modes, downward sizing, zero-size expensive positions, cash target/residual and conservation pass. Equal inputs/captured prices give equal results; no recommendation, fill or return is implied.
- **PORT-AC-03 — Share basis:** Raw valuation versus chart adjustment is explicit. Corporate-action/quantity uncertainty blocks a current complete valuation. Charts do not claim dividend-inclusive return or historical performance of manually entered current holdings.
- **PORT-AC-04 — Private persistence:** Synthetic two-user save/update/reopen/restart/revision/quota tests pass; another account cannot access a portfolio or provider profile. Definitions reopen without network; imports recompute validation and ignore derived totals. Key/financial-data logging and arbitrary URL/order requests are absent.
- **PORT-AC-05 — Studio UX:** Browser review at 1440px and 390px covers navigation, keyboard use, source/coverage/currency labels, missing/stale/loading/error states, refresh while editing, definition saving/reopening and permitted exports. Existing growth timing buttons and all calculator UI contracts remain intact.
- **PORT-AC-06 — Release evidence:** New unit/adapter/API/account tests, full regression suite, Python/JS/dependency checks and browser evidence pass before an implementation release. Test synthetic transport fixtures separately from a user-authorized real-provider smoke test. Do not commit keys or retained live responses. Pages continues with fictional/precomputed data and no API key or account backend.

## 7. Delivery sequence and review gates

| Slice | Deliverable | Completion gate |
| --- | --- | --- |
| S1: Current work | Reviewed specification, API comparison, exact math examples and pending decisions | No runtime/provider changes; user reviews proposed financial/UI conventions |
| M10A | Provider adapter, stock search/detail and clear freshness states | STK-AC-01/02; user-approved free provider setup and verified access; initial Studio preview |
| M10B | Pure holdings valuation, manual portfolio editor and encrypted definitions | PORT-AC-01/03/04/05; API/network independent math and owner isolation |
| M10C | Budget/target allocation planner | PORT-AC-02/05/06; independent conservation/rounding and full release verification |
| Later | Transaction/return history, rebalancing, international FX, optional bank connectivity | Separate approved definitions, provider/privacy/cost contracts and migration as applicable |

Before implementation, confirm the proposed USD/U.S. scope, limited-venue live label, manual holdings plus allocation scope, and provider account/rights/capabilities. New costs, public data display and bank/trading access require separate authorization. The user's $0/live-preferred choices are settled; provider activation and all unbuilt behaviors remain reviewable proposals.
