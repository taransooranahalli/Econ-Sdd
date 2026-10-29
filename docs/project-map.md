# Econ project map

The app is a Python FastAPI service with a small local HTML/CSS/JavaScript interface. Financial calculations, storage, and rendering have separate responsibilities.

```text
Econ-Sdd/
├── src/econ_sdd/
│   ├── finance/
│   │   ├── savings.py          Decimal savings projection
│   │   ├── goals.py            Required deposit and calendar rules
│   │   ├── investments.py      Total return, monthly fees and purchasing power
│   │   ├── cash_flow.py        Monthly income minus expenses
│   │   └── currencies.py       Supported currencies and minor units
│   ├── serialization/         Versioned JSON/CSV and server display values
│   ├── security.py            AES-GCM envelopes and private keyring files
│   ├── accounts.py            SQLite schema, credentials, sessions, plan CRUD
│   ├── account_api.py         Account routes and owner-scoped saved plans
│   ├── market/                Alpaca GET transport, validation, cache and local setup
│   ├── market_api.py          Session/CSRF guarded Stocks APIs
│   ├── web.py                 App factory, request guards and calculator API
│   ├── __main__.py            Loopback launcher
│   └── static/                Studio pages, scripts, styles and local fonts
├── tests/unit/                Math, encryption, storage and lifecycle checks
├── tests/integration/         HTTP, sessions, isolation, file and asset checks
├── docs/                      Product, math, data and security specifications
├── data/accounts.sqlite3      Local account database; excluded from Git
├── .secrets/keyring.json      Private keys; excluded from Git and editor search
├── .secrets/alpaca.json       Optional owner-bound provider profile; excluded from Git
├── requirements.lock          Exact installed dependency versions
└── pyproject.toml             Package metadata and runtime dependencies
```

## How a saved plan travels

The browser submits a name, calculator kind and original inputs. The API validates the inputs with the appropriate pure Python model. The store encrypts the name and canonical input record, binding it to the owner, plan ID and revision. SQLite retains that ciphertext and the ownership/revision metadata.

Opening a plan checks the signed-in owner, authenticates and decrypts the ciphertext, validates the recorded model version, and recalculates the result in Python. Saved derived balances are never trusted. The browser renders the new server result.

## SQL structure

The schema is defined in `AccountStore.initialize` in `src/econ_sdd/accounts.py`; `PRAGMA user_version` records its migration version. Unsupported versions fail closed. Future schema changes need a reviewed migration.

| Table | Purpose |
| --- | --- |
| users | Random user ID, keyed username lookup, encrypted username, Argon2id password hash, recovery-code digest |
| sessions | Session-token digest, user foreign key, creation and last-seen times |
| plans | Random plan ID, owner foreign key, revision, authenticated ciphertext, timestamps |
| attempts | Keyed attempt-limit buckets with expiration |
| metadata | Encrypted key-compatibility probe |

Keys are outside SQLite. Passwords are hashed, not decrypted. IDs, owner links, timestamps and hashes remain visible database metadata. This is server-managed encryption: the app can decrypt saved plans during authorized use.

Start with `docs/account-spec.md` for the security contract and `docs/plan.md` for verified checks and limitations. Hosting and production key/backup configuration remain separate work.

Stocks reads follow a separate path: signed-in owner + both CSRF tokens → bounded request validation → owner-bound market service → fixed-host HTTPS GET → normalized observations and Python-formatted prices → Studio rendering. Temporary source caches contain no portfolio inputs. [Setup and limits](alpaca-setup.md).
