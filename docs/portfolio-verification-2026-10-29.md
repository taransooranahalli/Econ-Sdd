# M10B manual portfolio verification — 2026-10-29

Finance 0.7.0 implements manual holdings valuation with the accepted Studio UI, the existing Alpaca profile and encrypted saved-plan library. Allocation planning, transaction/return history, predictions, bank/account synchronization and trading remain later work.

## Implemented contract

[PORT-M01 and M10B details](stock-portfolio-spec.md#m10b-implementation-contract--authorized-2026-10-29) define the input bounds, equations, precision, source/date rules and privacy boundaries. Holdings × unrounded source prices plus cash produces portfolio value; weights include cash. Optional total entered cost supports signed unrealized gain/loss, with unknown cost distinct from zero. No complete total/portfolio-wide weights for missing prices or an unconfirmed/mismatched share basis. Complete aged prices carry a last-observed label; daily closes share one raw IEX session date. No chart-adjusted prices or automatic corporate-action accounting.

Price captures are temporary, owner/session-bound, revision/hash-bound and expiring. The server owns observed prices; browser inputs cannot supply them. Live checks can announce new observations while preserving the displayed captured valuation and all edited inputs. Saved/imported definitions reopen unpriced with no automatic provider call. Local JSON exports omit prices/results and explicitly warn that the financial definition is unencrypted. Existing account encryption, revision checks and quotas apply without a database schema migration.

## Automated verification

**580 tests passed** (509 prior + 71 portfolio checks). New unit checks use exact Fraction references and an independent 110-digit ratio calculation, plus explicit half-even display ties, Decimal context isolation, signed gain, missing/zero cost, cash-only/empty portfolios, missing prices, date/share-basis review, source/adjustment guards and bounds/duplicates.

Capture/adapter/API checks cover one IEX/USD batch, no private financial inputs sent to the provider, missing/invalid/old quotes, changed listings, capture ownership/session/revision/hash/expiry/bounds, freshness reclassification and market close, CSRF/origin/JSON/size/duplicate-key guards, two-user isolation, encrypted persistence and restart, offline reopen without provider traffic, revision conflicts, the shared 100-plan quota, definition-only export/import and ignored forged totals. All fixtures, credentials and account databases are synthetic/temporary. No real saved records were inspected or modified for QA.

Python compilation, JavaScript syntax, dependency consistency, whitespace and showcase-build checks accompany the release. No new dependency was added. Package/app version is 0.7.0.

## Browser verification

Used a disposable loopback server/account and fictional provider transport, with a visible synthetic-server banner. Verified:

- Fictional DEMO-A/DEMO-B reference: $2,000.00 total, $1,584.20 securities, $415.80 cash, $124.20 aggregate gain and 63.21% / 16.00% / 20.79% weights.
- Editing a quantity preserves the previous total, marks it out of date and clears share confirmation. Explicit confirmation/revaluation produces the independently checked $2,060.20 edited example.
- Manual symbol search, resolved listing addition, shares/cost/cash editing, review-needed subtotal, explicit confirmation, full valuation, daily-close mode, matching-date review, and keyboard Enter valuation.
- Account save, library listing and reopen as an unpriced definition; existing update/copy controls remain available.
- Browser JSON download completed. Parsed its exact file to confirm definition-only schema, unpriced status and omission of prices, totals, capture IDs and credentials. Browser-native reimport was not completed; its backend validation/round-trip/version/size/forged-result cases passed through API tests.
- Desktop 1440px viewport: document client/scroll widths both 1425px. Phone 390px viewport: both 375px. Native scrollbars explain the viewport/client difference. Editor/result stack and bounded table scrolling were inspected. No warning/error entries were observed. Screenshots remain with private chat outputs, outside the public asset allowlist.

Browser lifecycle/file-dialog operations were unusually slow/intermittent; functional checks and screenshots succeeded, while opening the final page in the app was queued. Temporary verification storage/server are cleaned up; the real local app remains running at http://127.0.0.1:8004/portfolios.

## Real-provider smoke check and limits

With the user's existing owner-bound profile, a read-only AAPL/SPY batch price capture and portfolio valuation succeeded using explicitly fictional quantities, no cost basis and no account save. The computed state was **last_observed** after market close. No credentials or raw responses were displayed/committed; no real holdings were requested. This verifies the provider-to-engine path, not the user's actual account positions or investment performance.

Open-session refresh/freshness behavior remains unobserved against the real feed. Corporate actions depend on the user's explicit share-basis/date confirmation; the app does not detect splits/mergers or verify brokerage quantities. Broader provider rights, redistribution/export of market observations, an independent security/accessibility audit, a cross-browser matrix, load benchmarks and fresh-environment installation remain outside this verification. Public Pages remains a synthetic showcase with no backend, keys or personal holdings.
