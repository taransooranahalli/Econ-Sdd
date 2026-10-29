# Mathematical specification

Status: implemented savings conventions; goal extension specified separately. Reference examples below are independent of the implementation.

## Classification and model boundary

**SAV-M01** computes a constant-rate monthly savings balance. Its future values are projections conditional on assumptions. **SAV-M02** decomposes that projection into deposits and interest. Neither is a forecast. Financial functions must be pure Python without UI, filesystem, network, or ML dependencies.

## Inputs and ranges

All amounts in a scenario share one selected currency. USD is the default. Supported minor-unit digits: USD/EUR/GBP/CAD/AUD/INR = 2; JPY = 0; KWD = 3. Currency selection reinterprets entered amounts without FX conversion. Reject incompatible input precision rather than silently rounding deposits. Numeric magnitudes are otherwise unchanged by currency selection.

| Input | Unit/type | Valid range |
| --- | --- | --- |
| P: initial balance | Decimal amount in selected currency | 0 through 1,000,000,000,000; at most the currency minor-unit digits |
| C: monthly contribution | Decimal amount in selected currency | Same range/precision as P; withdrawals excluded |
| R: annual effective rate input | Decimal percent | -99 through 100 inclusive; at most 24 fractional digits |
| n: duration | Integer months | 0 through 1,200 inclusive |
| timing | Enum | end (default) or beginning |

Parse decimal text without passing through binary floating point. Internally use r = R/100, a dimensionless effective annual rate. Reject blank required fields, malformed/nonfinite values, booleans as numbers, fractional months, and out-of-range inputs. A negative rate is permitted as a constant-rate stress assumption, clearly labeled; it is not a prediction of bank behavior. Product bounds are engineering limits, not claims about plausible returns.

## SAV-M01: balance and schedule

Time zero is immediately before any recurring deposits. Twelve equal modeled months make one year; there are no actual calendar dates, day-count conventions, holidays, intramonth events, or leap-year adjustments.

Derive the effective monthly rate:

    i = (1 + r)^(1/12) - 1

This preserves (1+i)^12 = 1+r. Dividing an effective annual rate by twelve is incorrect under this convention. The constant-rate, equal-month model can approximate growth from an advertised annual yield but is not a bank statement or jurisdiction-specific APY disclosure calculation.

Initialize B_0 = P. For k = 1..n:

    end:       B_k = B_(k-1) * (1+i) + C
    beginning: B_k = (B_(k-1) + C) * (1+i)

End deposits occur at t=1..n; beginning deposits occur at t=0..n-1. Both schedules report closing balances after completed months. If n=0, no recurring deposits occur for either timing and the only row is B_0=P.

A derived closed-form cross-check is:

    i != 0, end:       B_n = P*(1+i)^n + C*((1+i)^n - 1)/i
    i != 0, beginning: B_n = P*(1+i)^n + C*(1+i)*((1+i)^n - 1)/i
    i == 0:           B_n = P + n*C

Derivation: accumulate P across n months and sum the geometric series of individual deposit growth factors. For beginning deposits, each deposit accrues one additional month. Use recurrence for the production schedule; do not evaluate the division at i=0. Closed form is a separate check, not the sole test oracle.

## SAV-M02: decomposition

For every row k (including k=0):

    recurring_deposits_k = k*C
    total_deposited_k = P + k*C
    cumulative_interest_k = B_k - total_deposited_k

For month k>=1:

    period_interest_k = B_k - B_(k-1) - C

Month zero has zero recurring deposits and zero interest. Final output is the n-th row. Signed interest can be negative. No additional tax, fee, or inflation model is applied. All monetary outputs have the same unit as P and C; interest is an amount, not an annualized return estimate.

## Precision, rounding, and errors

Use a local Decimal context with 80 significant digits and ROUND_HALF_EVEN. Detect exact rational monthly growth factors when the annual growth fraction has perfect twelfth-power numerator and denominator. For zero contributions, evaluate complete years using the exact annual growth factor and only residual months using the monthly factor. These algebraically equivalent refinements preserve exact half-minor-unit ties instead of letting root approximation choose the rounding direction. Preserve intermediate precision, including fractional monthly rates; do not round interest to minor units every month. Presentation and CSV money use the selected currency minor-unit digits with ROUND_HALF_EVEN; raw machine-readable results retain Decimal values as strings. Normalize displayed negative zero to the appropriate zero representation for that currency. Independently rounded interest rows may not add exactly to the rounded total; label this presentation effect rather than altering calculated balances.

Reject nonfinite input before arithmetic. Report numerical failure as unavailable; do not return NaN, infinity, or an invented balance. Tests compare unrounded balances to independent high-precision references with absolute error <= 1e-12 units across the supported domain, and require exact agreement for displayed two-decimal examples. Tests near rounding ties require an exact rational oracle or higher-precision reference; tolerance must not hide a wrong displayed cent.

## Independently checked examples

Examples are synthetic, use USD unless stated otherwise, and are not current market rates or performance claims. References originally stated in units retain the same numeric magnitude.

### Example A: effective annual rate and end deposits

