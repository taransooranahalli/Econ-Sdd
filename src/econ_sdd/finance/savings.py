"""SAV-M01/M02: constant effective-rate savings, with local Decimal precision."""

from dataclasses import dataclass
from decimal import Context, Decimal, DecimalException, ROUND_HALF_EVEN, localcontext
import re
from fractions import Fraction
from typing import Any, ClassVar, Mapping

from .currencies import CURRENCIES, DEFAULT_CURRENCY

PRECISION = 80
MODEL_VERSION = "savings-v1"
SCHEMA_VERSION = 1
MAX_AMOUNT = Decimal("1000000000000")
MAX_MONTHS = 1200
DECIMAL_TEXT = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)\Z", re.ASCII)


class ScenarioError(ValueError):
    """Safe field-level messages; never includes raw submitted values."""

    def __init__(self, errors: Mapping[str, str]):
        self.errors = dict(errors)
        super().__init__("Please check the highlighted fields.")


class CalculationUnavailable(ArithmeticError):
    """A finite result could not be calculated within the model conventions."""


def _decimal(value: Any, field: str) -> Decimal:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ScenarioError({field: "Enter a decimal amount or rate as text."})
    if not DECIMAL_TEXT.fullmatch(value.strip()):
        raise ScenarioError({field: "Enter a finite decimal number without exponent notation."})
    return Decimal(value.strip())


@dataclass(frozen=True, slots=True)
class SavingsScenario:
    initial_balance: Decimal
    monthly_contribution: Decimal
    annual_effective_rate_percent: Decimal
    duration_months: int
    contribution_timing: str = "end"
    currency: str = DEFAULT_CURRENCY
    source: str = "manual"
    sample_derived: bool = False
    name: str = ""

    FIELDS: ClassVar[frozenset[str]] = frozenset({
        "schema_version", "initial_balance", "monthly_contribution",
        "annual_effective_rate_percent", "duration_months", "contribution_timing",
        "currency", "source", "sample_derived", "name",
    })

    def __post_init__(self) -> None:
        errors: dict[str, str] = {}
        if not isinstance(self.currency, str) or self.currency not in CURRENCIES:
            errors["currency"] = "Select a supported currency."
        minor_digits = CURRENCIES[self.currency].minor_digits if not errors else 2
        for field in ("initial_balance", "monthly_contribution"):
            value = getattr(self, field)
            if not isinstance(value, Decimal) or not value.is_finite():
                errors[field] = "Enter a finite decimal amount."
            elif value < 0 or value > MAX_AMOUNT:
                errors[field] = "Enter an amount between 0 and 1,000,000,000,000."
            elif value.as_tuple().exponent < -minor_digits:
                errors[field] = f"This currency supports at most {minor_digits} decimal places."
        rate = self.annual_effective_rate_percent
        if not isinstance(rate, Decimal) or not rate.is_finite():
            errors["annual_effective_rate_percent"] = "Enter a finite annual effective rate."
        elif rate < -99 or rate > 100:
            errors["annual_effective_rate_percent"] = "Enter a rate between −99% and 100%."
        elif rate.as_tuple().exponent < -24:
            errors["annual_effective_rate_percent"] = "Use at most 24 decimal places."
        if type(self.duration_months) is not int or not 0 <= self.duration_months <= MAX_MONTHS:
            errors["duration_months"] = "Enter a whole number of months from 0 to 1,200."
        if self.contribution_timing not in ("end", "beginning"):
            errors["contribution_timing"] = "Choose month end or month start."
        if self.source not in ("manual", "sample"):
            errors["source"] = "Source must be manual or sample."
        if type(self.sample_derived) is not bool:
            errors["sample_derived"] = "Sample provenance must be true or false."
        if not isinstance(self.name, str) or len(self.name) > 80 or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in self.name):
            errors["name"] = "Use a plain-text name of at most 80 characters."
        if errors:
            raise ScenarioError(errors)
        if self.source == "sample":
            object.__setattr__(self, "sample_derived", True)

    @classmethod
    def from_mapping(cls, data: Any) -> "SavingsScenario":
        if not isinstance(data, dict) or not all(isinstance(k, str) for k in data):
            raise ScenarioError({"file": "Use a scenario JSON object."})
        if set(data) - cls.FIELDS:
            raise ScenarioError({"file": "The scenario contains unsupported fields."})
        if type(data.get("schema_version", 1)) is not int or data.get("schema_version", 1) != 1:
            raise ScenarioError({"file": "This scenario schema version is not supported."})
        required = ("initial_balance", "monthly_contribution", "annual_effective_rate_percent", "duration_months")
        errors = {field: "This field is required." for field in required if field not in data}
        parsed: dict[str, Decimal] = {}
        for field in required[:3]:
            if field in data:
                try:
                    parsed[field] = _decimal(data[field], field)
                except ScenarioError as exc:
                    errors.update(exc.errors)
        if errors:
            raise ScenarioError(errors)
        return cls(
            **parsed, duration_months=data["duration_months"],
            contribution_timing=data.get("contribution_timing", "end"),
            currency=data.get("currency", DEFAULT_CURRENCY), source=data.get("source", "manual"),
            sample_derived=data.get("sample_derived", False), name=data.get("name", ""),
        )

    def as_record(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "initial_balance": format(self.initial_balance, "f"),
            "monthly_contribution": format(self.monthly_contribution, "f"),
            "annual_effective_rate_percent": format(self.annual_effective_rate_percent, "f"),
            "duration_months": self.duration_months,
            "contribution_timing": self.contribution_timing,
            "currency": self.currency, "source": self.source,
            "sample_derived": self.sample_derived, "name": self.name,
        }


