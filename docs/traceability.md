# Requirements to evidence

The specifications define intended behavior; code implements it; tests check it. This map provides entry points rather than claiming exhaustive coverage or an independent audit.

| Requirement | Authoritative contract | Implementation | Verification |
| --- | --- | --- | --- |
| Savings arithmetic and timing, SAV-AC-01..03 | [SAV-M01/M02](math-spec.md) | [Savings engine](../src/econ_sdd/finance/savings.py) | [Independent worked example, exact Fraction timing, boundary references, seeded properties](../tests/unit/test_savings.py) |
| Goal deposit and dates, GOAL-AC-01..03/05 | [Goal contract](goal-spec.md) | [Goal solver/calendar](../src/econ_sdd/finance/goals.py) | [Independent cash-flow reference, minor-unit minimality, leap/clipped dates](../tests/unit/test_goals.py) |
| Monthly cash flow, CF-AC-02/03/06 | [CF-M01](cash-flow-spec.md) | [Cash flow engine](../src/econ_sdd/finance/cash_flow.py) | [Integer-cent reference, zero denominators, seeded invariants](../tests/unit/test_cash_flow.py) |
| Versions and recomputed imports, SAV-AC-06 / GOAL-AC-04 / CF-AC-05 | [Data contracts](data-spec.md) | [File adapters](../src/econ_sdd/serialization/) | [Savings records](../tests/integration/test_records.py), [goal records](../tests/integration/test_goal_records.py), [cash flow records](../tests/integration/test_cash_flow_records.py) |
| Account lifecycle and encrypted persistence, AUTH-AC-01/02/04 | [Account contract](account-spec.md) | [SQLite store](../src/econ_sdd/accounts.py), [encryption](../src/econ_sdd/security.py) | [Nonce/context authentication, raw-file privacy, expiry, recovery races, restart/restore/rotation](../tests/unit/test_account_store.py) |
| Two-user access and request guards, AUTH-AC-03 | [Account contract](account-spec.md) | [Account routes](../src/econ_sdd/account_api.py), [web boundary](../src/econ_sdd/web.py) | [Owner isolation, CSRF, revisions, safe errors, HTTPS settings](../tests/integration/test_account_api.py) |
| Studio UI and data states | [UI standard](ui-standard.md) | [Local frontend](../src/econ_sdd/static/) | [Recorded desktop/phone and Dia checks](plan.md); HTTP/static tests do not replace visual review |
| Safe public repository and Pages, PUB-AC-01..06 | [Publication contract](publication-spec.md) | [Publication checker](../tools/check_publication.py), [showcase builder](../tools/build_showcase.py), [workflow](../.github/workflows/verify-and-publish.yml) | [Publication tests](../tests/integration/test_publication.py), staged-file audit, passing JUnit build gate and browser review |

## Independent numerical examples

- Savings: $1,000 initially + $100 at each month end, 5% annual effective rate, 12 months -> **$2,277.26**. The test uses a separate cash-flow sum; rational cases protect timing and rounding ties.
- Goal: $1,000 initially, $5,000 target, 5% annual effective rate, 24 complete periods, month-end deposits -> **$154.92/month**. A 100-digit independent sum checks the value; one cent less fails the target.
- Cash flow: $4,500.30 income minus $3,000.30 expenses -> **$1,500.00**. Exact integer-minor-unit arithmetic supplies the reference.

## What the history means

After GitHub’s README initialization, the first application commit is a reviewed snapshot of work developed locally with its specifications. The milestone record in plan.md describes that work; it is not a fabricated sequence of earlier Git commits. Future changes can use branches, issue acceptance criteria and pull requests to make the specification-to-test progression visible.
