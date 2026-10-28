"""Versioned investment files; original inputs are always revalidated/recalculated."""
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import io
import json

from econ_sdd import __version__
from econ_sdd.finance.investments import MODEL_VERSION, InvestmentScenario, InvestmentProjection
from econ_sdd.finance.savings import ScenarioError
from econ_sdd.presentation import amount_text, money_text

ASSUMPTIONS = {'return': 'annual_effective_total_return_with_distributions_reinvested',
               'fee': 'annual_nominal_rate_divided_by_12_on_post_return_balance',
               'inflation': 'annual_effective_deflator', 'contributions': 'constant_nominal',
               'period': 'equal_months', 'tax': 'not_modeled', 'fx_conversion': False,
               'uncertainty': 'not_modeled', 'market_data': 'none'}
SUMMARY_FIELDS = ('ending_balance', 'total_contributed', 'net_gain', 'cumulative_fees',
                  'no_fee_balance', 'fee_impact', 'purchasing_power')


def scenario_from_record(data) -> InvestmentScenario:
    if not isinstance(data, dict):
        raise ScenarioError({'file': 'Choose an investment growth JSON scenario.'})
    if 'scenario' in data or 'model_version' in data:
        if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
            raise ScenarioError({'file': 'This investment result schema version is not supported.'})
        if data.get('model_version') != MODEL_VERSION:
            raise ScenarioError({'file': 'Open an investment-growth-v1 file in Investments.'})
        return InvestmentScenario.from_mapping(data.get('scenario'))
    return InvestmentScenario.from_mapping(data)


def investment_record(result: InvestmentProjection) -> dict:
    last = result.final
    summary = dict(zip(SUMMARY_FIELDS, (last.closing_balance, last.total_contributed, last.net_gain,
                                      last.cumulative_fees, last.no_fee_balance, result.fee_impact,
                                      result.purchasing_power)))
    return {'schema_version': 1, 'model_version': MODEL_VERSION, 'app_version': __version__,
            'output_category': 'conditional_projection', 'calculated_at_utc': datetime.now(timezone.utc).isoformat(),
            'scenario': result.scenario.as_record(), 'summary': {key: str(v) for key, v in summary.items()},
            'monthly_growth_factor': str(result.monthly_growth_factor),
            'monthly_fee_fraction': str(result.monthly_fee_fraction),
            'rows': [{key: value if key == 'month_index' else str(value) for key, value in asdict(row).items()}
                     for row in result.rows],
            'assumptions': {**ASSUMPTIONS, 'contribution_timing': result.scenario.contribution_timing}}


def investment_display(result: InvestmentProjection) -> dict:
    record = investment_record(result)
    currency = result.scenario.currency
    from decimal import Decimal
    return {'summary': {key: money_text(Decimal(value), currency) for key, value in record['summary'].items()},
            'rows': [{key: value if key == 'month_index' else money_text(Decimal(value), currency)
                      for key, value in row.items()} for row in record['rows']]}


def export_investment_json(result: InvestmentProjection) -> str:
    # Compact records keep all 1,201 full-precision rows within the import size cap.
    return json.dumps(investment_record(result), ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n'


def export_investment_csv(result: InvestmentProjection) -> str:
    record = investment_record(result)
    metadata = {key: value for key, value in record['scenario'].items() if key != 'name'}
    metadata.update({key: record[key] for key in ('model_version', 'app_version', 'output_category', 'calculated_at_utc')})
    metadata.update(record['assumptions'])
    metadata['start_period_purchasing_power'] = amount_text(result.purchasing_power, result.scenario.currency)
    metadata['fee_impact_on_ending_value'] = amount_text(result.fee_impact, result.scenario.currency)
    output = io.StringIO(newline='')
    row_fields = list(asdict(result.rows[0]))
    writer = csv.DictWriter(output, fieldnames=[*row_fields, *metadata], lineterminator='\n')
    writer.writeheader()
    for row in result.rows:
        writer.writerow({**{key: value if key == 'month_index' else amount_text(value, result.scenario.currency)
                            for key, value in asdict(row).items()}, **metadata})
    return output.getvalue()
