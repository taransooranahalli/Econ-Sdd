# Econ-Sdd

**A specification-driven finance application, built in Python.**

[Portfolio showcase](https://taransooranahalli.github.io/Econ-Sdd/) · [Requirements → code → tests](docs/traceability.md) · [Roadmap](docs/roadmap.md) · [Architecture](docs/architecture.md)

A private local app for savings, goals, monthly cash flow, and encrypted saved plans with the approved Studio UI: dark surfaces, Poppins typography, and purple accents inspired by taran.work. Financial results are computed in Python with Decimal arithmetic; the browser renders the results.

## What this project demonstrates

Econ starts with reviewable contracts: explicit units and assumptions, numbered acceptance criteria, independent numerical references, separate calculation/UI/storage boundaries, and verification recorded against each milestone. [Trace one requirement through its implementation and tests](docs/traceability.md).

The GitHub Pages site is a static portfolio with synthetic previews and precomputed examples. The full FastAPI application runs locally; Pages does not host its Python calculations, sign-in or SQLite data. [Publishing and backend-hosting boundary](docs/deployment.md).

| Area | Current status |
| --- | --- |
| Savings, target-date goals, monthly cash flow | Implemented |
| Sign-in and encrypted saved plans | Implemented and verified locally |
| Public portfolio | GitHub Pages publication workflow |
| Investment and portfolio research | Planned |
| Prediction-market analysis | Planned |
| Forecasting / ML and C/C++ acceleration | Separate future research; not implemented |

## Development workflow

1. Define the behavior in a [specification](docs/product-spec.md) and record assumptions before changing code.
2. Link the numbered acceptance criteria to a bounded implementation slice.
3. Verify financial models with independent examples, exact arithmetic or meaningful invariants.
4. Test the API, serialization, security and UI separately; state which checks actually ran.
5. Review the milestone and update [the evidence record](docs/plan.md). Use the issue/PR templates for subsequent work.

The first public commit is a reviewed snapshot of work developed locally. Earlier local milestones are documented; Git history is not backdated to imitate their development.

## Run locally

From this project folder, initialize account storage once, then start the app:

```sh
.venv/bin/python -m econ_sdd.accounts init
.venv/bin/python -m econ_sdd
```

Open http://127.0.0.1:8000/ in your browser. Stop the application with Ctrl-C. Use `--port 8001` if port 8000 is occupied. The launcher binds only to 127.0.0.1 and has no public-host option.

Alternatively, on macOS, open `Start Econ.command` in this folder.

## Use

1. Enter a starting balance, monthly deposit, annual effective rate, and a whole number of months; choose month-end or month-start deposits. For a first look, choose **Load example**. It is visibly labeled as sample data.
2. Calculate to see balance, total deposits, signed interest, a chart, and a monthly schedule. Edit inputs and recalculate to explore sensitivity; prior results are marked out of date.
3. USD is the default. Other supported currencies are EUR, GBP, CAD, AUD, INR, JPY, and KWD. Changing currency keeps entered numbers and performs **no exchange-rate conversion**. Currency minor-unit precision is enforced, including zero decimals for JPY and three for KWD.
4. Save a JSON record or export the monthly schedule to CSV. **Open scenario** validates a saved JSON record and recomputes its results. Unsupported model versions are rejected rather than silently migrated.

The example of $1,000 initially plus $100 at each month end, at 5% annual effective growth for 12 months, produces **$2,277.26**. This is a projection under constant assumptions, not a forecast or bank quote.

## Savings goals

Choose **Reach a goal**. Enter your starting balance, target amount, annual effective rate, start date, and target date. The start date defaults to your browser's local date and remains editable. The Python solver returns the smallest monthly deposit, rounded upward to the selected currency's minor unit, that reaches the goal under those assumptions.

Only complete monthly periods count. Each monthly anniversary is anchored to the original start day and clipped to month end where needed. Partial final months add no deposit or interest; the result shows both the requested deadline and the actual modeled end. Beginning-of-month deposits start on the start date; end-of-month deposits start one anniversary later. A deadline with no complete period needs a starting balance that already covers the goal.

For example: $1,000 starting balance, $5,000 goal, 5% annual effective rate, and 24 complete months needs **$154.92 per month** with month-end deposits. This is a conditional projection, not a guarantee of future returns. JSON/CSV goal exports retain the target and dates; imports recompute the deposit. Original savings files remain supported.

## Cash flow

Choose **Cash flow** from the sidebar or phone navigation, or open `/cash-flow`. Add monthly income and expense categories, then calculate to see income, spending, signed surplus/shortfall and a spending breakdown. Amounts are monthly totals in the selected currency, not weekly/annual entries. Use take-home income. Leave out own-account transfers, including savings allocations; avoid counting both card purchases and repayment of the same purchases as expenses. Enter zero explicitly or remove unused categories; keep at least one category on each side.

A surplus is money left before savings allocations. A shortfall means expenses exceed income; the result is not an account balance and does not track cash between paydays. Undefined percentages (such as spending share when income is zero) show Not applicable. No future extrapolation or target spending ratio is inferred.

**Load example** shows $4,500 income, $3,000 expenses and a $1,500 monthly surplus. **Save budget · JSON** and **Open budget** preserve and recompute cash flow inputs; **Export breakdown · CSV** includes each category, totals and conventions. CSV protects labels from spreadsheet-formula interpretation. Open savings/goal files in Savings, cash flow files in Cash flow. Unsaved inputs are lost on refresh or navigation.

## Accounts and saved plans

Open **Sign in**, then **Create account**. Use a username (3–32 letters/digits/periods/underscores/hyphens) and a password of 15–128 characters. Save the one-time recovery code somewhere private: it is required if you forget your password, and is replaced after recovery or password change. It is not emailed or shown again. Password changes and recovery sign out all existing sessions; normal sign-out revokes the current session. Sessions expire after 30 minutes idle or seven days absolute age.

Calculators remain available anonymously. After calculating, enter a **Plan name** and choose **Save to account**. **Saved plans** lists only your plans. Open a plan to restore its original inputs and recalculate it. Edit its name/inputs and choose **Update saved plan**, or **Save a copy**. Conflicting edits in another tab require reopening the latest version. Editing calculator inputs disables saving until recalculation. Saving is explicit, not automatic. Original JSON/CSV downloads remain available and unencrypted.

SQLite stores users, session-token digests, encrypted plans, and keyed attempt limits in `data/accounts.sqlite3`. The separate `.secrets/keyring.json` contains private server keys. Both are excluded from source control; their directories/files use owner-only permissions. Do not post or commit either file. Passwords use Argon2id hashes. Saved names, usernames and calculator inputs use authenticated AES-256-GCM encryption; IDs, ownership links, timestamps, hashes and revisions remain visible metadata.

This is server-managed encryption: the running app can decrypt saved inputs for authorized use. Losing the keyring makes the encrypted data unavailable; never generate replacement keys for an existing database. Initialization refuses that case and never overwrites an existing keyring. If you relocate data, configure `ECON_DATABASE_PATH` and `ECON_KEY_FILE` as separate private paths.

### Backup and rotation

Stop the app before making a simple file-copy backup. Back up the SQLite file and keyring separately to protected locations, preserve their private permissions, and test restoring copies before relying on a backup. The application does not schedule backups. Do not distribute a database backup together with its keys. Existing plaintext JSON/CSV downloads need their own storage protection.

To rotate the data encryption key, stop all app processes using the database, make protected backups, then run:

```sh
.venv/bin/python -m econ_sdd.accounts rotate-keys
```

The command keeps old decryption keys for old backups, re-encrypts current records transactionally, and preserves credentials and saved plans. Restart after rotation. Do not manually retire old keys while any retained backup needs them.

### Hosting boundary

This release is verified locally, not publicly deployed or independently security-audited. Before hosting, review HTTPS and trusted proxy/domain settings, secret-manager/key recovery, persistent storage, backups/restore, internet abuse controls/capacity, and account lifecycle/MFA needs. SQLite currently targets one app instance on a durable disk. `ECON_PUBLIC_ORIGIN` accepts only an exact HTTPS origin; it enables Secure `__Host-` cookies, origin/Host restrictions and HSTS, and rejects HTTP. The launcher still binds to loopback and does not trust forwarded headers. A hosting choice and deployment remain separate work.

See [the project map](docs/project-map.md), [account security specification](docs/account-spec.md), and [verification record](docs/plan.md).

## Assumptions and privacy

For savings and goal projections, rates are annual effective rates converted into twelve equal modeled months. Interest is not rounded to cash each month; only presented/exported amounts use currency minor units and half-even rounding. Negative rates are available as stress assumptions. Taxes, fees, inflation, variable rates, withdrawals, and actual bank day-count/accrual rules are not modeled.

There is no bank connection, market-data feed, analytics, or automatic saving of calculator inputs. Financial inputs are not logged. Fonts and assets are local. Unsaved state is lost on refresh. Downloaded files are unencrypted and should be stored/deleted appropriately. The local service is intended for a single user on their own computer; it does not provide isolation from other local software.

## Recreate the environment

Requires Python 3.12 or newer. The tested version is recorded in docs/plan.md. These commands install the pinned packages into a project virtual environment; installation requires network access, but normal operation does not contact external services.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
```

No Node build is required to run the app. No C/C++ compiler, TensorFlow, or other ML dependency is installed for this release.

## Verification

```sh
.venv/bin/python -m pytest tests/unit
.venv/bin/python -m pytest tests/integration
.venv/bin/python -m pytest
.venv/bin/python -m compileall -q src tests
.venv/bin/python -m pip check
```

If Node is available, `node --check src/econ_sdd/static/app.js` and `node --check src/econ_sdd/static/cash-flow.js`, and `node --check src/econ_sdd/static/account.js` check JavaScript syntax. Browser layout and interactions are reviewed separately from HTTP tests. See docs/plan.md for actual verification results and remaining limits.

## Public CI and Pages

The workflow in [.github/workflows/verify-and-publish.yml](.github/workflows/verify-and-publish.yml) verifies source/test safety, runs Python and JavaScript checks, and builds only an allowlisted static artifact. Its displayed check count comes from a passing pytest JUnit report. Pull requests verify and build; only main publishes to GitHub Pages.

Local reproduction:

```sh
.venv/bin/python -m pytest --junitxml=work/test-results.xml
.venv/bin/python tools/check_publication.py
.venv/bin/python tools/build_showcase.py --repository taransooranahalli/Econ-Sdd --test-report work/test-results.xml
```

Serve `dist/showcase/` as a static directory to preview it. It contains no database, keyring, account API or personal records. The staged-file audit and allowlist are safeguards, not a guarantee that every possible secret pattern can be detected. Never add private runtime files to Git.

## License and attribution

A project software license has not yet been selected. Public visibility alone does not grant an open-source license. Poppins is distributed under its included SIL Open Font License; synthetic UI screenshots show this project's own implementation.

## Project guidance

Start with AGENTS.md. Product, math, data, architecture, UI standard, and implementation status are under docs/. Scope changes follow the specification-first workflow. Forecasting and optional native acceleration are later work and require separate evaluated models.

Poppins is included under the SIL Open Font License; see src/econ_sdd/static/fonts/OFL.txt. Dependencies retain their respective licenses.
