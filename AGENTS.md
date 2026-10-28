# Econ-Sdd project guidance

## Status and workflow

This is a private, single-user personal finance, investment, and options analysis project. The first requested feature is a savings calculator, and Python is the requested primary language. The user approved implementation on 2026-10-26 and selected the portfolio-inspired Studio UI standard, USD default, and currency selector. Later C/C++ acceleration and Python ML libraries are architectural directions, not current implementation milestones.

Savings and goal features are complete. The user selected monthly income and expenses for the cash flow calculator on 2026-10-27; its approved scope and conventions are in docs/cash-flow-spec.md.

Implement each approved calculator milestone one at a time. Changes to approved behavior still require specification-first updates. A folder-creation request is not scope approval. Deployment and paid services require separate authorization. Ask before material changes to product scope, financial assumptions, costs, or privacy.

Use spec-driven development after approval, one milestone at a time:

1. Identify applicable requirements and numbered acceptance criteria.
2. Update the specification before changing behavior or assumptions.
3. Implement the smallest coherent change.
4. Run relevant mathematical, application, and integration checks.
5. Review the change against the acceptance criteria.
6. Update milestone status and record remaining limitations.

For each completed milestone, report changes, verification, failures or uncertainty, and next steps. Make routine engineering decisions autonomously within approved scope.

## Specification ownership

- `docs/product-spec.md`: journeys, scope, non-goals, and numbered acceptance criteria.
- `docs/math-spec.md`: formulas, conventions, examples, limitations, and validation.
- `docs/data-spec.md`: schemas, provenance, freshness, privacy, and missing data.
- `docs/architecture.md`: proposed architecture and decisions.
- `docs/plan.md`: milestones, dependencies, acceptance checks, and status.

Keep documents concise and link to the authoritative definition rather than duplicating it. Mark proposed defaults as assumptions and unresolved choices as pending.

## Financial and research requirements

Separate financial calculations from UI code. Clearly label calculations from known inputs, projections conditional on assumptions, and experimental forecasts estimated from historical data. Explain material assumptions and tradeoffs in plain language.

Every approved model must specify its purpose, inputs, outputs, units, valid ranges, formula or algorithm, authoritative references where applicable, timing, compounding, annualization, fees, inflation, applicable tax treatment, precision, rounding, edge cases, limitations, and unavailable or unreliable conditions. Include an independently checked worked example and meaningful tests with explicit numerical tolerances.

Compare strategies with consistent starting capital, contribution schedules, horizons, and costs. Show liquidity needs, possible losses, and sensitivity to assumptions.

For options, distinguish expiration payoff from pre-expiration theoretical value. Specify multipliers, premiums, fees, exercise style, dividends, volatility, time conventions, and assignment or early-exercise limitations. Explain any approximation outside model assumptions.

Before implementing forecasting, define the target, horizon, information available at prediction time, metrics, baselines, and success criteria. Require chronological training, validation, and untouched final test periods; walk-forward evaluation where appropriate; and leakage controls in preprocessing and feature selection. Address survivorship bias, corporate actions, publication delays, and uncertainty calibration or coverage. Trading evaluations must account for costs, spreads, slippage, and executable timing. Record data versions, parameters, seeds, model versions, and unsuccessful experiments. Evaluate forecast quality separately from trading profitability. Never fabricate results or imply hypothetical performance is realized performance. Simulation ranges are conditional on simulation assumptions and are not automatically calibrated forecasts.

## Data, privacy, and UI requirements

Begin with manual input and clearly labeled sample data unless the user agrees otherwise. Keep providers replaceable. Display price sources, timestamps, and historical, delayed, or live status; expose stale or missing data and never invent substitute prices.

Keep credentials out of source control and browser code. Do not put personal financial data in logs or test fixtures. Do not request credentials or sensitive financial records during discovery. Brokerage execution and automated trading are outside the initial scope.

The UI should expose assumptions, scenario comparisons, uncertainty, save/export actions, understandable validation, and useful empty, loading, and error states.

## Required checks

Stack: Python 3.12, FastAPI/Uvicorn, approved Studio HTML/CSS/JavaScript UI, standard-library Decimal calculations, and pytest/HTTPX2. JavaScript renders server results and never supplies authoritative financial balances. See `docs/architecture.md` for decisions and future native/ML boundaries. Pin installed dependencies in requirements.lock. Preserve the accepted UI standard in docs/ui-standard.md.

After the approved toolchain is installed in a project virtual environment, required commands are:

- `.venv/bin/python -m pytest tests/unit` for savings math and validation.
- `.venv/bin/python -m pytest tests/integration` for serialization, API, privacy boundaries, and static asset contracts.
- `.venv/bin/python -m pytest` for the full available suite at milestone completion.
- `.venv/bin/python -m compileall -q src tests` for syntax validation.

Manual browser review must cover narrow/wide layout, keyboard use, assumptions, validation, sample labels, and exports. Verify loopback binding and absence of telemetry or external assets. API tests alone do not establish browser layout. Run the full available suite at each completed implementation milestone; report unavailable browser checks explicitly.

For applicable milestones, require independent mathematical reference values, edge cases, and meaningful properties; unit and integration checks; relevant application checks; and review of privacy, data-state labeling, and acceptance criteria. Never validate a formula solely by repeating the implementation in a test. Report checks not run and why.

## Account milestone

The user authorized sign-in, a user database and encrypted persistent calculator data on 2026-10-27. docs/account-spec.md defines the scope and security contract. This supersedes the original single-user/download-only constraint for explicit account saves. Deployment remains separately authorized. Never use real user credentials or financial records for tests; keep keys out of source and test against temporary stores.
