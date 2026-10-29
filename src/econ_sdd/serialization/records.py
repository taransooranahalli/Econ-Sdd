from datetime import datetime, timezone
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
import csv
import io
import json
import re
from typing import Any

from econ_sdd import __version__
from econ_sdd.finance.goals import GOAL_MODEL_VERSION, GoalSolution, SavingsGoal, anniversary
from econ_sdd.finance.savings import MODEL_VERSION, SCHEMA_VERSION, ScenarioError, SavingsProjection, SavingsScenario
from econ_sdd.presentation import amount_text, money_text

MAX_FILE_BYTES = 1024 * 1024
ROW_FIELDS = ("closing_balance", "recurring_deposits_to_date", "total_deposited", "period_interest", "cumulative_interest")


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ScenarioError({"file": "Duplicate JSON fields are not supported."})
        obj[key] = value
    return obj


def _invalid_constant(_value):
    raise ScenarioError({"file": "JSON values must be finite."})


def load_json(payload: bytes) -> Any:
    if len(payload) > MAX_FILE_BYTES:
        raise ScenarioError({"file": "Choose a JSON file no larger than 1 MiB."})
    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=_invalid_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ScenarioError):
            raise
        raise ScenarioError({"file": "Use one valid UTF-8 JSON object."}) from None
    if not isinstance(value, dict):
        raise ScenarioError({"file": "Use one scenario or exported-result JSON object."})
    return value


def legacy_rate_inputs(data: Any) -> Any:
    """Repair only bounded rate notation emitted by older supported models.

    Call only after checking a saved record's model version, never on manual inputs.
    The exponent bound prevents untrusted records from expanding enormous strings.
    """
    if not isinstance(data, dict):
        return data
    raw = data.get("annual_effective_rate_percent")
    if not isinstance(raw, str) or len(raw) > 128 or not re.fullmatch(r"[+-]?\d+(?:\.\d+)?E[+-]?\d{1,2}", raw):
        return data
    rate = Decimal(raw)
    if -24 <= rate.as_tuple().exponent <= 2 and -99 <= rate <= 100:
        return {**data, "annual_effective_rate_percent": format(rate, "f")}
    return data


def scenario_from_record(data: Any) -> SavingsScenario:
    if not isinstance(data, dict):
        raise ScenarioError({"file": "Use a scenario JSON object."})
    if "scenario" not in data:
        return SavingsScenario.from_mapping(data)
    if type(data.get("schema_version")) is not int or data.get("schema_version") != SCHEMA_VERSION:
        raise ScenarioError({"file": "This result schema version is not supported."})
    if data.get("model_version") != MODEL_VERSION:
        raise ScenarioError({"file": "This model version is not supported; a reviewed migration is required."})
    # Saved totals and rows are deliberately ignored and recomputed by the caller.
    return SavingsScenario.from_mapping(legacy_rate_inputs(data["scenario"]))


