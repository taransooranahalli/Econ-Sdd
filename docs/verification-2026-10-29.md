# Econ verification — 2026-10-29

Release: **0.5.1**. Current scope is verified locally within the checks below. Real market data, stocks/portfolio construction and bank connections are later work.

## App availability and startup

The original port-8004 URL had no listening Python process. Restart initially encountered this Codex session's loopback-network restriction; the user granted the required session access. The app is running again on **http://127.0.0.1:8004/investments**, bound only to 127.0.0.1. Savings, Cash flow, Investments, Account, Saved plans and configuration routes all returned HTTP 200.

The CLI and `Start Econ.command` now both default to port 8004. The launcher was exercised from outside the project directory and started the correct project/virtual environment. Its executable permission and shell syntax were checked. Keep the Python process running while using the app. If it stops or the computer restarts, double-click `/Users/saint/Econ-Sdd/Start Econ.command` in Finder, leave its Terminal open, then revisit the local URL. This patch installs no automatic background service.

## Calculator and saved-plan checks

All amounts below are USD and use labeled synthetic data.

| Feature | Reference case | Verified result |
| --- | --- | --- |
| Savings | $1,000 + $100/month, 5% annual effective, 12 months, month end | $2,277.26 |
| Goal | $1,000 initially, $5,000 target, 5%, 24 complete months | $154.92/month |
| Cash flow | $4,500 monthly income − $3,000 expenses | $1,500.00 surplus |
| Investment growth | $10,000 + $250/month, 5% total return, 0.5% annual nominal fee, 2% inflation, 120 months | $53,067.70 nominal ending value |

The running main service returned all four reference results. In a separate temporary account database, browser sign-in, named saving of all four calculator types, library listing, reopening and recalculation, and sign-out worked. Investment edits/currency changes disabled stale file/account saves; the prior result retained USD; fractional JPY contributions produced a field error. Phone layout had equal client/scroll widths (375px inside the 390px viewport). The current desktop app panel was visually inspected. Browser warning/error logs were empty. Temporary test storage/services were removed/stopped; real account records and keys were not used as test fixtures.

## Bugs fixed during verification

- Savings/Goal original rates could serialize as `1E-8`, then fail the strict importer or saved-plan reopening. New original-input JSON/CSV uses fixed-point text. Supported legacy result files/encrypted plans receive a bounded, numerically equivalent read-time notation repair; manual inputs remain strict, and invalid versions/ranges/precision are still rejected. Existing plans are not rewritten automatically.
- The local bookmark used port 8004 while default startup used 8000. Defaults and launcher instructions now agree.
- Installed package metadata still reported 0.4.0 while the app displayed 0.5.0. Package metadata now reads the single app-version definition; an editable reinstall verified both report 0.5.1.

## Automated verification

**425 tests passed**: the previous 415 checks plus 10 regression cases for canonical/legacy tiny-rate file and encrypted-plan reopening, strict manual inputs and hostile/out-of-range legacy exponents. The full suite includes independent Decimal/Fraction references, boundaries, currencies, timing, file recomputation, SQL ownership/revisions, encryption/tamper handling, passwords/recovery/sessions, request guards, and publication boundaries.

Python compilation, app JavaScript syntax, installed dependency consistency, shell syntax and publication checks passed. The showcase builds from the actual passing JUnit report. The initial pre-permission test run could not write its report; the final run completed successfully after the session grant.

## Limits and next work

This is not an independent security audit, exhaustive assistive-technology/cross-browser evaluation, performance benchmark or production-hosting sign-off. Password/recovery, ciphertext tampering and multi-user isolation were verified through automated temporary-store/API tests; native password/recovery forms and download/file-picker dialogs were not repeated manually this session. Existing real user plans were deliberately not inspected. No market data provider or bank account was connected.

The current product is ready for the user's local review. The next specification can define stock coverage, API/provider budget, data licensing/freshness, dividends/corporate actions, valuation, allocation and portfolio return conventions. Bank connections remain a separate possible milestone with explicit consent and token/privacy requirements.
