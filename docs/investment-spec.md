# Investment growth — first milestone

Status: implemented and locally verified in 0.5.0, 2026-10-28. The user selected investment growth first after reviewing the draft, and requested portfolio allocation/rebalancing and holdings/historical-return analysis later. Preserve the Studio UI and implement INV-AC-01..06 below.

## Purpose and boundary

Explore how an initial investment and fixed monthly contributions could grow under a user-entered constant total return, portfolio fee and inflation assumption. This is a deterministic conditional projection. It does not estimate future returns or recommend investments. Returns may be negative and the projected balance may be below total contributions.

Use manual inputs and labeled synthetic examples. Treat the portfolio as one aggregate investment. The return includes reinvested dividends/distributions; there is no separate dividend yield to add. No instrument selection, prices, brokerage connections, historical performance, allocation, trading, tax calculation, withdrawals, stochastic intervals or ML in this milestone. Public hosting of accounts remains deferred.

## Inputs and conventions

| Input | Contract |
| --- | --- |
| Initial investment P | Required decimal string, 0 to 1,000,000,000,000, selected currency minor-unit precision |
| Monthly contribution C | Required decimal string, same bounds; fixed nominal amount; zero must be explicit |
| Gross annual effective total return R | Required decimal percent, −99 to 100, at most 24 decimal places; user assumption before the separately modeled fee |
| Duration n | Whole number of equal months, 0 to 1,200; no calendar or partial-month accrual |
| Contribution timing | End of month by default; beginning selectable |
| Annual portfolio fee F | Required decimal percent, 0 to 100, at most 24 decimal places; explicit 0 allowed; deducted monthly as F/12 percent of the post-return invested balance |
| Annual effective inflation H | Required decimal percent, −99 to 100, at most 24 decimal places; explicit 0 allowed; fixed assumption |
| Currency | USD default; EUR, GBP, CAD, AUD, INR, JPY and KWD; retain entered numbers on selection changes, no FX conversion |
| Provenance/name | Existing manual/sample, sample-derived and plain-text name conventions |

Begin with empty required financial fields. A sample is synthetic, carries a visible sample label, and supplies no recommended return. Any future convenience defaults must remain explicit and reviewable.

The fee is a simplified portfolio charge, not a reconstruction of a fund's daily expense-ratio accrual. Its annual label describes a nominal rate split into twelve deductions, not an effective annual reduction of exactly F percent. For example, 1.2% means a 0.1% deduction each month. Do not enter a fee again if it is already included in the supplied return. Tax treatment is before tax, with no jurisdiction or account type assumed.

## INV-M01: projection and cost accounting

Convert percent inputs to fractions r=R/100, f=F/100 and h=H/100. Let g=(1+r)^(1/12), a=f/12 and B_0=P. For month t=1..n:

1. X_t=B_(t−1)+C for beginning contributions, otherwise X_t=B_(t−1).
2. Gross investment gain L_t=X_t(g−1).
3. Modeled fee A_t=X_t*g*a.
4. B_t=X_t*g−A_t+C for end contributions; otherwise B_t=X_t*g−A_t.

Total contributions D_t=P+t*C. Cumulative deducted fees are sum(A_1..A_t). Net investment gain is B_t−D_t; gross gains sum(L_1..L_t), so B_t=D_t+sum(L)−sum(A). Preserve signed gains and losses.

Calculate a separate zero-fee counterfactual using exactly the same P, C, R, n and timing with F=0. Fee impact on ending value is B_without_fees−B_with_fees. This includes the changed compounding path and is distinct from the sum of fees deducted; do not label the difference as fees paid.

No periodic currency rounding inside the model. Use local Decimal precision 80, retain full working results, and round display/CSV half-even to currency minor units. Protect exact rational cases and real rounding ties. Finite results that cannot be computed safely are unavailable, with a useful error; never substitute zero or a stale balance.

## INV-M02: purchasing power

Ending balance in start-period purchasing power is B_n/(1+h)^(n/12). Label it as purchasing power at the start of the projection, in the selected currency. It is not an FX conversion or a prediction of an individual's cost of living. Keep total contributions and net gain explicitly nominal; do not subtract nominal deposits from a deflated balance and call that a real return.

At n=0, show P, no recurring contributions, no gains or fees and purchasing power P. Negative returns/deflation and zero amounts are valid within the bounds. No leverage or −100% loss case is supported in this version; disclose those limits.

## Independently checked numerical reference

Use an intentionally constructed arithmetic fixture, not a suggested market assumption: P=$1,000, C=$100 at month end, n=12, R=12.6825030131969720661201%, F=1.2%, H=12.6825030131969720661201%. Here g=1.01 exactly and the monthly after-fee factor q=1.00899 exactly.

An exact Fraction cash-flow sum P*q^12 + C*sum(q^k, k=0..11), independent of the monthly recurrence, gives:

| Output | USD, half-even display |
| --- | --- |
| Ending balance | $2,374.53 |
| Total contributions | $2,200.00 |
| Net investment gain | $174.53 |
| Cumulative deducted fees | $19.61 |
| Ending balance without modeled fee | $2,395.08 |
| Fee impact on ending value | $20.55 |
| Start-period purchasing power | $2,107.27 |

