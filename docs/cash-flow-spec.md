# Monthly cash flow specification

Status: implemented and verified in 0.3.0 on 2026-10-27; user selected monthly income and expenses. Implementation follows the approved Studio UI, Python calculations, USD default, currency precision, local privacy and explicit downloads.

## CF-M01: monthly budget

Purpose: calculate the surplus or shortfall of a manually entered monthly budget and show spending categories. This is arithmetic on supplied monthly amounts, not a return forecast, transaction history or dated liquidity analysis.

Inputs: one currency (existing supported subset, USD default); income and expenses lists, each 1..50 labeled rows; source manual/sample, sample_derived boolean, optional name. Each row has exactly label and amount. Labels are nonblank plain text, at most 80 characters, with no control or surrogate characters. Amounts are required finite decimal strings without exponent notation, 0..1,000,000,000,000, and at most the currency's minor digits. Missing/blank amounts are errors; enter zero explicitly or remove unused rows. Duplicate labels are allowed and shown as separate rows. Optional name follows the existing 80-character plain-text contract. Unknown fields and versions are rejected.

All entries are monthly totals. Enter take-home income after deductions; include applicable bills, fees, tax payments and debt payments in expenses yourself. Exclude transfers between your own accounts (including savings/investment allocations) from spending. When entering card purchases as expenses, exclude repayment of the same purchases; add debt payments not otherwise counted. No frequency conversion, tax computation, daily ordering, starting balance, interest, inflation or future extrapolation is inferred.

Let I = sum(income amounts), E = sum(expense amounts), and N = I-E. Output I, E, signed N, and status surplus if N>0, shortfall if N<0, balanced otherwise. N is money left before savings allocations when positive, or the unfunded spending gap when negative. It is not a bank balance. Spending share of income is 100*E/I when I>0, otherwise null (display Not applicable). Expense category share is 100*amount/E when E>0, otherwise null. Shares may exceed 100% of income; never clamp financial ratios. Category bar widths only represent shares of expenses.

Use a local Decimal context of 80 significant digits and half-even presentation. Sums and differences are exact within these bounds. Keep raw amounts/ratios as Decimal strings; money formatting reuses currency minor digits, percentages display two decimal places. Rounded category shares need not sum to exactly 100%. Undefined ratios stay null, never become zero or NaN. Labels and arithmetic stay separate; the engine imports no UI/network modules.

## Independent examples and edge cases

- Monthly take-home pay 4,200.10 plus other income 300.20 gives I=4,500.30. Housing 1,600.05, utilities 200.10, food 450.15, transport 250.00 and other spending 500.00 give E=3,000.30; N=1,500.00. Exact integer-cent arithmetic is the reference.
- I=100 and E=125 gives N=-25 (shortfall), spending share 125%; I=0, E=25 gives N=-25 and undefined spending share. All-zero inputs are balanced with undefined ratios. Zero income does not divide by zero.
- Exact minor-unit arithmetic must work in USD (2 digits), JPY (0), KWD (3), at supported maxima, and regardless of the caller's Decimal context. Reordering rows leaves totals unchanged; adding equal income and expense preserves N; adding one minor unit of expense decreases N by exactly one minor unit.

## UI and acceptance criteria

- CF-AC-01: Savings and Cash flow navigation works on desktop and phone. Savings and goal modes retain behavior. Studio typography, colors and currency behavior remain consistent.
- CF-AC-02: Add/remove/edit monthly income and expense categories, clear manual inputs, or load an explicitly labeled synthetic example. Required/precision/range errors identify the affected row without echoing private values. Enter submits. Start empty; zero is explicit.
- CF-AC-03: Python returns exact income, expense and signed net totals, status and defined/undefined ratios. Show surplus/shortfall/balanced text, currency, category breakdown and plain-language conventions. Do not imply the surplus has already been saved.
- CF-AC-04: Editing rows or currency marks results out of date and disables exports. Preserve input on errors; prevent delayed responses from overwriting newer edits/imports.
- CF-AC-05: JSON preserves original inputs, currency, provenance and versions; load recomputes derived data. CSV includes each line, totals and conventions, and neutralizes spreadsheet-formula text in labels. Wrong calculator/model/schema files are rejected with an actionable message. Existing savings/goal files remain unchanged.
- CF-AC-06: Independent integer-minor-unit references, bounds, null ratios, invariants, serialization/API/security and regressions pass. Browser review covers wide/narrow layout, keyboard use, validation, stale states, sample labels and exports. Report unperformed native-dialog/accessibility/cross-browser checks.

## Integration and privacy

Cash flow has a separate pure finance/cash_flow.py module, serialization/cash_flow.py adapter, /cash-flow page and cash-flow.js. Reuse local styling/fonts and guarded FastAPI boundary. POST /api/cash-flow calculates; /api/cash-flow/import recalculates saved records; /api/cash-flow/export/json or csv exports. No new packages, providers, logs of amounts, background persistence or telemetry.

Raw budget: schema_version 1, calculation_mode cash_flow, income/expenses arrays of {label,amount}, currency, source, sample_derived, name. Output: schema_version 1, model_version cash-flow-v1, app_version, output_category monthly_budget_calculation, calculated_at_utc, budget, summary, expense_breakdown and assumptions. Derived values from imports are ignored; original budget/version validated. Export size remains below the 1 MiB import limit. Cash flow files use econ-cash-flow-CURRENCY filenames. CSV rows repeat metadata and totals, keep category order, and mark rows as income/expense; numeric fields are plain currency amounts. UI renders user labels as text.

## Reference and limits

[CFPB Monthly Budget](https://files.consumerfinance.gov/f/documents/cfpb_well-being_monthly-budget.pdf) defines the income-minus-spending approach. The app's explicit conventions above determine its scope. A monthly total cannot reveal temporary shortfalls between paydays; a dated running-balance calculator is deferred. This release has no target ratio, spending recommendation, automatic account import, cash transfer or guaranteed saving result.
