# Architecture

Status: implementation authorized on 2026-10-26. Python is the primary language; the accepted Studio design is the UI standard.

## ADR-001: independent Python math and approved browser UI

Use Python 3.12, FastAPI/Uvicorn for the loopback web service, standard-library dataclasses/Decimal/json/csv for calculations and serialization, and pytest/HTTPX2 for verification. Serve the Studio HTML/CSS and a small JavaScript interaction layer from the same process. Exact installed versions are pinned in requirements.lock. No Node runtime is required to use the app.

The earlier Streamlit proposal was provisional. The accepted UI now has precise typography, component layout, currency controls, and data inspection behavior. Serving the existing design directly avoids fragile Streamlit CSS overrides and preserves the approved standard. A separate frontend build system or API host is unnecessary. This is an engineering choice within the approved Python/local scope.

## Boundaries and layout

    src/econ_sdd/finance/       immutable inputs/results, validation, Decimal savings engine
    src/econ_sdd/serialization/ strict JSON parsing, saved records, JSON/CSV exports
    src/econ_sdd/presentation.py currency-aware server formatting
    src/econ_sdd/web.py         local API, CSRF/Host guards, static files
    src/econ_sdd/static/        Studio HTML/CSS/JS and local font files
    tests/unit/                independent references, boundaries, properties
    tests/integration/         serialization and local HTTP contracts

Flow: UI input strings -> validated scenario -> pure Python engine -> raw/string result plus server-formatted amounts -> UI/exports. Only chart coordinates and approximate chart ticks use browser floating point. Financial logic imports no UI, storage, network, or ML libraries. Decimal contexts are local and explicit.

## ADR-002: local privacy and saving

The supported launch command binds only to 127.0.0.1. Use same-origin requests, a process-scoped random CSRF token exposed in the local page, JSON content-type enforcement, Host checks, and a 1 MiB request cap. Do not enable cross-origin access. Serve fonts, styles, and scripts locally. Include no analytics, telemetry, external data providers, automatic persistence, shared result cache, or financial-value logging. Disable Uvicorn access logs. Tests cover boundary enforcement.

Session state is in the browser's memory. JSON save/load and CSV downloads are user-controlled and unencrypted; unsaved changes may be lost on refresh. No database, account system, or hosted access. A loopback service is not isolation from other software running under the same local user. Any later hosting/authentication/data-connection design requires a new decision and separate deployment authorization.

## Verification and dependency policy

Commands live in [AGENTS.md](../AGENTS.md). Implement/verify the engine first, then the local UI/API, then save/load/export. Dependencies are isolated in .venv and pinned in requirements.lock. The UI standard is [ui-standard.md](ui-standard.md). Test browser layout separately from HTTP tests; inspect phone and desktop widths, keyboard use, assumptions, stale/error states, and downloads.

## Future research and native code

Keep future NumPy/SciPy, scikit-learn, TensorFlow/Keras or other evaluated libraries optional and outside this app's runtime dependencies. No ML model is implemented in this release. Define targets, horizons, prediction-time information, metrics, baselines, success criteria, chronological training/validation/untouched-test splits, walk-forward protocol where appropriate, leakage/bias/publication-delay controls, uncertainty calibration, and reproducibility records before implementation. Trading evaluation adds executable timing, costs, spreads, and slippage; forecast accuracy and trading profitability remain separate.

C/C++ may later replace a profiled numerical bottleneck behind the Python contract. First benchmark the reference; then require explicit units/dtypes, ownership/error contracts, correctness parity, precision tolerances, and representative speed measurements. Added complexity does not establish better unseen-data accuracy.

## Primary references

- [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/) and [testing](https://fastapi.tiangolo.com/tutorial/testing/).
- [Starlette Host and origin middleware](https://www.starlette.io/middleware/).
- [Python Decimal](https://docs.python.org/3.12/library/decimal.html).
- [TensorFlow overfitting/generalization](https://www.tensorflow.org/tutorials/keras/overfit_and_underfit).

## Goal extension

Keep goal solving and calendar mapping in finance/goals.py, with no UI/network imports. It calls the existing forward engine and uses monotonic search over integer currency minor units. The web/serialization adapters dispatch goal and savings records separately. No new dependency or external provider is needed. See [goal specification](goal-spec.md).

## Cash flow extension

Use a separate pure finance/cash_flow.py module and serialization/cash_flow.py adapter. Serve /cash-flow with cash-flow.js and shared Studio styles/fonts. Cash flow API routes reuse the existing request guards. Savings and goal modules and file models remain unchanged. See [cash flow specification](cash-flow-spec.md).

## ADR-003: accounts and encrypted saved plans

The user requested sign-in, a user database and encrypted reusable calculator information on 2026-10-27. [Account specification](account-spec.md) supersedes ADR-002's no-database constraint for explicit saves. Add independent SQLite/account and AES-GCM storage adapters; retain pure calculator engines. Public hosting remains a later reviewed deployment.

## ADR-004: static public showcase, separate app hosting

Keep the Python/SQLite app intact. Publish an allowlisted static portfolio under site/ through GitHub Pages, with no live account forms or private runtime files. A later Python host can deploy from the same repository after its own storage/HTTPS/keys review. See [publication specification](publication-spec.md).
