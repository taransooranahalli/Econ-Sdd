from decimal import Context, Decimal as D, ROUND_DOWN, getcontext, localcontext
from fractions import Fraction
import random

import pytest

from econ_sdd.finance.currencies import CURRENCIES
from econ_sdd.finance.savings import SavingsScenario, ScenarioError, calculate_savings
from econ_sdd.presentation import amount_text, money_text


def scenario(p="1000", c="100", rate="5", months=12, timing="end", currency="USD"):
    return SavingsScenario(D(p), D(c), D(rate), months, timing, currency)


def reference_cashflows(s):
    # Independent algorithm: separately grow every cash flow at 100-digit precision.
    with localcontext(Context(prec=100)):
        q = (1 + s.annual_effective_rate_percent / 100) ** (D(1) / 12)
        n = s.duration_months
        return s.initial_balance * q ** n + sum(
            (s.monthly_contribution * q ** (n - payment + (s.contribution_timing == "beginning"))
             for payment in range(1, n + 1)), D(0))


def test_independent_worked_example_a():
    result = calculate_savings(scenario())
    assert abs(result.final.closing_balance - D("2277.257752959728084062622637853")) < D("1e-24")
    assert money_text(result.final.closing_balance, "USD") == "$2,277.26"
    assert result.final.total_deposited == 2200
    assert amount_text(result.final.cumulative_interest, "USD") == "77.26"
    assert len(result.rows) == 13


@pytest.mark.parametrize("timing,expected", [("end", Fraction(12211, 10)), ("beginning", Fraction(122311, 100))])
def test_exact_rational_timing_reference(timing, expected):
    result = calculate_savings(scenario(rate="12.6825030131969720661201", months=2, timing=timing))
    assert result.monthly_rate == D("0.01")
    assert result.final.closing_balance == D(expected.numerator) / D(expected.denominator)


@pytest.mark.parametrize("timing", ["end", "beginning"])
def test_zero_rate_by_direct_addition(timing):
    result = calculate_savings(scenario(rate="0", timing=timing))
    assert result.final.closing_balance == D(1000) + sum([D(100)] * 12)
    assert all(row.period_interest == 0 for row in result.rows)


@pytest.mark.parametrize("timing", ["end", "beginning"])
def test_zero_duration_means_no_contributions(timing):
    result = calculate_savings(scenario(months=0, timing=timing))
    assert len(result.rows) == 1
    assert result.final.closing_balance == 1000
    assert result.final.recurring_deposits_to_date == result.final.cumulative_interest == 0


def test_published_cfpb_two_year_reference():
    result = calculate_savings(scenario(c="0", months=24))
    assert result.final.closing_balance == D("1102.5000")


@pytest.mark.parametrize("percent,expected", [("0.5", "1.00"), ("1.5", "1.02")])
def test_lump_sum_annual_half_even_ties(percent, expected):
    result = calculate_savings(scenario(p="1", c="0", rate=percent))
    assert amount_text(result.final.closing_balance, "USD") == expected


@pytest.mark.parametrize("principal,expected", [("0.50", "0.50"), ("1.50", "1.52")])
def test_exact_monthly_half_even_ties(principal, expected):
    # 1% monthly has a finite annual effective rate within the allowed precision.
    result = calculate_savings(scenario(p=principal, c="0", rate="12.6825030131969720661201", months=1))
    exact = Fraction(principal) * Fraction(101, 100)
    assert result.final.closing_balance == D(exact.numerator) / D(exact.denominator)
    assert amount_text(result.final.closing_balance, "USD") == expected


@pytest.mark.parametrize("rate", ["-99", "-5", "0", "0.000000000000000000000001", "5", "100"])
@pytest.mark.parametrize("months", [0, 1, 12, 1200])
def test_domain_boundaries_against_cashflow_reference(rate, months):
    s = scenario(p="1000000000000", c="1000000000000", rate=rate, months=months)
    expected = reference_cashflows(s)
    result = calculate_savings(s)
    with localcontext(Context(prec=100)):
        assert abs(result.final.closing_balance - expected) <= D("1e-12")
        for row in result.rows:
            assert abs(row.closing_balance - row.total_deposited - row.cumulative_interest) < D("1e-12")


def test_seeded_independent_cases_and_properties():
    rng = random.Random(20261026)
    for _ in range(20):
        s = scenario(p=str(rng.randrange(100000)), c=str(rng.randrange(1000)),
                     rate=str(rng.randrange(-500, 1501) / 100), months=rng.randrange(241),
                     timing=rng.choice(["end", "beginning"]))
        result = calculate_savings(s)
        with localcontext(Context(prec=100)):
            assert abs(result.final.closing_balance - reference_cashflows(s)) < D("1e-12")
            doubled = scenario(p=str(s.initial_balance * 2), c=str(s.monthly_contribution * 2),
                               rate=str(s.annual_effective_rate_percent), months=s.duration_months,
                               timing=s.contribution_timing)
            assert abs(calculate_savings(doubled).final.closing_balance - result.final.closing_balance * 2) < D("1e-12")


