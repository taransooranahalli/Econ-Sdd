# Ongoing product roadmap

The project is deliberately incomplete. The current release establishes calculator, data and account boundaries that later research features can reuse.

| Area | Status | Next specification work |
| --- | --- | --- |
| Savings projection | Implemented | Feedback and reviewed extensions such as variable deposits/rates |
| Savings goal | Implemented | Sensitivity/scenario comparison with explicit calendar conventions |
| Monthly cash flow | Implemented | Dated running-balance planning if requested |
| Local accounts and encrypted saved plans | Implemented locally | Hosting threat model, operational backups and account lifecycle |
| GitHub Pages showcase | Published | Continue refining the CI-backed SDD evidence and product previews |
| Live Python backend | Planned | Host/budget, persistent SQL storage, TLS/proxy, secrets, backups, capacity and abuse controls |
| Investment growth | Implemented locally in 0.5.0 | [Investment growth contract](investment-spec.md): manual total return, fees, inflation, Studio UI and encrypted plans |
| Stocks and market-data API | M10A local implementation; real-account verification pending | [Personal Alpaca setup](alpaca-setup.md), synthetic UI/API checks; verify actual free IEX access and personal display permissions after keys are configured |
| Manual holdings portfolios | Implemented locally in 0.7.0 | [M10B verification](portfolio-verification-2026-10-29.md); explicit share-basis/date confirmation, Alpaca value/weights/gains and encrypted definition saves |
| Budget / target allocation | Next implementation slice | PORT-M02 user-selected weights, cash target and bounded whole/fractional share sizing |
| Rebalancing existing holdings | Later contract | Transaction/cost rules, cash constraints, rounding and explicit review; no order execution |
| Holdings and historical return analysis | User requested later | Transactions, deposits/withdrawals, total/time-weighted/money-weighted returns, distributions, corporate actions, benchmarks and data provenance |
| Bank/account connections | Explicitly deferred by user; not connected | Separate consent, provider/permissions, token storage, sync/reconciliation, revocation and privacy contract before implementation |
| Prediction-market analysis | Planned | Event/outcome definitions, market-implied probabilities, fees/spreads/liquidity, resolution rules, timestamps and data provenance; analysis before execution |
| Stock predictions / ML and potential investment guidance | User-confirmed long-term direction; separate research track | [User review of statistics before modeling](stock-portfolio-spec.md#long-term-stock-prediction-direction--user-clarification-2026-10-29); target/horizon, baselines, chronological evaluation, leakage/bias controls, calibrated uncertainty and reproducibility; separate assessment before public advice features |
| C/C++ acceleration | Deferred until profiling | Correctness parity and measured speed benefits behind the Python contract |

Investment analysis, prediction-market probabilities and ML forecasts are different products. Market prices do not automatically provide calibrated forecasts. No trading or investment performance is claimed; the investment growth tool projects user-entered assumptions; prediction-market analysis and forecasts are not implemented.

Each milestone follows the workflow in [AGENTS.md](../AGENTS.md): define the contract and acceptance criteria, implement a bounded slice, independently verify, review, then record limits and status.
