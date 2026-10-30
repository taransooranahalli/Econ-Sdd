# Data specification

Status: implemented savings and savings-goal data contracts. Only manual savings inputs and explicitly labeled sample data are included. No providers, financial accounts, or market prices are involved.

## Input model: SavingsScenario v1

A versioned record contains:

| Field | Type and convention |
| --- | --- |
| schema_version | Integer 1 |
| name | Optional plain-text label, maximum 80 characters; never interpreted as markup/code |
| initial_balance | Canonical decimal string in selected currency |
| monthly_contribution | Canonical decimal string in selected currency |
| annual_effective_rate_percent | Canonical decimal string in percent; 5 means 5%, not 500% |
| duration_months | Integer |
| contribution_timing | beginning or end |
| currency | ISO code from the supported set in math-spec.md; default USD; no FX conversion |
| source | manual or sample; manually edited sample remains sample-derived |
| sample_derived | Boolean, true if any inputs were loaded from an example |

Numeric bounds and precision have a single definition in [math](math-spec.md#inputs-and-ranges). Unknown numeric input is not zero. No birth dates, account numbers, credentials, balances from banks, or other sensitive records are requested.

## Result and monthly rows

SavingsResult v1 contains the scenario, output_category=conditional_projection, model_version=savings-v1, schema_version=1, app_version, calculated_at_utc (ISO-8601 UTC), and monthly rows. Display calculation time as calculation time, not market observation time.

Each row contains month_index, closing_balance, recurring_deposits_to_date, total_deposited, period_interest, and cumulative_interest. Row zero exists even at zero duration. Money and rates in JSON are Decimal strings. All raw computed amounts retain the [math precision policy](math-spec.md#precision-rounding-and-errors); CSV uses presentation precision.

Include explicit assumptions in result metadata: annual_effective rate convention, twelve equal months, selected deposit timing, nominal money values, and tax/fee/inflation treatment=not_modeled. These flags must not imply that actual taxes or fees are zero.

## Serialization and import validation

JSON is a user-controlled local download, with supported re-import of its scenario. CSV is export only: include the monthly schedule plus scenario inputs, convention, currency, output category, provenance, schema/model versions, and UTC calculation timestamp as repeated metadata columns. Omit arbitrary user names from CSV to avoid spreadsheet-formula injection. Do not silently interpret arbitrary CSV as an import format.

Limit JSON uploads to 1 MiB; accept one UTF-8 JSON object, reject duplicate keys, malformed/nonfinite values, unsupported schema versions, invalid fields, and unknown scenario fields. Validate bounds before calculation. Reject booleans for numeric/version fields. Ignore exported result totals on reload and recompute; never deserialize executable objects or pickle. Reject unsupported model versions with an understandable message; migration to a new model convention is a later feature requiring explicit review. Export metadata records the current model version.

Every import/export test uses synthetic fixtures, covers sample provenance, and checks exact input round-trip and recalculated output. If a user edits imported fields, results become stale until recalculated. Use safe plain-text rendering of names and uploaded error details.

## Privacy, persistence, and missing data

Use per-session memory; no database or automatic persistence in v1. Browser refresh/server restart may discard unsaved scenarios; state this in the UI. Saving and backup mean an explicit download to a location controlled by the browser/user; deletion of downloaded files remains the user's responsibility. Files are not encrypted by the application; explain this beside export because files may contain personal inputs.

Bind runtime to loopback. Include no telemetry or analytics. Same-origin JSON requests require a per-process CSRF token; verify the Host header and reject cross-origin requests. Use only bundled/local UI assets. Do not send inputs to third parties, include inputs in logs/tracebacks, or use shared result caches. Handle uploads/downloads in memory where supported and avoid retaining uploaded files. Store dependency/environment files in the project; exclude virtual environments, secrets, generated exports, and runtime data from source control when Git is initialized.

Empty required fields produce field-level prompts and no result. Validation/arithmetic errors make current results unavailable; a prior result may remain only if visibly out of date and clearly associated with its original inputs. Downloads are disabled for stale results. There is no market-data freshness rule in v1 because there is no market data; future providers must define sources, timestamps, historical/delayed/live classification, stale thresholds, and unavailable behavior before integration.

## Local API contract

GET / serves the local UI and CSRF token; GET /api/config supplies supported currencies, precision, versions, and limits. POST /api/calculate accepts a SavingsScenario and returns the raw result plus server-formatted display values. POST /api/import accepts a complete JSON export or a scenario and validates/recalculates it. POST /api/export/json and /api/export/csv validate/recalculate the current scenario and return local file downloads. All POST bodies are at most 1 MiB and require application/json, same-origin context, and the X-CSRF-Token supplied by the UI. Errors use field-keyed messages without echoing entered values. Runtime stores no results on disk.

JSON raw monetary values remain strings; UI display values and CSV derive from the Python Decimal result. Chart coordinates alone may use finite binary floats. No browser financial calculation is authoritative. Source/model metadata and currency accompany every export. The scenario name is supported for imported records but omitted from CSV.

## Goal records

[Goal data contract](goal-spec.md#data-and-integration) adds SavingsGoal inputs and savings-goal-v1 result records alongside savings-v1. POST /api/goal computes a goal; import/export dispatch by the saved goal model or explicit calculation_mode=goal. Dates and amounts remain explicit user inputs. Derived contributions, period counts, and saved results are recomputed, not trusted. Savings files continue to use the existing schema/model.

## Cash flow records

[Cash flow specification](cash-flow-spec.md#integration-and-privacy) defines cash-flow-v1, original budget and derived outputs, separate guarded API routes, strict row validation, recomputed imports, and formula-safe CSV labels. Existing savings and goal contracts remain supported.

## Accounts and saved plans

[Account specification](account-spec.md) owns credentials, sessions, owner-scoped encrypted original inputs, revisions, recovery codes, encryption coverage/limits, key management, persistence and schema migration. Earlier download-only persistence describes anonymous use; signed-in users may explicitly save to their account. JSON/CSV downloads remain unencrypted.

## Investment records

[Investment data contract](investment-spec.md#data-api-and-encrypted-plans) defines investment-growth-v1, the investment_growth kind, explicit decimal inputs and recomputed JSON/CSV/account saves. Canonical inputs use fixed-point strings (never exponent notation), including tiny supported rates. Compact JSON preserves all monthly rows within the 1 MiB import cap.

## Canonical input notation — 2026-10-29 clarification

Every saved original money/rate input uses fixed-point decimal text, including very small supported rates. Exporting a valid decimal must not turn it into exponent notation that the strict input parser rejects. This applies to Savings, Goals, Investments and canonical encrypted input saves. Reopening recalculates without changing model conventions or trusting derived results.

Compatibility repair for pre-0.5.1 records: after checking a supported savings/goal result or encrypted-plan model version, bounded uppercase-E annual-rate strings previously emitted by Decimal are converted to equivalent fixed-point text and then fully validated. This does not change numeric meaning or rewrite the stored plan automatically. Raw/manual scenarios still reject exponent notation; unsupported versions and out-of-range/overprecision values remain rejected.

## Proposed market data and portfolio definitions

[Stock/portfolio draft](stock-portfolio-spec.md) owns provider/feed identity, live/EOD labels, source/fetch timestamps, freshness, corporate-action share basis, strict definition schemas, owner-bound market access and licensed retention/export gates. Financial definitions remain separate from price observations. No provider/cache/schema change is implemented.

## M10A stock observations

[Stocks contract](stock-portfolio-spec.md#m10a-implementation-details--2026-10-29) defines stable provider identity, Decimal-string prices, source/feed/currency, event versus bar timestamps, retrieval age, session calendar, missing-data states and memory-cache limits. Provider profile is a private mode-0600 local file bound to an existing account UUID; no browser/import credentials are accepted. Observations are temporary and are not saved to SQL, exported or displayed publicly. Existing encrypted calculator records and schemas are unchanged. [Setup](alpaca-setup.md).

## Portfolio holdings definitions

Model `portfolio-holdings-v1`, kind `portfolio_holdings`, schema 1. Save resolved identities, decimal-string shares/optional total cost/cash, USD pricing mode, as-of/confirmation and sample provenance. Encrypt names/definitions with the existing account envelope. Reopen/import returns unpriced and ignores derived totals; no provider request on reopen. Prices and results are excluded from JSON exports. Captures are in-memory owner/session/revision/hash-bound observations, never SQL records or exported files. [Authoritative bounds/source rules](stock-portfolio-spec.md#m10b-implementation-contract--authorized-2026-10-29).
