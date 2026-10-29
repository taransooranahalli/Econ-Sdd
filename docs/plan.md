# Implementation plan

Status: calculators complete on 2026-10-27; accounts and encrypted SQLite saved plans verified on 2026-10-28. Complete-month date handling approved by the user.

| Milestone | Status | Dependencies | Acceptance checks |
| --- | --- | --- | --- |
| M0: Project scaffold | Complete | Requested project location | AGENTS.md and five docs files exist |
| M1: Savings specification | Complete | User selected savings and Python | Product criteria, math conventions/examples, schema/privacy, architecture, and plan cross-reference consistently |
| G1: Specification approval | Complete | M1 | Confirm or revise proposed effective-rate convention, monthly timing, USD with currency minor-unit precision, omitted taxes/fees/inflation, local runtime, Studio UI and Python backend, and download-based saving |
| M2: Pure savings engine | Complete | G1; verify Python/tooling | SAV-AC-01/02; isolated domain types; independent references, edge cases, mathematical properties, documented tolerances; unit suite passes |
| M3: Local savings UI | Complete | M2 | SAV-AC-03/04/05/07/08; summary, assumptions, sample state, schedule/chart; HTTP integration and UI state coverage; verify loopback/telemetry and inspect browser layout |
| M4: Save/load/export and release review | Complete | M3 | SAV-AC-06 and all remaining criteria; JSON round-trip/version validation, CSV parity, privacy checks, full relevant suite, run instructions, and limitations |
| M5: Savings goal | Complete | M4; approved complete-month convention | GOAL-AC-01..05; independent inverse values/minimality, dates, compatible files, API and responsive Studio UI |
| M6: Monthly cash flow | Complete | User selected monthly income and expenses | CF-AC-01..06; exact signed totals, ratios, categories, files and request guards, navigation and responsive UI |
| M10A: Stocks/API | Specification draft only | [Free live-preferred scope and provider capability gate](stock-portfolio-spec.md) | STK-AC-01/02; no integration claims until real access checked |
| M10B/C: Holdings and allocation | Specification draft only | Reviewed financial/data contract; M10A | PORT-AC-01..06; independent math, encrypted definitions, Studio UI and later implementation evidence |
| M9: Investment growth | Complete locally in 0.5.0 | User requested investments with spec-first workflow; [approved contract](investment-spec.md) | INV-AC-01..06; independent math, fees/inflation, Studio UI, files/encrypted plans, browser and regression verification before push |

## Current verification

During specification preparation, independently checked synthetic worked examples using high-precision Decimal calculations, separate individual-cash-flow sums, and exact Fraction arithmetic. These checks validate documented examples, not an unbuilt application. M2: 86 unit tests passed, covering independent cash-flow references, exact rational timing/rounding ties, published examples, seeded properties, domain bounds, currencies, invalid inputs, and isolated Decimal context. Syntax checks passed. Currency minor digits were verified against official SIX List One. M3/M4: 44 integration tests passed (130 tests total). API tests cover JSON/CSV round-trip, tampered-result recomputation, file-size and version guards, currencies, field errors, same-origin/CSRF/Host boundaries, privacy labels, and static asset contracts. JavaScript syntax, Python compilation, and pip dependency checks passed. No performance benchmark has run. No forecasting or trading results exist.

## Milestone completion protocol

Identify criteria; update specs before changing assumptions; implement only the current slice; run required checks; review against criteria; record changes, verification/failures, uncertainty, limitations, and next steps. Do not mark a milestone complete merely because code exists. Command definitions live in [AGENTS.md](../AGENTS.md).

## Unresolved topics and deferred dependencies

USD/currency selection is approved. Country-specific taxes, data-provider budgets, options experience, and access across devices remain deferred; none is required for the approved local savings release. Future native code follows profiling; future forecasting follows a separate approved experiment specification and measured unseen-data evaluation. Hosting and paid services require separate authorization.

## Browser review and release notes

Reviewed the actual Python-backed application on 2026-10-27:

