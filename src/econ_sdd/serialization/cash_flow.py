"""Versioned cash flow records and safe, explicit downloads."""

import csv
from datetime import datetime, timezone
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
import io
import json
from typing import Any

from econ_sdd import __version__
from econ_sdd.finance.cash_flow import CASH_FLOW_MODEL_VERSION, CashFlowBudget, CashFlowResult
from econ_sdd.finance.savings import PRECISION, ScenarioError
from econ_sdd.presentation import amount_text, money_text


def budget_from_record(data: Any) -> CashFlowBudget:
    if not isinstance(data, dict):
        raise ScenarioError({"file": "Choose a cash flow JSON budget."})
    if "budget" in data or "model_version" in data:
        if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
            raise ScenarioError({"file": "This cash flow result schema version is not supported."})
        if data.get("model_version") != CASH_FLOW_MODEL_VERSION:
            raise ScenarioError({"file": "Choose a cash-flow-v1 file; open savings files in Savings."})
        return CashFlowBudget.from_mapping(data.get("budget"))
    return CashFlowBudget.from_mapping(data)


def percent_text(value: Decimal | None) -> str:
    if value is None:
        return "Not applicable"
    with localcontext(Context(prec=PRECISION, rounding=ROUND_HALF_EVEN)):
        return format(value, ".2f") + "%"


def cash_flow_record(result: CashFlowResult) -> dict:
    return {"schema_version": 1, "model_version": CASH_FLOW_MODEL_VERSION, "app_version": __version__,
            "output_category": "monthly_budget_calculation", "calculated_at_utc": datetime.now(timezone.utc).isoformat(),
            "budget": result.budget.as_record(), "summary": {
                "total_income": str(result.total_income), "total_expenses": str(result.total_expenses),
                "net_cash_flow": str(result.net_cash_flow), "status": result.status,
                "spending_share_percent": str(result.spending_share_percent) if result.spending_share_percent is not None else None},
            "expense_breakdown": [{"label": item.label, "amount": str(item.amount),
                                   "share_percent": str(share) if share is not None else None}
                                  for item, share in zip(result.budget.expenses, result.expense_shares_percent)],
            "assumptions": {"period": "monthly", "income_basis": "take_home", "own_account_transfers": "excluded",
                            "frequency_conversion": False, "daily_timing": "not_modeled", "interest": "not_modeled",
                            "tax_calculation": "not_modeled", "inflation": "not_modeled", "fx_conversion": False}}


def cash_flow_display(result: CashFlowResult) -> dict:
    currency = result.budget.currency
    return {"summary": {field: money_text(getattr(result, field), currency)
                         for field in ("total_income", "total_expenses", "net_cash_flow")},
            "spending_share_percent": percent_text(result.spending_share_percent),
            "income": [{"label": item.label, "amount": money_text(item.amount, currency)} for item in result.budget.income],
            "expenses": [{"label": item.label, "amount": money_text(item.amount, currency), "share_percent": percent_text(share)}
                         for item, share in zip(result.budget.expenses, result.expense_shares_percent)]}


def export_cash_flow_json(result: CashFlowResult) -> str:
    return json.dumps(cash_flow_record(result), ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _safe_cell(text: str) -> str:
    # Protect user-authored text from spreadsheet formula interpretation.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def export_cash_flow_csv(result: CashFlowResult) -> str:
    record = cash_flow_record(result)
    budget = result.budget
    metadata = {"currency": budget.currency, "total_income": amount_text(result.total_income, budget.currency),
                "total_expenses": amount_text(result.total_expenses, budget.currency),
                "net_cash_flow": amount_text(result.net_cash_flow, budget.currency), "status": result.status,
                "source": budget.source, "sample_derived": str(budget.sample_derived).lower(), "name": _safe_cell(budget.name),
                "schema_version": 1, "model_version": CASH_FLOW_MODEL_VERSION, "app_version": __version__,
                "output_category": record["output_category"], "calculated_at_utc": record["calculated_at_utc"],
                **record["assumptions"]}
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["type", "category", "amount", *metadata], lineterminator="\n")
    writer.writeheader()
    for group in ("income", "expenses"):
        for item in getattr(budget, group):
            writer.writerow({"type": "expense" if group == "expenses" else "income", "category": _safe_cell(item.label),
                             "amount": amount_text(item.amount, budget.currency), **metadata})
    return output.getvalue()