Inputs: P=1,000.00, C=100.00, R=5%, n=12, timing=end.

    i = 0.004074123783648301605419602672107...
    B_12 = 2277.257752959728084062622637853...
    total_deposited = 2200.00
    cumulative_interest = 77.257752959728084062622637853...
    displayed balance = 2277.26; displayed interest = 77.26

Specification verification: 60-digit Decimal recurrence and closed form agreed beyond 50 decimal places. An independently expressed binary64 sum of the twelve individual deposit cash flows gave 2277.257752959728350, within 3e-13 units. That floating-point comparison is a small-example check, not a precision oracle for the entire input domain.

### Example B: exact rational timing reference

Choose a constructed R=12.6825030131969720661201%, which makes 1+i exactly 1.01. P=1,000.00, C=100.00, n=2.

    end month 1: 1000*1.01 + 100 = 1110
    end month 2: 1110*1.01 + 100 = 1221.10
    beginning month 1: (1000+100)*1.01 = 1111
    beginning month 2: (1111+100)*1.01 = 1223.11

Exact fractions independently give 12211/10 and 122311/100. Deposits total 1200.00; interest is 21.10 or 23.11 respectively. This deliberately constructed rate tests timing and is not a suggested savings yield.

### Example C: zero rate and decomposition

P=1,000.00, C=100.00, R=0%, n=12 gives 2200.00 for either timing and zero interest. Direct addition of twelve deposits independently verifies both SAV-M01 and SAV-M02. At n=0, either timing instead gives 1000.00, zero recurring deposits, and zero interest.

### Example D: independent published compound-interest check

The CFPB example starts with 1,000 at a 5% annual rate and reaches 1,102.50 after two annual compounding periods. With C=0, R=5%, n=24 our monthly-effective conversion yields the same 1000*(1.05)^2=1102.50; total deposits remain 1000 and interest is 102.50.

## Validation requirements

- Preserve Examples A-D as independent references, including rational arithmetic for B and direct sums for C; assert schedule rows and decomposition, not only final balance.
- Verify USD default, currency-invariant raw balances for equivalent valid inputs, JPY integer inputs, KWD three-decimal inputs, rejection of unsupported currency codes, and half-even presentation in each supported precision.
- Cover zero principal, zero contribution, all-zero input, n=0/1/1200, valid negative rates, near-zero rates, rate endpoints, amount bounds, missing inputs, nonfinite values, malformed strings, and invalid precision.
- Compare representative and seeded boundary cases against a 100-digit independent cash-flow sum; use exact Fraction arithmetic for rational monthly growth cases. Record the reference method and fixed seeds.
- Verify B_k = P+k*C+interest_k, n+1 rows, rate-conversion identity, scaling in P/C within bounds, and sensitivity to P/C/r. For nonnegative rates, balances cannot decline with increasing horizon or when moving deposits earlier. With negative rates, do not assert those last two properties; earlier deposits accrue more loss.
- Ensure precision isolation from the global Decimal context, exact half-even presentation ties, input/export round-trip, and consistency between summaries, schedules, and chart source data.

## Limitations and references

Constant rates/deposits and equal months cannot reproduce variable bank rates, daily accrual, tiered balances, taxes, fees, inflation, irregular contributions, withdrawals, or investment risk. No probability, confidence interval, or recommendation is produced. Sensitivity is explored by editing assumptions and recalculating; no uncertainty band is implied.

- [CFPB: compound-interest definition and independent two-year example](https://www.consumerfinance.gov/ask-cfpb/how-does-compound-interest-work-en-1683/).
- [Investor.gov: compound-interest calculator input concepts](https://www.investor.gov/financial-tools-calculators/calculators/compound-interest-calculator). This is contextual, not an independently executed oracle; its unspecified cash-flow conventions must not be assumed identical.
- [CFPB: annual percentage yield definition and calculation context](https://www.consumerfinance.gov/rules-policy/regulations/1030/a/). Referenced for effective-yield context, not a claim of regulatory compliance.
- [Python Decimal documentation](https://docs.python.org/3.12/library/decimal.html) for arithmetic context and rounding.

Future options/forecasting specifications must meet [AGENTS.md](../AGENTS.md). No such model is part of this release.

Currency metadata reference: [SIX ISO 4217 maintenance agency and List One](https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html). Currency selection does not imply a country or tax regime.

## Savings goal model

[GOAL-M01](goal-spec.md) defines the inverse contribution formula, complete-month calendar mapping approved by the user, upward contribution rounding, independent examples, tolerances, and validation. Existing SAV-M01/SAV-M02 behavior is unchanged.

## Cash flow model

[CF-M01](cash-flow-spec.md#cf-m01-monthly-budget) defines monthly income-minus-expenses, exact currency sums and undefined ratios. It is independent of savings interest calculations.

## Investment growth

[INV-M01/M02](investment-spec.md) own the investment total-return, monthly fee, zero-fee counterfactual and purchasing-power formulas, bounds, rounding and independent references. Existing savings/goal math remains unchanged.

## Proposed stock/portfolio math

[STK-M01 and PORT-M01/M02](stock-portfolio-spec.md#4-inputs-valuation-and-accounting) draft matched-basis stock price change, manual-holdings value/weights/entered-cost gain and budget/target allocation. The draft specifies source-price precision, share rounding, cash residuals, missing data and independently checked fictional examples; it is not implemented.
