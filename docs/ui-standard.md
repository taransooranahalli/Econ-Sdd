# Econ-Sdd UI standard

Status: accepted by the user on 2026-10-26. Studio is the production UI standard; implement in Python-backed local web application.

## Visual identity

Reference: [taran.work](https://taran.work), inspected live for palette and typography. Adapt its near-black background, white type, Poppins typography, purple accents (reference accent #b252ca), understated rounded controls, and black-to-purple gradient. Use a restrained gradient in the app chrome so financial data stays readable. Do not copy portfolio images, biography, contact details, or other unrelated content into the finance app.

Studio is the selected layout: a sidebar, a dedicated assumptions form, and a focused result panel. Workbench remains an earlier alternative and is not part of this release.

Use consistent spacing, visible labels, tabular numbers, accessible contrast and focus, responsive stacking, and explicit stale/error states. Tables retain row/column labels; charts include currencies and time units. Keep assumptions close to the results. Show sample provenance and label outputs as conditional projections.

## Currency behavior

- Default to USD. Display currency symbols on money values and explicit ISO currency codes in the selector, inputs, result context, tables, and charts.
- Supported currencies: USD, EUR, GBP, CAD, AUD, INR, JPY, KWD. This is an initial set, not a country or tax assumption.
- A scenario contains amounts in one selected currency. Changing the selection retains entered numeric amounts and reinterprets the scenario in that currency. It does not perform exchange-rate conversion. State that behavior beside the inputs.
- Use the selected currency's minor-unit precision in inputs and presentation: for example, USD has two decimal places, JPY zero, KWD three. Reject incompatible entered precision instead of silently rounding deposits.
- Apply one currency consistently to principal, contributions, balances, interest, chart axes/readouts, tables, errors, and accessible labels. A stale result retains its original currency until successfully recalculated. Changing inputs disables exports until a successful calculation.
- Persist the currency choice as a presentation preference only; do not send user-entered financial amounts into conversation state.
- Production JSON/CSV formats record the currency code. Product, math, and data specifications now reflect this convention.
- FX conversion, FX data sources/timestamps, cross-currency portfolios, and jurisdiction-specific taxes need their own specifications before integration.

## Calculation boundary

The original prototype demonstrated style with browser arithmetic. Production financial results must come from the independently tested Python Decimal engine. Results are conditional projections, not bank quotes or forecasts. No financial provider, brokerage, hosting, or paid service is connected.

## Goal mode

Preserve Studio styling with a Grow savings / Reach a goal segmented selector. Goal mode replaces monthly-deposit and numeric-horizon inputs with target amount and editable dates. Emphasize the required monthly deposit above the existing projected balance, show the requested and modeled end dates, and reuse the chart/schedule with date labels and a goal line. Keep precision/date errors, stale markers, and export disabling consistent. [Goal specification](goal-spec.md) owns the financial conventions.

## Cash flow page

Preserve Studio sidebar, dark surfaces, purple accents, local Poppins, currency selector, and responsive layout. Use editable income/expense sections and a focused signed monthly net result with category bars. Show monthly-only inputs, sample/manual labels, safe empty/error/stale/loading states and JSON/CSV controls. Both calculators must be reachable on phone as well as desktop.

## Accounts and saved plans

Use existing Studio surfaces/typography/currency behavior for /account and /plans. Explain encryption coverage and explicit saves. Provide accessible sign-in/create/recover/password forms, one-time recovery-code display, signed-in state, named account saves, a private plan library and stale/revision-conflict feedback. Calculator math remains unchanged.
