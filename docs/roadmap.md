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
| Stocks and market-data API | Specification draft; live preferred / $0 initial budget | [Stock/portfolio contract](stock-portfolio-spec.md) and [provider review](market-data-api-review.md); limited-venue live feasibility and explicit EOD fallback |
| Portfolio creation and target allocation | Specification draft | Manual holdings, cash, optional entered basis, user-selected weights and bounded share sizing; encrypted definition saves |
| Rebalancing existing holdings | Later contract | Transaction/cost rules, cash constraints, rounding and explicit review; no order execution |
| Holdings and historical return analysis | User requested later | Transactions, deposits/withdrawals, total/time-weighted/money-weighted returns, distributions, corporate actions, benchmarks and data provenance |
| Bank/account connections | Explicitly deferred by user; not connected | Separate consent, provider/permissions, token storage, sync/reconciliation, revocation and privacy contract before implementation |
| Prediction-market analysis | Planned | Event/outcome definitions, market-implied probabilities, fees/spreads/liquidity, resolution rules, timestamps and data provenance; analysis before execution |
| Forecasting / ML experiments | Planned, separate research track | Target/horizon, information cutoff, chronological evaluation, leakage/bias controls, baselines, uncertainty and reproducibility |
| C/C++ acceleration | Deferred until profiling | Correctness parity and measured speed benefits behind the Python contract |

Investment analysis, prediction-market probabilities and ML forecasts are different products. Market prices do not automatically provide calibrated forecasts. No trading or investment performance is claimed; the investment growth tool projects user-entered assumptions; prediction-market analysis and forecasts are not implemented.

Each milestone follows the workflow in [AGENTS.md](../AGENTS.md): define the contract and acceptance criteria, implement a bounded slice, independently verify, review, then record limits and status.
