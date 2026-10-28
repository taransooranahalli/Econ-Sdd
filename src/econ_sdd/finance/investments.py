"""INV-M01/M02: manual total-return projection, monthly fees and purchasing power."""
from dataclasses import dataclass, fields
from decimal import Context, Decimal, DecimalException, ROUND_HALF_EVEN, localcontext
from typing import Any, ClassVar

from .savings import (PRECISION, CalculationUnavailable, ScenarioError, SavingsScenario,
                      _decimal, _monthly_rate, calculate_savings)

MODEL_VERSION = 'investment-growth-v1'
ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class InvestmentScenario:
    initial_balance: Decimal
    monthly_contribution: Decimal
    annual_return_percent: Decimal
    annual_fee_percent: Decimal
    annual_inflation_percent: Decimal
    duration_months: int
    contribution_timing: str = 'end'
    currency: str = 'USD'
    source: str = 'manual'
    sample_derived: bool = False
    name: str = ''

    FIELDS: ClassVar[frozenset[str]] = frozenset({
        'schema_version', 'calculation_mode', 'initial_balance', 'monthly_contribution',
        'annual_return_percent', 'annual_fee_percent', 'annual_inflation_percent',
        'duration_months', 'contribution_timing', 'currency', 'source', 'sample_derived', 'name'})

    def savings_scenario(self) -> SavingsScenario:
        return SavingsScenario(self.initial_balance, self.monthly_contribution, self.annual_return_percent,
                               self.duration_months, self.contribution_timing, self.currency,
                               self.source, self.sample_derived, self.name)

    def __post_init__(self) -> None:
        errors = {}
        try:
            self.savings_scenario()
        except ScenarioError as exc:
            errors.update({('annual_return_percent' if k == 'annual_effective_rate_percent' else k): v
                           for k, v in exc.errors.items()})
        for field, low, high in [('annual_fee_percent', 0, 100), ('annual_inflation_percent', -99, 100)]:
            value = getattr(self, field)
            if not isinstance(value, Decimal) or not value.is_finite():
                errors[field] = 'Enter a finite decimal percentage.'
            elif not low <= value <= high:
                errors[field] = f'Enter a percentage from {low} to {high}.'
            elif value.as_tuple().exponent < -24:
                errors[field] = 'Use at most 24 decimal places.'
        if errors:
            raise ScenarioError(errors)
        if self.source == 'sample':
            object.__setattr__(self, 'sample_derived', True)

    @classmethod
    def from_mapping(cls, data: Any) -> 'InvestmentScenario':
        if not isinstance(data, dict) or not all(isinstance(k, str) for k in data) or set(data) - cls.FIELDS:
            raise ScenarioError({'file': 'Use an investment scenario with supported fields.'})
        if type(data.get('schema_version', 1)) is not int or data.get('schema_version', 1) != 1:
            raise ScenarioError({'file': 'This investment schema version is not supported.'})
        if data.get('calculation_mode', 'investment_growth') != 'investment_growth':
            raise ScenarioError({'file': 'Choose an investment growth scenario.'})
        required = ('initial_balance', 'monthly_contribution', 'annual_return_percent',
                    'annual_fee_percent', 'annual_inflation_percent', 'duration_months')
        errors = {key: 'This field is required.' for key in required if key not in data}
        parsed = {}
        for key in required[:-1]:
            if key in data:
                try:
                    parsed[key] = _decimal(data[key], key)
                except ScenarioError as exc:
                    errors.update(exc.errors)
        if errors:
            raise ScenarioError(errors)
        return cls(**parsed, duration_months=data['duration_months'],
                   **{key: data[key] for key in ('contribution_timing', 'currency', 'source', 'sample_derived', 'name')
                      if key in data})

    def as_record(self) -> dict:
        return {'schema_version': 1, 'calculation_mode': 'investment_growth',
                **{field.name: format(getattr(self, field.name), 'f') if isinstance(getattr(self, field.name), Decimal)
                   else getattr(self, field.name) for field in fields(self)}}


@dataclass(frozen=True, slots=True)
class InvestmentRow:
    month_index: int
    contribution: Decimal
    total_contributed: Decimal
    gross_gain: Decimal
    fee: Decimal
    cumulative_fees: Decimal
    closing_balance: Decimal
    no_fee_balance: Decimal
    net_gain: Decimal


@dataclass(frozen=True, slots=True)
class InvestmentProjection:
    scenario: InvestmentScenario
    monthly_growth_factor: Decimal
    monthly_fee_fraction: Decimal
    rows: tuple[InvestmentRow, ...]
    purchasing_power: Decimal
    fee_impact: Decimal

    @property
    def final(self) -> InvestmentRow:
        return self.rows[-1]


def calculate_investments(scenario: InvestmentScenario) -> InvestmentProjection:
    if not isinstance(scenario, InvestmentScenario):
        raise TypeError('A validated InvestmentScenario is required.')
    try:
        with localcontext(Context(prec=PRECISION, rounding=ROUND_HALF_EVEN)):
            no_fee = calculate_savings(scenario.savings_scenario())
            g = 1 + no_fee.monthly_rate
            a = scenario.annual_fee_percent / 1200
            p, c = scenario.initial_balance, scenario.monthly_contribution
            balance, fees = p, ZERO
            rows = [InvestmentRow(0, p, p, ZERO, ZERO, ZERO, p, p, ZERO)]
            for t in range(1, scenario.duration_months + 1):
                invested = balance + c if scenario.contribution_timing == 'beginning' else balance
                fee = invested * g * a
                closing = invested * g - fee + (c if scenario.contribution_timing == 'end' else ZERO)
                if not a:
                    closing = no_fee.rows[t].closing_balance
                elif not c:
                    # Annual return identity protects lump-sum presentation ties.
                    years, remainder = divmod(t, 12)
                    closing = p * (1 + scenario.annual_return_percent / 100) ** years * g ** remainder * (1-a) ** t
                gross_gain = closing - balance - c + fee
                fees += fee
                balance = closing
                total = p + t*c
                rows.append(InvestmentRow(t, c, total, gross_gain, fee, fees, balance,
                                          no_fee.rows[t].closing_balance, balance-total))
            years, remainder = divmod(scenario.duration_months, 12)
            inflation_factor = ((1 + scenario.annual_inflation_percent / 100) ** years
                                * (1 + _monthly_rate(scenario.annual_inflation_percent)) ** remainder)
            purchasing_power = balance / inflation_factor
            fee_impact = no_fee.final.closing_balance - balance
            if not all(v.is_finite() for row in rows for v in (
                    row.closing_balance, row.fee, row.gross_gain, row.cumulative_fees)) or not purchasing_power.is_finite():
                raise CalculationUnavailable('A finite investment projection is unavailable.')
            return InvestmentProjection(scenario, g, a, tuple(rows), purchasing_power, fee_impact)
    except DecimalException as exc:
        raise CalculationUnavailable('The investment projection is unavailable for these assumptions.') from exc
