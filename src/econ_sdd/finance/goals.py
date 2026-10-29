"""GOAL-M01: date-aware, complete-month savings goal solving."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Context, Decimal, DecimalException, ROUND_CEILING, ROUND_HALF_EVEN, localcontext
import re
from typing import Any, ClassVar

from .currencies import CURRENCIES, DEFAULT_CURRENCY
from .savings import (MAX_AMOUNT, MAX_MONTHS, PRECISION, CalculationUnavailable, ScenarioError,
                      SavingsProjection, SavingsScenario, _decimal, calculate_savings)

GOAL_MODEL_VERSION = "savings-goal-v1"


def anniversary(anchor: date, months: int) -> date:
    year, month = divmod(anchor.year * 12 + anchor.month - 1 + months, 12)
    month += 1
    return date(year, month, min(anchor.day, monthrange(year, month)[1]))


def complete_months(start: date, target: date) -> int:
    if target < start:
        raise ScenarioError({"target_date": "Choose a target date on or after the start date."})
    months = (target.year - start.year) * 12 + target.month - start.month
    if anniversary(start, months) > target:
        months -= 1
    if months > MAX_MONTHS:
        raise ScenarioError({"target_date": "Choose a deadline within 1,200 complete monthly periods."})
    return months


def _date_text(value: Any, field: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ScenarioError({field: "Enter a date in YYYY-MM-DD format."})
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ScenarioError({field: "Enter a valid calendar date."}) from None


@dataclass(frozen=True, slots=True)
class SavingsGoal:
    initial_balance: Decimal
    goal_amount: Decimal
    annual_effective_rate_percent: Decimal
    start_date: date
    target_date: date
    contribution_timing: str = "end"
    currency: str = DEFAULT_CURRENCY
    source: str = "manual"
    sample_derived: bool = False
    name: str = ""

    FIELDS: ClassVar[frozenset[str]] = frozenset({
        "schema_version", "calculation_mode", "initial_balance", "goal_amount",
        "annual_effective_rate_percent", "start_date", "target_date", "contribution_timing",
        "currency", "source", "sample_derived", "name",
    })

    def __post_init__(self):
        errors = {}
        try:
            base = SavingsScenario(self.initial_balance, Decimal(0), self.annual_effective_rate_percent, 0,
                                   self.contribution_timing, self.currency, self.source, self.sample_derived, self.name)
        except ScenarioError as exc:
            errors.update(exc.errors)
        if not isinstance(self.goal_amount, Decimal) or not self.goal_amount.is_finite():
            errors["goal_amount"] = "Enter a finite goal amount."
        elif not 0 <= self.goal_amount <= MAX_AMOUNT:
            errors["goal_amount"] = "Enter a goal between 0 and 1,000,000,000,000."
        elif isinstance(self.currency, str) and self.currency in CURRENCIES and self.goal_amount.as_tuple().exponent < -CURRENCIES[self.currency].minor_digits:
            errors["goal_amount"] = f"This currency supports at most {CURRENCIES[self.currency].minor_digits} decimal places."
        for field in ("start_date", "target_date"):
            if type(getattr(self, field)) is not date:
                errors[field] = "Enter a valid calendar date."
        if errors:
            raise ScenarioError(errors)
        complete_months(self.start_date, self.target_date)
        if base.sample_derived:
            object.__setattr__(self, "sample_derived", True)

    @classmethod
    def from_mapping(cls, data: Any) -> "SavingsGoal":
        if not isinstance(data, dict) or set(data) - cls.FIELDS:
            raise ScenarioError({"file": "Use a savings-goal object with supported fields."})
        if type(data.get("schema_version", 1)) is not int or data.get("schema_version", 1) != 1:
            raise ScenarioError({"file": "This goal schema version is not supported."})
        if data.get("calculation_mode", "goal") != "goal":
            raise ScenarioError({"file": "This calculation mode is not supported."})
        required = ("initial_balance", "goal_amount", "annual_effective_rate_percent", "start_date", "target_date")
        errors = {field: "This field is required." for field in required if field not in data}
        values = {}
        for field in required:
            if field not in data:
                continue
            try:
                values[field] = _date_text(data[field], field) if field.endswith("_date") else _decimal(data[field], field)
            except ScenarioError as exc:
                errors.update(exc.errors)
        if errors:
            raise ScenarioError(errors)
        return cls(**values, currency=data.get("currency", DEFAULT_CURRENCY),
                   contribution_timing=data.get("contribution_timing", "end"), source=data.get("source", "manual"),
                   sample_derived=data.get("sample_derived", False), name=data.get("name", ""))

    def as_record(self) -> dict:
        return {"schema_version": 1, "calculation_mode": "goal", "initial_balance": format(self.initial_balance, "f"),
                "goal_amount": format(self.goal_amount, "f"), "annual_effective_rate_percent": format(self.annual_effective_rate_percent, "f"),
                "start_date": self.start_date.isoformat(), "target_date": self.target_date.isoformat(),
                "contribution_timing": self.contribution_timing, "currency": self.currency,
                "source": self.source, "sample_derived": self.sample_derived, "name": self.name}


@dataclass(frozen=True, slots=True)
class GoalSolution:
    goal: SavingsGoal
    projection: SavingsProjection
    unrounded_monthly_contribution: Decimal
    modeled_end_date: date
    unused_days: int

    @property
    def required_monthly_contribution(self) -> Decimal:
        return self.projection.scenario.monthly_contribution

    @property
    def first_deposit_date(self) -> date | None:
        if not self.projection.scenario.duration_months or not self.required_monthly_contribution:
            return None
        return anniversary(self.goal.start_date, 1 if self.goal.contribution_timing == "end" else 0)

    @property
    def last_deposit_date(self) -> date | None:
        months = self.projection.scenario.duration_months
        if not months or not self.required_monthly_contribution:
            return None
        return anniversary(self.goal.start_date, months if self.goal.contribution_timing == "end" else months - 1)


def solve_goal(goal: SavingsGoal) -> GoalSolution:
    if not isinstance(goal, SavingsGoal):
        raise TypeError("A validated SavingsGoal is required.")
    months = complete_months(goal.start_date, goal.target_date)
    end = anniversary(goal.start_date, months)

    def forward(contribution: Decimal, *, principal: Decimal | None = None) -> SavingsProjection:
        return calculate_savings(SavingsScenario(goal.initial_balance if principal is None else principal, contribution,
            goal.annual_effective_rate_percent, months, goal.contribution_timing, goal.currency,
            goal.source, goal.sample_derived, goal.name))

    try:
        with localcontext(Context(prec=PRECISION, rounding=ROUND_HALF_EVEN)):
            base = forward(Decimal(0))
            if base.final.closing_balance >= goal.goal_amount:
                return GoalSolution(goal, base, Decimal(0), end, (goal.target_date - end).days)
            if months == 0:
                raise ScenarioError({"target_date": "Allow at least one complete month, or increase the starting balance to cover the goal."})
            factor = forward(Decimal(1), principal=Decimal(0)).final.closing_balance
            raw = (goal.goal_amount - base.final.closing_balance) / factor
            quantum = Decimal(1).scaleb(-CURRENCIES[goal.currency].minor_digits)
            cap = int(MAX_AMOUNT / quantum)
            high = min(cap, max(1, int((raw / quantum).to_integral_value(rounding=ROUND_CEILING))))
            if forward(high * quantum).final.closing_balance < goal.goal_amount:
                high = cap
                if forward(high * quantum).final.closing_balance < goal.goal_amount:
                    raise ScenarioError({"goal_amount": "The required monthly deposit exceeds this calculator's supported amount. Allow more time or adjust the goal."})
            low = 1
            while low < high:
                middle = (low + high) // 2
                if forward(middle * quantum).final.closing_balance >= goal.goal_amount:
                    high = middle
                else:
                    low = middle + 1
            projection = forward(low * quantum)
            if projection.final.closing_balance < goal.goal_amount or forward((low - 1) * quantum).final.closing_balance >= goal.goal_amount:
                raise CalculationUnavailable("A minimum monthly contribution could not be verified.")
            return GoalSolution(goal, projection, raw, end, (goal.target_date - end).days)
    except DecimalException:
        raise CalculationUnavailable("A savings-goal projection is unavailable for these assumptions.") from None