def test_negative_rate_losses_and_timing():
    end = calculate_savings(scenario(rate="-5"))
    beginning = calculate_savings(scenario(rate="-5", timing="beginning"))
    assert beginning.final.closing_balance < end.final.closing_balance < end.final.total_deposited
    assert all(r.period_interest <= 0 for r in beginning.rows)


def test_positive_rate_order_and_annual_identity():
    base = calculate_savings(scenario())
    early = calculate_savings(scenario(timing="beginning"))
    larger = calculate_savings(scenario(c="101"))
    assert early.final.closing_balance > base.final.closing_balance
    assert larger.final.closing_balance > base.final.closing_balance
    assert all(b.closing_balance >= a.closing_balance for a, b in zip(base.rows, base.rows[1:]))
    with localcontext(Context(prec=100)):
        assert abs((1 + base.monthly_rate) ** 12 - D("1.05")) < D("1e-75")


def test_global_decimal_context_does_not_change_projection():
    s = scenario()
    expected = calculate_savings(s)
    with localcontext() as ctx:
        ctx.prec = 6
        ctx.rounding = ROUND_DOWN
        assert calculate_savings(s) == expected
        assert money_text(expected.final.closing_balance, "USD") == "$2,277.26"
        assert getcontext().prec == 6


@pytest.mark.parametrize("currency", list(CURRENCIES))
def test_currency_invariance_and_display_precision(currency):
    result = calculate_savings(scenario(currency=currency))
    assert result.final.closing_balance == calculate_savings(scenario()).final.closing_balance
    rendered = amount_text(result.final.closing_balance, currency)
    digits = CURRENCIES[currency].minor_digits
    assert (len(rendered.split(".")[1]) if "." in rendered else 0) == digits


@pytest.mark.parametrize("currency,value,expected", [("USD", "1.005", "1.00"), ("USD", "1.015", "1.02"),
    ("JPY", "2.5", "2"), ("JPY", "3.5", "4"), ("KWD", "1.0005", "1.000"), ("KWD", "1.0015", "1.002"),
    ("USD", "-0.001", "0.00")])
def test_currency_rounding_reference(currency, value, expected):
    assert amount_text(D(value), currency) == expected


def payload(**overrides):
    return dict(initial_balance="1000", monthly_contribution="100", annual_effective_rate_percent="5", duration_months=12, **overrides)


@pytest.mark.parametrize("key,value", [
    ("initial_balance", ""), ("initial_balance", "NaN"), ("initial_balance", "Infinity"),
    ("initial_balance", "-1"), ("initial_balance", "1e2"), ("initial_balance", 1000.0),
    ("initial_balance", True), ("initial_balance", "1000000000000.01"), ("initial_balance", "1.001"),
    ("monthly_contribution", "-0.01"), ("annual_effective_rate_percent", "-99.01"),
    ("annual_effective_rate_percent", "100.01"), ("annual_effective_rate_percent", "0."+"0"*24+"1"),
    ("duration_months", True), ("duration_months", 12.0), ("duration_months", -1), ("duration_months", 1201),
    ("currency", "BTC"), ("currency", []), ("contribution_timing", "daily"), ("source", "bank"),
    ("sample_derived", "false"), ("name", "x"*81), ("schema_version", True), ("schema_version", 2),
    ("unknown", "anything"),
])
def test_invalid_inputs(key, value):
    data = payload()
    data[key] = value
    with pytest.raises(ScenarioError):
        SavingsScenario.from_mapping(data)


@pytest.mark.parametrize("currency,value,valid", [("JPY", "10.1", False), ("JPY", "10", True),
    ("KWD", "10.123", True), ("KWD", "10.1234", False)])
def test_input_currency_precision(currency, value, valid):
    data = payload(currency=currency)
    data["initial_balance"] = value
    if valid:
        assert SavingsScenario.from_mapping(data).currency == currency
    else:
        with pytest.raises(ScenarioError):
            SavingsScenario.from_mapping(data)


def test_defaults_required_fields_and_provenance():
    s = SavingsScenario.from_mapping(payload())
    assert s.currency == "USD" and s.contribution_timing == "end"
    assert SavingsScenario.from_mapping(payload(source="sample")).sample_derived
    data = payload(); del data["initial_balance"]
    with pytest.raises(ScenarioError) as exc:
        SavingsScenario.from_mapping(data)
    assert "initial_balance" in exc.value.errors
