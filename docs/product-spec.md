# Product specification

Status: savings implementation approved by the user on 2026-10-26. Studio is the accepted UI standard; USD is the default with a currency selector.

## Product goal and first release

Build a private, single-user finance and research application incrementally. First deliver a deterministic savings calculator: users supply a starting balance, constant monthly contribution, constant annual effective rate, duration, and contribution timing. Show ending balance, total deposited, interest gained or lost, and a monthly schedule/chart. Results are projections conditional on user assumptions, not market forecasts or quoted bank offers.

## Decisions and assumptions

| Decision | State | First-release proposal |
| --- | --- | --- |
| First feature | User selected | Savings calculator only |
| Primary language and research direction | User selected | Python; future Python ML libraries and optional C/C++ kernels |
| Currency | User selected | USD default; selectable EUR, GBP, CAD, AUD, INR, JPY, KWD; currency minor-unit precision; no FX conversion |
| Rate convention | Approved first-release assumption | Annual effective rate; do not silently treat nominal annual interest as effective yield |
| Contributions | Approved first-release assumption | Fixed monthly deposits; end of month by default; beginning of month selectable |
| Taxes, fees, inflation | Approved first-release assumption | Not modeled; results explicitly labeled before these adjustments |
| Inputs and market data | Approved first-release assumption | Manual inputs; explicit synthetic example; no prices, accounts, or external providers |
| Access and persistence | Approved first-release assumption | Local computer only; session memory plus user-controlled JSON save/load and CSV schedule export |
| UI | User accepted Studio design | Portfolio-inspired dark surfaces, Poppins, purple accents; Python FastAPI backend serves the approved HTML/CSS UI |

Country-specific tax rules, hosting, data budgets, and options experience remain discovery topics before their respective features. None is inferred from the user's name or location.

## User journeys

1. Open the calculator with empty required fields and a clear explanation of the inputs. Alternatively choose Load example, which visibly marks all populated inputs as sample data.
2. Enter assumptions, select contribution timing, and calculate. Inspect summary, schedule, chart, and assumptions together.
3. Change an assumption and recalculate to explore sensitivity. Prior output is marked out of date until recalculation; this is not yet a side-by-side comparison tool.
4. Download a JSON scenario/result record or a CSV monthly schedule. Reload a previously saved JSON scenario and recalculate with version checks.

## Acceptance criteria

- **SAV-AC-01 — Inputs:** Accept and validate exactly the input ranges and conventions in [math](math-spec.md#inputs-and-ranges); missing values never become zero silently.
- **SAV-AC-02 — Arithmetic:** Produce all outputs and the month-zero row defined by SAV-M01/M02. Required numerical reference tests and edge cases pass.
- **SAV-AC-03 — Timing and rates:** Label annual effective rate and beginning/end contribution timing beside the controls and results. Explain equal-month accrual and show before-tax/fee/inflation status.
- **SAV-AC-04 — Inspection:** Show ending balance, initial plus subsequent deposits, signed interest, a monthly table, and a chart contrasting balance with deposits. Data sources, output category, model version, and calculation timestamp remain accessible.
- **SAV-AC-05 — States:** Start with an informative empty state; offer a labeled example; display field-specific validation, calculating, and recoverable error states; prevent stale results from appearing current. Validation errors retain user input.
- **SAV-AC-06 — Save/export:** JSON round-trip preserves inputs and conventions; reload recalculates rather than trusting supplied totals. CSV rows match the displayed schedule at the defined presentation precision. Apply [data validation](data-spec.md#serialization-and-import-validation).
- **SAV-AC-07 — Privacy:** Runtime binds to 127.0.0.1; analytics/usage statistics are disabled; no external UI assets or network providers; no sensitive inputs in logs, caches shared across sessions, or committed fixtures. Saved files are explicit user downloads, not background writes.
- **SAV-AC-08 — Usability:** Inputs have readable labels and validation, remain keyboard accessible, and summary/control layout works at 390px and 1440px widths. Wide schedules may scroll horizontally. Browser QA is separate from API/integration tests. Follow [UI standard](ui-standard.md).

- **SAV-AC-09 — Currencies:** Default to USD; use one selected currency across inputs, results, chart/table labels, validation, and exports. Switching currency keeps entered numbers and performs no FX conversion. Enforce minor-unit precision from [math](math-spec.md#inputs-and-ranges); stale results retain their original currency.

## Later features and non-goals

Later: multi-scenario comparison, variable rates/deposits, inflation and fee models, additional currencies/locales, net worth, debt comparisons, stock/ETF/portfolio/options research, and evaluated experimental forecasts.

No brokerage execution, automated trading, paid services, hosted deployment, account connections, real-time prices, tax engine, withdrawals, stochastic intervals, or predictive model in this release. Exported records are hypothetical projections, not realized returns. Future research follows [AGENTS.md](../AGENTS.md) and the research gate in [architecture](architecture.md#future-research-and-native-code).


## Savings goal extension

The user requested required monthly savings by a target date and approved complete monthly periods. Add Reach a goal mode while preserving Studio styling and USD/currency selection. [Goal specification](goal-spec.md) owns GOAL-AC-01 through GOAL-AC-05, calendar conventions, inverse math, examples, and goal persistence requirements.


## Monthly cash flow extension

The user selected monthly income and expenses on 2026-10-27. Add a Cash flow page with editable monthly categories, surplus/shortfall and category breakdown. [Cash flow specification](cash-flow-spec.md) owns CF-AC-01..06, conventions, examples, model and persistence contracts.

## Account extension

The user requested sign-in and encrypted persistent user data for every calculator, in preparation for eventual hosting. Add explicit account saves and a reusable private plan library per [account specification](account-spec.md); keep anonymous calculations. No public deployment or paid service is authorized.

## Public showcase and ongoing roadmap

The user selected GitHub Pages showcase first on 2026-10-28. [Publication specification](publication-spec.md) defines repository/site requirements. Investments and prediction-market analysis are planned future sections; current calculators and local encrypted accounts are implemented. The Pages site does not provide the Python/account backend.

## Investments specification work

The user requested the investments section on 2026-10-28 using the same specification-first workflow and Studio UI. [Investment growth contract](investment-spec.md) defines the first bounded tool, explicit financial conventions and INV-AC-01..06. The user selected growth first, with portfolio allocation/rebalancing and holdings/historical returns later. Implemented locally in 0.5.0; verification and limitations are recorded in plan.md.