def projection_record(projection: SavingsProjection, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("The calculation timestamp must be timezone-aware.")
    s = projection.scenario
    return {
        "schema_version": SCHEMA_VERSION, "model_version": MODEL_VERSION, "app_version": __version__,
        "output_category": "conditional_projection",
        "calculated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "scenario": s.as_record(), "monthly_rate": str(projection.monthly_rate),
        "summary": {"ending_balance": str(projection.final.closing_balance),
                    "total_deposited": str(projection.final.total_deposited),
                    "interest": str(projection.final.cumulative_interest)},
        "assumptions": {"rate_convention": "annual_effective", "periods_per_year": 12,
                        "contribution_timing": s.contribution_timing, "money_basis": "nominal",
                        "taxes": "not_modeled", "fees": "not_modeled", "inflation": "not_modeled",
                        "fx_conversion": False},
        "rows": [{"month_index": row.month_index, **{key: str(getattr(row, key)) for key in ROW_FIELDS}}
                 for row in projection.rows],
    }


def display_record(projection: SavingsProjection) -> dict:
    currency = projection.scenario.currency
    with localcontext(Context(prec=80, rounding=ROUND_HALF_EVEN)):
        monthly_rate_display = format(projection.monthly_rate * 100, ".12f") + "%"
        share = (projection.final.cumulative_interest / projection.final.closing_balance * 100
                 if projection.final.closing_balance > 0 and projection.final.cumulative_interest >= 0 else Decimal(0))
        growth_share = format(share, ".0f")
    return {
        "monthly_rate_percent": monthly_rate_display,
        "growth_share_percent": growth_share,
        "balance_zero": projection.final.closing_balance == 0,
        "interest_negative": projection.final.cumulative_interest < 0,
        "summary": {"ending_balance": money_text(projection.final.closing_balance, currency),
                    "total_deposited": money_text(projection.final.total_deposited, currency),
                    "interest": money_text(projection.final.cumulative_interest, currency)},
        "rows": [{"month_index": row.month_index,
                  **{key: money_text(getattr(row, key), currency) for key in ROW_FIELDS}}
                 for row in projection.rows],
    }


def calculation_input(data: Any) -> SavingsScenario | SavingsGoal:
    if isinstance(data, dict) and (data.get("calculation_mode") == "goal" or "goal_amount" in data):
        return SavingsGoal.from_mapping(data)
    return SavingsScenario.from_mapping(data)


def calculation_from_record(data: Any) -> SavingsScenario | SavingsGoal:
    if isinstance(data, dict) and ("goal" in data or data.get("model_version") == GOAL_MODEL_VERSION):
        if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
            raise ScenarioError({"file": "This goal result schema version is not supported."})
        if data.get("model_version") != GOAL_MODEL_VERSION:
            raise ScenarioError({"file": "This goal model version is not supported; a reviewed migration is required."})
        return SavingsGoal.from_mapping(legacy_rate_inputs(data.get("goal")))
    if isinstance(data, dict) and "scenario" not in data:
        return calculation_input(data)
    return scenario_from_record(data)


def result_record(result: SavingsProjection | GoalSolution) -> dict:
    if isinstance(result, SavingsProjection):
        return projection_record(result)
    record = projection_record(result.projection)
    goal = result.goal
    with localcontext(Context(prec=80, rounding=ROUND_HALF_EVEN)):
        surplus = result.projection.final.closing_balance - goal.goal_amount
    record.update({"model_version": GOAL_MODEL_VERSION, "projection_model_version": MODEL_VERSION,
                   "calculation_mode": "goal", "goal": goal.as_record(), "goal_result": {
        "required_monthly_contribution": str(result.required_monthly_contribution),
        "unrounded_monthly_contribution": str(result.unrounded_monthly_contribution),
        "modeled_end_date": result.modeled_end_date.isoformat(), "unused_days": result.unused_days,
        "complete_months": result.projection.scenario.duration_months,
        "first_deposit_date": result.first_deposit_date.isoformat() if result.first_deposit_date else None,
        "last_deposit_date": result.last_deposit_date.isoformat() if result.last_deposit_date else None,
        "surplus": str(surplus), "goal_met": result.projection.final.closing_balance >= goal.goal_amount,
        "status": "no_additional_deposit" if not result.required_monthly_contribution else "monthly_deposits_required",
    }})
    record["assumptions"].update({"calendar_convention": "anchored_complete_months",
                                  "partial_month_interest": "not_modeled",
                                  "monthly_contribution_rounding": "up_to_minor_unit"})
    for row in record["rows"]:
        month = row["month_index"]
        row["closing_date"] = anniversary(goal.start_date, month).isoformat()
        row["deposit_date"] = (anniversary(goal.start_date, month if goal.contribution_timing == "end" else month - 1).isoformat()
                               if month and result.required_monthly_contribution else None)
    return record


def result_display(result: SavingsProjection | GoalSolution) -> dict:
    if isinstance(result, SavingsProjection):
        return display_record(result)
    display = display_record(result.projection)
    with localcontext(Context(prec=80, rounding=ROUND_HALF_EVEN)):
        surplus = result.projection.final.closing_balance - result.goal.goal_amount
    display["goal"] = {
        "required_monthly_contribution": money_text(result.required_monthly_contribution, result.goal.currency),
        "goal_amount": money_text(result.goal.goal_amount, result.goal.currency),
        "surplus": money_text(surplus, result.goal.currency),
    }
    return display


def export_json(projection: SavingsProjection | GoalSolution) -> str:
    return json.dumps(result_record(projection), ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def export_csv(projection: SavingsProjection | GoalSolution) -> str:
    result = projection
    record = result_record(result)
    projection = result.projection if isinstance(result, GoalSolution) else result
    s = projection.scenario
    metadata = {
        "currency": s.currency, "initial_balance": amount_text(s.initial_balance, s.currency),
        "monthly_contribution": amount_text(s.monthly_contribution, s.currency),
        "annual_effective_rate_percent": format(s.annual_effective_rate_percent, "f"),
        "duration_months": s.duration_months, "contribution_timing": s.contribution_timing,
        "rate_convention": "annual_effective", "output_category": "conditional_projection",
        "source": s.source, "sample_derived": str(s.sample_derived).lower(),
        "schema_version": SCHEMA_VERSION, "model_version": MODEL_VERSION,
        "app_version": __version__, "calculated_at_utc": record["calculated_at_utc"],
        "taxes": "not_modeled", "fees": "not_modeled", "inflation": "not_modeled",
    }
    date_fields = []
    if isinstance(result, GoalSolution):
        metadata.update({"model_version": GOAL_MODEL_VERSION, "projection_model_version": MODEL_VERSION,
            "calculation_mode": "goal", "goal_amount": amount_text(result.goal.goal_amount, s.currency),
            "start_date": result.goal.start_date.isoformat(), "target_date": result.goal.target_date.isoformat(),
            "modeled_end_date": result.modeled_end_date.isoformat(), "unused_days": result.unused_days,
            "required_monthly_contribution": amount_text(result.required_monthly_contribution, s.currency),
            "calendar_convention": "anchored_complete_months", "partial_month_interest": "not_modeled"})
        date_fields = ["closing_date", "deposit_date"]
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=["month_index", *date_fields, *ROW_FIELDS, *metadata.keys()], lineterminator="\n")
    writer.writeheader()
    for row in projection.rows:
        writer.writerow({"month_index": row.month_index,
                         **{key: record["rows"][row.month_index][key] or "" for key in date_fields},
                         **{key: amount_text(getattr(row, key), s.currency) for key in ROW_FIELDS}, **metadata})
    return out.getvalue()
