# Savings goal specification

Status: implemented and verified on 2026-10-27; user approved complete-month date handling. This is an extension of the accepted Studio UI and existing savings engine.

## Goal and inputs

GOAL-M01 solves the minimum fixed monthly deposit needed for a nominal savings target by a selected date. Output is a conditional projection using the same annual-effective rate, deposit timing, fee/tax/inflation exclusions, and currency rules as [SAV-M01](math-spec.md).

Inputs: initial balance P; target amount G; annual effective rate R; start_date and target_date as explicit ISO calendar dates; end/beginning deposit timing; currency (USD default); source/sample provenance and optional name. P and G must be finite, nonnegative, at most 1,000,000,000,000, and use the selected currency minor-unit precision. Rate, metadata, and currency bounds match the existing model. Dates must be valid YYYY-MM-DD strings, target >= start, and produce no more than 1,200 complete periods. Start defaults to the browser's local calendar date, is editable, and is persisted explicitly for reproducibility. Country or tax treatment is not inferred from dates or currency.

## Calendar convention

For an anchor date S, anniversary(k) means S plus k calendar months, retaining S.day when available and otherwise clipping to that month's final day. Always calculate from the original anchor: Jan 31 -> Feb 28/29 -> Mar 31. n is the largest nonnegative k for which anniversary(k) <= target_date. The modeled end is anniversary(n). Dates between that end and the requested deadline receive no additional interest or deposit. Show n, both dates, and unused days explicitly; do not divide days by 30 or silently round up the horizon.

There are n scheduled contribution periods; a positive monthly contribution produces exactly n deposits. A zero-contribution solution has no first/last deposit date. End timing: anniversaries 1..n. Beginning timing: anniversaries 0..n-1. Each calendar interval is still one equal modeled month; calendar labels do not introduce daily accrual or leap-year interest. At n=0 no recurring deposit occurs for either timing. If the current balance is below the goal, report that a complete monthly period or a larger starting balance is needed. A funded zero-period goal requires zero monthly saving.

## Formula and algorithm

Let q = 1+i, with i = (1+R/100)^(1/12)-1, and A the existing engine's zero-deposit terminal balance.

    F_end = sum(q^k, k=0..n-1)
    F_beginning = q * F_end
    C_raw = max(0, (G-A)/F_timing)

At i=0, F=n. These factors follow from separately accumulating each deposit to the period end; this is the inverse of SAV-M01's future-value equation. A zero required contribution means the modeled terminal value of the starting balance covers the goal, not necessarily that today's balance already does. With a negative rate, a starting balance above G may still require deposits.

Use an 80-significant-digit local Decimal context. Report C_raw for inspection. The payable contribution is the smallest nonnegative integer multiple of the currency minor unit whose forward projection reaches G. Round upward rather than half-even to avoid underfunding. A monotonic integer search against the existing forward engine establishes the minimum, with at most roughly 50 comparisons for the supported amount/currency bounds. Verify the final projection >= G and (when C>0) one minor unit less produces a terminal balance < G. If even the maximum supported monthly contribution cannot reach the target, report the result as unavailable; do not clamp or claim success.

Financial displays other than the required contribution continue using existing half-even rules. Retain all intermediate precision. Show the final projected balance and surplus above the target (including any contribution-rounding surplus). Raw values remain Decimal strings; no browser financial solving is authoritative.

## Independently checked examples

1. USD, P=1000, G=5000, R=5%, 2026-10-27 to 2028-10-27, end timing: n=24. A separately summed 100-digit cash-flow calculation gives C_raw=154.9160726514073708011990381906114...; monthly deposit $154.92 yields 5000.098807314682033...; $154.91 yields 4999.847219475325289..., so $154.92 is the minimum cent amount.
2. Zero rate, P=0, G=100, n=3: exact fractions give C_raw=100/3; USD needs $33.34 (final $100.02; $33.33 reaches $99.99), JPY needs 34 (final 102; 33 reaches 99), and KWD needs 33.334 (final 100.002; 33.333 reaches 99.999).
3. Constructed R=12.6825030131969720661201% gives q=1.01 exactly. P=1000, n=2, end timing, G=1221.10 requires exactly 100 monthly. Beginning timing with G=1223.11 also requires exactly 100. Fraction arithmetic independently checks both.
4. Jan 31, 2027 to Mar 30, 2027 counts one complete period, ends Feb 28, and excludes 30 days. A Mar 31 target counts two periods. Feb 29, 2028 to Feb 28, 2029 counts twelve periods.

## UI and acceptance criteria

- GOAL-AC-01: Add Grow savings / Reach a goal mode selection within the accepted Studio design. Goal mode takes a target amount and dates instead of a monthly deposit and numeric horizon. Preserve USD default and all currency behavior.
- GOAL-AC-02: Highlight the required monthly deposit, target, requested deadline, complete-period count, modeled end, excluded partial days, and deposit timing. Explain upward rounding and the same conditional assumptions as savings projections.
- GOAL-AC-03: Reuse the existing Python projection for summaries, chart, and dated monthly schedule. Include a labeled goal line. Show a zero-deposit solution when covered and understandable errors for invalid dates, too-short unfunded horizons, unsupported precision, and range limits.
- GOAL-AC-04: Save/load/export retain goal inputs, dates, conventions, provenance, goal-model version, computed contribution, and projection. Imports recompute all derived results. Existing savings-v1 files remain supported. Editing inputs or currency invalidates results and disables stale exports.
- GOAL-AC-05: Independent values, minimality, negative/zero/near-zero rates, all currency precision classes, calendar clipping/leap years, n=0/1/1200, and regression tests pass. Verify accessible controls, responsive layout, and local-only operation; report browser test limits.

## Data and integration

Add goal model savings-goal-v1 alongside savings-v1; neither changes the other's meaning. A goal result contains the original goal input, derived SavingsScenario, forward projection, required/raw monthly contribution, target, surplus, modeled end, unused days, and first/last deposit dates. Rows include period-end and deposit dates. Goal JSON exports remain schema version 1 with a distinct model tag; CSV repeats goal metadata with the schedule. Unknown model versions remain rejected. All existing request size, source, CSRF, Host, privacy, and missing-data rules apply.

## References and limitations

- [Investor.gov savings-goal calculator](https://www.investor.gov/financial-tools-calculators/calculators/savings-goal-calculator) defines the monthly-contribution goal-solving use case.
- [LibreOffice PMT](https://help.libreoffice.org/latest/en-US/text/scalc/01/04060119.html) documents fixed periodic payments and beginning/end timing. The formula above is derived for this app's effective-rate and calendar conventions; no external calculator execution is claimed.

There is no daily proration, automatic bank transfer, changing rate, missed-deposit simulation, tax/fee/inflation model, FX conversion, or probabilistic forecast. Reaching the modeled target is conditional on assumptions and making the calculated deposits; it is not a guarantee of actual returns.