- Initial empty state and manual input labels; explicit sample loading/provenance.
- Independent $1,000 + $100/month, 5% annual-effective, 12-month result: $2,277.26.
- USD/EUR denomination change with no FX conversion; JPY fractional-deposit validation; prior result retains its currency and exports disable while stale.
- Monthly schedule and growth-chart views; zero-month Enter-key calculation produces the initial balance and no invalid chart coordinates.
- Desktop viewport 1440px: approved Studio styling and all main regions inspected. Phone viewport 390px: 375px content area with 375px scroll width; no document-wide horizontal overflow. Screenshots retained with the chat outputs.
- Browser console reported no warnings/errors during these checks. All assets are local; API/asset tests assert no external runtime resource URLs.

Verification limits: native browser file-picker/save-dialog behavior was not separately automated. JSON import/export and CSV behavior were verified through HTTP and serialization integration tests. No exhaustive assistive-technology audit, cross-browser compatibility matrix, packaging test on another OS, or fresh-environment installation was performed. None is represented as completed. The app is local-only and has not been deployed.

Tested runtime: Python 3.12.14. Exact installed package versions are pinned in requirements.lock; README.md describes setup, use, assumptions, and privacy. Start Econ.command is a convenience launcher for macOS.

Next work follows user feedback on the working calculator; multi-scenario comparisons, accounts, options, forecasting, and native acceleration remain deferred.

## M5: Savings goal

