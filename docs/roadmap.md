# Ongoing product roadmap

The project is deliberately incomplete. The current release establishes calculator, data and account boundaries that later research features can reuse.

| Area | Status | Next specification work |
| --- | --- | --- |
| Savings projection | Implemented | Feedback and reviewed extensions such as variable deposits/rates |
| Savings goal | Implemented | Sensitivity/scenario comparison with explicit calendar conventions |
| Monthly cash flow | Implemented | Dated running-balance planning if requested |
| Local accounts and encrypted saved plans | Implemented locally | Hosting threat model, operational backups and account lifecycle |
| GitHub Pages showcase | Current publication milestone | Verified CI/deployment and readable SDD evidence |
| Live Python backend | Planned | Host/budget, persistent SQL storage, TLS/proxy, secrets, backups, capacity and abuse controls |
| Investment and portfolio research | Planned | Instruments, valuation/return definitions, dividends/corporate actions, allocation, benchmark and cost assumptions, data licensing/freshness |
| Prediction-market analysis | Planned | Event/outcome definitions, market-implied probabilities, fees/spreads/liquidity, resolution rules, timestamps and data provenance; analysis before execution |
| Forecasting / ML experiments | Planned, separate research track | Target/horizon, information cutoff, chronological evaluation, leakage/bias controls, baselines, uncertainty and reproducibility |
| C/C++ acceleration | Deferred until profiling | Correctness parity and measured speed benefits behind the Python contract |

Investment analysis, prediction-market probabilities and ML forecasts are different products. Market prices do not automatically provide calibrated forecasts. No trading or investment performance is claimed; no investment or prediction-market engine is implemented in this release.

Each milestone follows the workflow in [AGENTS.md](../AGENTS.md): define the contract and acceptance criteria, implement a bounded slice, independently verify, review, then record limits and status.