Implementation tests verify exact Fraction cash-flow and fee sums independently of the engine. Non-rational cases compare the implementation to an independent 110-digit cash-flow reference with relative tolerance 1e−65 (absolute tolerance 1e−65 near zero), and check the displayed minor units. Presentation ties use separate exact rational cases. See [milestone evidence](plan.md#m9-investment-growth) for performed checks and limits.

## Studio UI and user journey

Add Investments to the existing desktop sidebar and phone navigation, linking to /investments. Retain dark surfaces, local Poppins, purple accents, spacing, focus styling and the USD selector. Reuse the assumptions-form/result-panel layout without introducing a new design system.

Form: initial investment, monthly contribution, gross annual effective total return, duration, timing, fee and inflation. Keep fee convention, dividend reinvestment and no-FX explanations beside the relevant controls. Result: nominal ending balance and signed net gain, total contributions, fees deducted, fee impact and start-period purchasing power. A monthly chart compares after-fee balance, the zero-fee counterfactual and nominal contributions; no probability bands. The schedule exposes monthly gains, fee, contribution and closing balance, including month zero. Distinguish nominal chart values from the separate purchasing-power summary.

Retain empty/loading/error/stale states, field validation, keyboard submission, explicit sample provenance, accessible table/chart labels and disabled saves/exports until a valid current calculation exists. Show model version, calculation timestamp and all assumptions near results. No amount is entered or changed silently when switching currencies.

## Data, API and encrypted plans

Identifiers: model_version=investment-growth-v1, schema_version=1, calculation_mode=investment_growth, account kind=investment_growth, output_category=conditional_projection. Original fields: schema_version=1, calculation_mode=investment_growth, initial_balance, monthly_contribution, annual_return_percent, annual_fee_percent, annual_inflation_percent, duration_months, contribution_timing, currency, source, sample_derived, name. Money/rates are decimal strings; duration is an integer; provenance uses the existing boolean convention. The result input key is scenario. Reject unknown fields, duplicate JSON keys, unsupported versions, nonfinite values and incompatible precision. Calculation timestamps are not market-data timestamps.

Add a pure finance/investments.py model and serialization/investments.py adapter; reuse currency validation, server presentation and request guards without changing savings/goal/cash-flow math or formats. Routes: /investments; POST /api/investments; POST /api/investments/import; POST /api/investments/export/json and /csv. Extend config, account dispatch and saved-plan navigation deliberately.

JSON saves canonical original inputs plus versioned results/assumptions; imports recalculate and never trust supplied totals. CSV includes schedule, input assumptions, currency, provenance, model and calculation time; arbitrary names remain absent or safely neutralized. Existing 1 MiB request/import limits apply.

Signed-in users explicitly name/save/update/reopen investments through the current owner-scoped AES-GCM/SQLite library. Save only validated canonical original inputs and existing plan metadata; reopen recalculates. Retain ownership, session, CSRF, revision, quota and tamper checks. No database schema migration is expected because calculator payloads are encrypted generic records; confirm in tests. Anonymous calculations and unencrypted local downloads remain supported. No runtime database, key, account or private scenario goes into Git or the static showcase.

## Numbered acceptance criteria

- **INV-AC-01 — Inputs:** All input ranges, timing, currencies, provenance and invalid/missing-value behavior are enforced by Python; return, fee and inflation conventions are visible.
- **INV-AC-02 — Arithmetic:** Independent exact reference, beginning/end timing, signed loss, accounting identity, zero periods/rates/amounts, maximum bounds and Decimal context isolation pass. With F=0, balances match the existing savings engine under identical assumptions without altering that model.
- **INV-AC-03 — Costs and inflation:** Zero-fee counterfactual uses identical inputs except fee; fee drag and actual deducted fees have distinct labels. Increasing fee cannot increase the balance for these nonnegative cash flows. Inflation changes purchasing power but never nominal balances; deflation and zero inflation are covered.
- **INV-AC-04 — UI:** Studio at desktop 1440px and phone 390px, keyboard controls/navigation, signed losses, explicit synthetic samples, chart/table units, assumptions and empty/error/loading/stale states are reviewed in a browser. Record any unperformed accessibility/cross-browser checks.
- **INV-AC-05 — Files and saved plans:** Versioned JSON round-trip and tampered-total recomputation, CSV parity/safety, encrypted investment CRUD/reopen, two-user isolation, stale-save prevention and revision conflicts pass. Existing saved plan/file kinds remain compatible.
- **INV-AC-06 — Release boundary:** Local-only runtime, local assets, no telemetry/provider calls and existing request guards remain verified. Full regression suite, Python compilation, JavaScript syntax and dependency checks pass before commit/push; CI must pass before updating the Pages showcase. Public previews use synthetic precomputed examples only.

## Sequence and approval checkpoint

1. Scope approved by the user on 2026-10-28: growth first; allocation and holdings later. The reviewed conventions below are the implementation contract.
2. Implement and independently test the pure model and serialization contract.
3. Add Studio page/API and encrypted saved-plan integration; perform HTTP/security regression checks.
4. Review the working local UI at desktop/phone widths, record evidence and limits, then commit/push tested changes and verify CI. Update the public showcase only with reviewed static synthetic content.

Holdings/return analysis, portfolio allocation and market data need their own subsequent specification; this milestone establishes reusable investment scenario boundaries.

## References and attribution

- [SEC Investor.gov compound interest calculator](https://www.investor.gov/financial-tools-calculators/calculators/compound-interest-calculator), consulted 2026-10-28: reference for an input-driven growth tool. Its compounding choices do not define this app's effective-return convention.
- [SEC Investor.gov fee-impact bulletin](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/updated), consulted 2026-10-28: explains ongoing versus transaction fees and how fees reduce the capital earning returns. The monthly deduction and counterfactual formulas above are this project's explicit model, not an SEC billing rule.