Status: Complete. [GOAL-AC-01..05](goal-spec.md#ui-and-acceptance-criteria) implemented in release 0.2.0 with no additional dependencies. The independent Python solver finds the minimum currency-unit monthly deposit using the unchanged forward engine. Goal JSON/CSV persist dates and conventions; imports recompute results; savings-v1 compatibility remains covered.

Verification: 194 tests passed (130 existing plus 41 goal unit and 23 goal integration tests). Independent 100-digit cash-flow and exact Fraction references verify $154.92 and currency/timing rounding examples. Tests cover contribution minimality, negative/zero/tiny rates, clipped/leap dates, zero and 1,200 periods, limits, tampered exports, request guards, and privacy. Python compilation, JavaScript syntax, and installed dependency checks passed. The final HTML/CSS adjustment also passed the static element-ID contract and JavaScript syntax check.

Browser review used synthetic inputs in a separate temporary service. Confirmed $154.92 monthly for the two-year $5,000 example, dated schedule, the Jan 31 to Mar 30 one-period cutoff, keyboard submission and invalid-date feedback, sample labels, and stale-result warnings with disabled exports. Inspected 1440px desktop and 390px phone views; phone document width equaled scroll width (390px). No browser warning/error logs were observed. Screenshots retained in chat outputs. The user's existing port-8000 tab was preserved. Session permissions prevented stopping its older process, so the verified 0.2.0 app is running separately at http://127.0.0.1:8001/. Browser opening was queued in Codex. The default launcher still uses port 8000; stop the older instance before reusing that port.

Limits: native file-picker/save dialogs, exhaustive assistive-technology testing, cross-browser coverage, fresh-environment installation, and performance benchmarks were not performed. JSON/CSV behavior was verified through HTTP/serialization tests. Local-only operation and unchanged external-asset/request guards remain tested. No forecast, account connection, or transfer was added.

## M6: Monthly cash flow

Status: Complete in release 0.3.0; [CF-AC-01..06](cash-flow-spec.md#ui-and-acceptance-criteria) implemented. User selected monthly income and expenses on 2026-10-27. Separate pure Python arithmetic, guarded API/file adapters and Studio page preserve savings/goal behavior. No new dependencies or deployment.

Verification: 258 tests passed (194 previous plus 46 cash flow unit and 18 cash flow integration tests). Exact integer-minor-unit and Fraction references, seeded reordering/equal-flow/unit-step invariants, negative/zero results, null denominators, currency precision, range/row/schema validation, global Decimal-context isolation, maximum file round trips, model guards, safe CSV text and request/privacy boundaries passed. Python compilation, both JavaScript syntax checks, and dependency consistency passed. An initial test helper accidentally intercepted malformed-list input; corrected it to test the raw budget mapping. Distinct test filenames resolve pytest's default module-name collision. Neither issue required model changes.

Browser review on the actual updated port-8001 service: empty and sample states; $4,500 income minus $3,000 expenses equals $1,500 surplus; keyboard submission; negative cash flow; zero-income undefined ratio; field-specific required/JPY precision errors; currency edits retain numbers while old results retain denomination; add/remove rows; sample-derived labels; stale warnings and disabled exports. JSON download and file-chooser reimport restored original inputs and recomputed the net; CSV download completed. Inspected 1440px desktop and 390px phone views with no horizontal document overflow (phone width/scroll width both 390). Phone navigation reached Savings, verified its $154.92 goal example, and returned to Cash flow. Browser warning/error logs were empty. Screenshots retained in chat outputs.

Runtime: successfully restarted the owned service at http://127.0.0.1:8001/ and verified version 0.3.0, cash-flow-v1 configuration and the /cash-flow page. Cash flow is left open in a new deliverable tab; prior user tab was not navigated or reloaded. Older port-8000 service was not touched.

Limits: no exhaustive accessibility/assistive-technology audit, cross-browser matrix, fresh-environment install or performance benchmark. Native download/file-chooser behavior was exercised in this browser only. The calculator uses monthly totals; daily cash timing, frequency conversion, account feeds, allocations, forecasts and transfers remain outside this milestone.

## M7: Accounts and encrypted saved plans

Status: Complete locally in 0.4.0. [AUTH-AC-01..06](account-spec.md#acceptance-criteria) implemented: SQLite users/sessions/plans, Argon2id passwords, one-time recovery, session-bound mutation CSRF, owner-scoped encrypted original inputs, revision checks and the Studio account/library controls. Main account database is initialized empty; all test identities use temporary stores.

Verification: 333 tests passed (258 calculator regressions plus 42 account/store unit and 33 account/API integration cases). Covered independent ciphertext nonce/context checks, raw-database plaintext absence, password hash parameters/rehash, credential validation, session rotation/revocation/idle/absolute expiry, two-user CRUD isolation, concurrent edit and recovery races, one-use recovery, plan/session quotas, persistent attempt limits, request/Host/origin/content/body guards, production-style HTTPS cookie settings, tampered ciphertext, missing/wrong keys, private permissions, unsupported schema/model versions, backup-copy restore and interrupted key rotation. Python compilation, all three JavaScript syntax checks and dependency consistency passed. Installed cryptography/argon2-cffi and transitive versions are pinned in requirements.lock.

Browser review used synthetic identities in a separate temporary SQLite preview. In Dia: signed in, calculated cash flow, saved an encrypted budget, edited an expense and confirmed account/file saves disabled while stale, then reopened the saved inputs and fresh $1,500 result through the library. At phone width 390 in the in-app QA browser: keyboard sign-in, goal example $154.92, named save, library navigation, reopening and renaming/updating, then sign-out. No document overflow (client width equaled scroll width, 375px content inside the requested viewport). Desktop library and phone screenshots retained in chat outputs. Browser password change/recovery were not automated; those flows are covered through store/HTTP tests. No independent penetration test, exhaustive accessibility audit, cross-browser matrix, public deployment, or production backup operation is claimed.

Corrections during verification: the initial Unicode-header test needed raw HTTP bytes, and the static-ID regex needed a word boundary; these were test harness issues. Runtime database connections now refuse to recreate a missing database, and anonymous inputs remain intact on account-service lookup errors. The UI prompt for signed-in account saves was corrected.

Runtime/handoff: initialize with `python -m econ_sdd.accounts init`, then launch on port 8001. The user requested Dia plus VS Code; Econ-Sdd was opened in a separate VS Code window, and the account page is handed off in Dia. See README for key/backup/rotation instructions and docs/project-map.md for scaffolding. Public hosting still requires a separate reviewed deployment.

## M8: Public repository and Pages showcase

Status: Published on 2026-10-28. [PUB-AC-01..06](publication-spec.md#pub-ac-01-06) implemented. Public repository: https://github.com/taransooranahalli/Econ-Sdd. Project showcase: https://taransooranahalli.github.io/Econ-Sdd/. The user's existing homepage and other repositories were not replaced. Backend hosting remains deferred by the user's selection.

The public snapshot contains reviewed source, specifications, traceability, roadmap, issue/PR templates, pinned dependencies, synthetic screenshots and an allowlisted static builder. GitHub initialized the repository with a README seed; the following application commit is the reviewed local snapshot. Earlier local development is documented without backdating Git history. Commits use the verified owner's GitHub no-reply address. The local database/keyring, sessions, downloads, caches and virtual environment are absent from the Git snapshot and Pages artifact.

Verification: 348 tests passed locally and in the first GitHub Actions run (333 application cases plus 15 publication cases). The Pages builder rejects failed JUnit evidence, unreviewed files and symlinks; its displayed count comes from the report. Staged/tracked-file checks passed for 74 reviewed files. JavaScript syntax, Python compilation, dependency consistency, local asset/document links and a fresh pinned install on the GitHub Ubuntu runner passed. Workflow actions are pinned to verified official release commit SHAs; PRs verify/build without publishing, and only main deploys with Pages/OIDC permissions.

Browser review: inspected the complete desktop showcase at 1440px and phone layout at 390px; tab click and arrow-key selection showed the correct savings/cash flow panels. A background pseudo-element initially caused 8px phone overflow; corrected the mobile inset and confirmed document client/scroll widths both 375px inside the phone viewport. No browser warning/error logs were observed. Site copy labels precomputed synthetic previews and separates implemented local features from planned investments/prediction-market research. No live account forms or financial inputs are collected on Pages. Screenshots retained with chat outputs.

The first workflow run completed verify-and-build and publish successfully: https://github.com/taransooranahalli/Econ-Sdd/actions/runs/40645018689. Public site availability and assets are checked after deployment. Future changes flow through the same tests/build/deploy pipeline. No paid service, live account backend, independent security audit or exhaustive browser/accessibility matrix was introduced.

## M9: Investment growth

Status: Complete locally in 0.5.0 on 2026-10-28. User selected investment growth first after reviewing the specification, with portfolio allocation/rebalancing and holdings/historical-return analysis explicitly deferred to later milestones. [INV-AC-01..06](investment-spec.md#numbered-acceptance-criteria) implemented using independent Python Decimal math, existing Studio design/currencies, versioned JSON/CSV and encrypted original-input plans. No new dependency or SQL schema migration.

Verification: **415 tests passed** (348 prior checks, 46 investment unit cases, 18 investment file/API/privacy cases and 3 additional account cases). Independent exact Fraction cash-flow and fee sums check the $2,374.53/$19.61/$20.55 fixture; independent 110-digit sums cover non-rational, tiny, negative and extreme rates. Covered accounting, timing, zero periods, maximum bounds, zero-fee savings parity, fee monotonicity, inflation isolation, Decimal context, currency precision/half-even ties, complete-file size and tampered-total recomputation, HTTP guards, private logging, encrypted saves/restart, two-user isolation and revision conflicts. Python compilation, all app/showcase JavaScript syntax checks, dependency consistency and whitespace checks passed. Static showcase builds from the actual passing JUnit report.

Browser review used a synthetic account in a separate temporary SQLite service. At desktop 1440px and phone 390px, inspected accepted styling, assumptions, synthetic sample, negative-return loss, keyboard form submission and schedule tabs, JPY fractional-input errors, retained currency/old-result denomination, stale file/account-save disabling, JSON download/file-chooser reimport, encrypted save, library reopen/recalculation and rename/update. Desktop client/scroll widths both 1425px; phone both 375px inside the requested viewport. Warning/error log check returned no entries. Screenshots retained with the chat outputs. CSV parity/metadata/safety were verified through HTTP tests; native CSV save-dialog behavior was not separately verified. No exhaustive accessibility audit, cross-browser matrix, independent security audit or performance benchmark.

Corrections found by boundary tests: long-horizon deflation can require more than 80 integer display digits, so currency quantization now allocates sufficient presentation precision without changing calculation precision. Tiny valid rate inputs now serialize in fixed-point notation, ensuring they can be reopened under the strict no-exponent input contract. Maximum synthetic records remain within the 1 MiB import cap.

Runtime: updated local app is loopback-only at http://127.0.0.1:8004/investments and is open in a separate Dia tab with the labeled example. The older port-8001 service could not be stopped through this session's process permissions; its tab was preserved. Real account records/keys were not used for testing. Public Pages remains an allowlisted static showcase with only synthetic precomputed content; sign-in and live calculations stay local.

Static showcase review: the new precomputed investment tab and screenshot were inspected at desktop and phone widths. Adding the fourth tab initially caused phone overflow; wrapping the tab bar into two columns fixed it (phone client/scroll widths both 375px). The public build remains a fixed allowlist of 11 source assets plus .nojekyll. Temporary QA services were stopped and their synthetic account store removed.

## Investment workflow UI refinement — 2026-10-28

User requested Investments before Saved plans and the Savings-style deposit timing buttons. Updated the UI contract before implementation, reordered all five sidebar templates (phone order already matched), and replaced the investment select with the existing Month end / Month start segmented controls. The original beginning/end model and saved-file contract are unchanged. Button state synchronizes on input loading, sample loading and clearing; choosing timing invalidates prior results and save/export actions.

Verification: 415 tests passed; JavaScript syntax, Python compilation and whitespace checks passed. Browser checks covered desktop 1440px and phone 390px, keyboard Month start selection, stale/export disabling, recalculation ($53,205.06 for the synthetic month-start example), reset to Month end, sample loading, and JSON reopening with Month start visibly selected. Phone client/scroll widths both 390px. Updated the public synthetic screenshot. Existing account/API regression checks pass; account sign-in/CRUD was not repeated manually for this presentation change.

## Pre-market-data verification — 2026-10-29

Completed in 0.5.1: [verification record](verification-2026-10-29.md). Restored the stopped local app, aligned CLI/macOS startup to port 8004, fixed canonical tiny-rate exports and bounded legacy plan/file reopening, and unified package/app version metadata. 425 tests passed, plus launcher, live route/reference checks, and synthetic browser sign-in/save/reopen for all four calculator types. The record distinguishes automated/manual checks and remaining limits. Stocks, real-data APIs, portfolio construction and bank connections were not implemented.

## Stock and portfolio specification — 2026-10-29

Drafted [stock/portfolio contract](stock-portfolio-spec.md) and [official-source API review](market-data-api-review.md). User selected free access, preferably live, otherwise daily closes; bank linking stays deferred. Proposed Alpaca Basic/IEX live coverage is explicitly single-venue, with a whole-valuation EOD fallback and actual entitlement/display/retention gates. Draft includes manual holdings, budget/weight allocation, Decimal/bounds, freshness/partial-data states, identity/corporate actions, encrypted definitions, Studio journeys and numbered acceptance criteria.

Preparation checked worked examples with exact Fraction arithmetic and independent allocation-conservation calculations. These are specification references, not implementation tests. Only documentation changed; no stock API calls, keys, provider accounts, application code, dependencies or existing calculator/account behavior changed. New financial/default/provider choices remain draft pending review.

## M10A Stocks implementation — 2026-10-29

The user authorized Alpaca free live IEX Stocks with the accepted Finance UI; portfolios/predictions remain later. Local Stocks UI, read-only adapter, authenticated owner profile, setup command, source/freshness/calendar/history states and fictional preview are implemented in 0.6.0. **506 tests pass** plus syntax/dependency/build checks and desktop/phone/synthetic account browser review. [Verification and limits](stocks-verification-2026-10-29.md). STK-AC-01 remains pending actual account/key setup and live capability/display checks; the user has no Alpaca account yet. No real-provider result is claimed. [Personal setup](alpaca-setup.md).
