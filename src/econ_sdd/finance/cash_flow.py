"""CF-M01: monthly budget arithmetic, independent of UI and persistence."""

from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from typing import Any, ClassVar

from .currencies import CURRENCIES, DEFAULT_CURRENCY
from .savings import DECIMAL_TEXT, MAX_AMOUNT, PRECISION, ScenarioError

CASH_FLOW_MODEL_VERSION = "cash-flow-v1"
MAX_ITEMS = 50


def plain_text(value: Any, *, required: bool = False) -> bool:
    return (isinstance(value, str) and len(value) <= 80
            and (not required or bool(value.strip()))
            and not any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF for c in value))


@dataclass(frozen=True, slots=True)
class CashFlowItem:
    label: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class CashFlowBudget:
    income: tuple[CashFlowItem, ...]
    expenses: tuple[CashFlowItem, ...]
    currency: str = DEFAULT_CURRENCY
    source: str = "manual"
    sample_derived: bool = False
    name: str = ""

    FIELDS: ClassVar[frozenset[str]] = frozenset({
        "schema_version", "calculation_mode", "income", "expenses", "currency", "source", "sample_derived", "name",
    })

    def __post_init__(self):
        errors = {}
        if not isinstance(self.currency, str) or self.currency not in CURRENCIES:
            errors["currency"] = "Select a supported currency."
        digits = CURRENCIES[self.currency].minor_digits if not errors else 2
        for group in ("income", "expenses"):
            items = getattr(self, group)
            if not isinstance(items, tuple) or not 1 <= len(items) <= MAX_ITEMS:
                errors[group] = "Use between 1 and 50 categories; enter zero explicitly if none apply."
                continue
            for index, item in enumerate(items):
                key = f"{group}.{index}"
                if not isinstance(item, CashFlowItem):
                    errors[key] = "Use a labeled amount."
                    continue
                if not plain_text(item.label, required=True):
                    errors[key + ".label"] = "Enter a plain-text category of 1 to 80 characters."
                amount = item.amount
                if not isinstance(amount, Decimal) or not amount.is_finite():
                    errors[key + ".amount"] = "Enter a finite decimal amount."
                elif amount < 0 or amount > MAX_AMOUNT:
                    errors[key + ".amount"] = "Enter an amount between 0 and 1,000,000,000,000."
                elif amount.as_tuple().exponent < -digits:
                    errors[key + ".amount"] = f"This currency supports at most {digits} decimal places."
        if self.source not in ("manual", "sample"):
            errors["source"] = "Source must be manual or sample."
        if type(self.sample_derived) is not bool:
            errors["sample_derived"] = "Sample provenance must be true or false."
        if not plain_text(self.name):
            errors["name"] = "Use a plain-text name of at most 80 characters."
        if errors:
            raise ScenarioError(errors)
        if self.source == "sample":
            object.__setattr__(self, "sample_derived", True)

    @classmethod
    def from_mapping(cls, data: Any) -> "CashFlowBudget":
        if not isinstance(data, dict) or set(data) - cls.FIELDS:
            raise ScenarioError({"file": "Use a cash flow budget with supported fields."})
        if type(data.get("schema_version", 1)) is not int or data.get("schema_version", 1) != 1:
            raise ScenarioError({"file": "This cash flow schema version is not supported."})
        if data.get("calculation_mode", "cash_flow") != "cash_flow":
            raise ScenarioError({"file": "Open this file in its matching calculator."})
        errors, groups = {}, {}
        for group in ("income", "expenses"):
            items = data.get(group)
            if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
                errors[group] = "Use between 1 and 50 categories; enter zero explicitly if none apply."
                continue
            parsed = []
            for index, item in enumerate(items):
                key = f"{group}.{index}"
                if not isinstance(item, dict) or set(item) != {"label", "amount"}:
                    errors[key] = "Each category needs a label and amount, with no additional fields."
                    continue
                value = item["amount"]
                if (not isinstance(value, str) or len(value) > 128
                        or not DECIMAL_TEXT.fullmatch(value.strip())):
                    errors[key + ".amount"] = "Enter a decimal amount without exponent notation; use zero explicitly."
                    continue
                parsed.append(CashFlowItem(item["label"], Decimal(value.strip())))
            groups[group] = tuple(parsed)
        if errors:
            raise ScenarioError(errors)
        return cls(**groups, currency=data.get("currency", DEFAULT_CURRENCY), source=data.get("source", "manual"),
                   sample_derived=data.get("sample_derived", False), name=data.get("name", ""))

    def as_record(self) -> dict:
        return {"schema_version": 1, "calculation_mode": "cash_flow", "currency": self.currency,
                "source": self.source, "sample_derived": self.sample_derived, "name": self.name,
                **{group: [{"label": item.label, "amount": str(item.amount)} for item in getattr(self, group)]
                   for group in ("income", "expenses")}}


@dataclass(frozen=True, slots=True)
class CashFlowResult:
    budget: CashFlowBudget
    total_income: Decimal
    total_expenses: Decimal
    net_cash_flow: Decimal
    spending_share_percent: Decimal | None
    expense_shares_percent: tuple[Decimal | None, ...]

    @property
    def status(self) -> str:
        return "surplus" if self.net_cash_flow > 0 else "shortfall" if self.net_cash_flow < 0 else "balanced"


def calculate_cash_flow(budget: CashFlowBudget) -> CashFlowResult:
    if not isinstance(budget, CashFlowBudget):
        raise TypeError("A validated CashFlowBudget is required.")
    with localcontext(Context(prec=PRECISION, rounding=ROUND_HALF_EVEN)):
        income = sum((item.amount for item in budget.income), Decimal(0))
        expenses = sum((item.amount for item in budget.expenses), Decimal(0))
        return CashFlowResult(budget, income, expenses, income - expenses,
                              expenses / income * 100 if income else None,
                              tuple(item.amount / expenses * 100 if expenses else None for item in budget.expenses))