@dataclass(frozen=True, slots=True)
class MonthlyRow:
    month_index: int
    closing_balance: Decimal
    recurring_deposits_to_date: Decimal
    total_deposited: Decimal
    period_interest: Decimal
    cumulative_interest: Decimal


@dataclass(frozen=True, slots=True)
class SavingsProjection:
    scenario: SavingsScenario
    monthly_rate: Decimal
    rows: tuple[MonthlyRow, ...]

    @property
    def final(self) -> MonthlyRow:
        return self.rows[-1]


def _perfect_twelfth_root(value: int) -> int | None:
    low, high = 0, 1 << ((value.bit_length() + 11) // 12)
    while low <= high:
        middle = (low + high) // 2
        power = middle ** 12
        if power == value:
            return middle
        if power < value:
            low = middle + 1
        else:
            high = middle - 1
    return None


def _monthly_rate(percent: Decimal) -> Decimal:
    # Exact rational roots protect genuine presentation ties from root roundoff.
    growth = Fraction(1) + Fraction(percent) / 100
    numerator = _perfect_twelfth_root(growth.numerator)
    denominator = _perfect_twelfth_root(growth.denominator)
    if numerator is not None and denominator is not None:
        return Decimal(numerator) / Decimal(denominator) - 1
    return (Decimal(1) + percent / 100) ** (Decimal(1) / 12) - 1


def calculate_savings(scenario: SavingsScenario) -> SavingsProjection:
    """Project monthly closing balances without rounding monthly interest to cash."""
    if not isinstance(scenario, SavingsScenario):
        raise TypeError("A validated SavingsScenario is required.")
    try:
        with localcontext(Context(prec=PRECISION, rounding=ROUND_HALF_EVEN)):
            rate = scenario.annual_effective_rate_percent / Decimal(100)
            monthly_rate = _monthly_rate(scenario.annual_effective_rate_percent) if rate else Decimal(0)
            balance = scenario.initial_balance
            contribution = scenario.monthly_contribution
            rows = [MonthlyRow(0, balance, Decimal(0), balance, Decimal(0), Decimal(0))]
            for month in range(1, scenario.duration_months + 1):
                previous = balance
                if scenario.contribution_timing == "beginning":
                    balance = (previous + contribution) * (1 + monthly_rate)
                else:
                    balance = previous * (1 + monthly_rate) + contribution
                if not contribution:
                    # Preserve the exact annual identity for lump-sum savings.
                    years, remaining = divmod(month, 12)
                    balance = scenario.initial_balance * (1 + rate) ** years * (1 + monthly_rate) ** remaining
                recurring = month * contribution
                total = scenario.initial_balance + recurring
                rows.append(MonthlyRow(month, balance, recurring, total,
                                       balance - previous - contribution, balance - total))
            if not all(row.closing_balance.is_finite() for row in rows):
                raise CalculationUnavailable("A finite projection is unavailable.")
            return SavingsProjection(scenario, monthly_rate, tuple(rows))
    except DecimalException as exc:
        raise CalculationUnavailable("A projection is unavailable for these assumptions.") from exc
