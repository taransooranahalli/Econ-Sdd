"""PORT-M01 independent arithmetic, definitions and unavailable-state checks."""
from copy import deepcopy
from datetime import date
from decimal import Context, Decimal, getcontext, localcontext
from fractions import Fraction
from uuid import UUID

import pytest

from econ_sdd.finance.portfolios import PortfolioDefinition, PricePoint, value_portfolio
from econ_sdd.finance.savings import ScenarioError
from econ_sdd.portfolio_service import example_definition
from econ_sdd.serialization.portfolios import definition_record, definition_from_record, export_definition, valuation_record

DAY=date(2026,10,29)


def definition(**changes):
    data=example_definition(DAY).as_record()
    data.update(changes)
    return PortfolioDefinition.from_mapping(data)


def prices(d,**changes):
    return {h.instrument.id:PricePoint(Decimal('120.40') if i==0 else Decimal('80'),DAY,'synthetic',
             'Fictional fixture','none',price_kind='daily_close' if d.pricing_mode=='daily' else 'eligible_trade',**changes)
            for i,h in enumerate(d.holdings)}


def test_documented_holdings_and_gain_reference_use_independent_rational_arithmetic():
    d=definition();r=value_portfolio(d,prices(d),DAY)
    exact_values=[Fraction('10.5')*Fraction('120.40'),Fraction(4)*Fraction(80)]
    exact_total=sum(exact_values)+Fraction('415.80')
    assert r.total==Decimal(exact_total.numerator)/Decimal(exact_total.denominator)==Decimal('2000')
    assert [x.value for x in r.rows]==[Decimal('1264.20'),Decimal('320')]
    assert [x.weight for x in r.rows]==[Decimal('63.21'),Decimal('16')]
    assert r.cash_weight==Decimal('20.79')
    assert [x.gain for x in r.rows]==[Decimal('164.20'),Decimal('-40')]
    assert r.gain==Decimal('124.20') and r.priced_count==2 and r.state=='synthetic'


def test_nonterminating_weights_use_independent_110_digit_fraction_reference():
    data=definition().as_record();data['cash']='0';data['holdings'][0]['shares']='1';data['holdings'][1]['shares']='2'
    d=PortfolioDefinition.from_mapping(data);r=value_portfolio(d,prices(d),DAY)
    expected=Fraction('120.4')/(Fraction('120.4')+160)*100
    with localcontext(Context(prec=110)):
        reference=Decimal(expected.numerator)/Decimal(expected.denominator)
        assert abs(r.rows[0].weight-reference)<Decimal('1e-65')


def test_decimal_context_isolation_and_display_tie():
    before=getcontext().copy();d=definition()
    p=prices(d);first=d.holdings[0].instrument.id;p[first]=PricePoint(Decimal('1.005'),DAY,'synthetic','Fictional fixture','none')
    value_portfolio(d,p,DAY)
    assert getcontext().prec==before.prec and getcontext().rounding==before.rounding


def test_missing_price_prevents_total_and_all_portfolio_weights():
    d=definition();p=prices(d);p.pop(d.holdings[1].instrument.id)
    r=value_portfolio(d,p,DAY)
    assert r.total is None and r.securities is None and r.cash_weight is None
    assert r.known_subtotal==Decimal('1680') and r.priced_count==1 and r.state=='partial'
    assert all(row.weight is None for row in r.rows)
    assert r.gain is None and r.rows[0].gain==Decimal('164.20')


@pytest.mark.parametrize('change',[{'quantities_confirmed':False},{'as_of_date':'2026-10-28'}])
def test_share_basis_review_withholds_holding_values(change):
    d=definition(**change);r=value_portfolio(d,prices(d),DAY)
    assert r.total is None and r.known_subtotal==Decimal('415.80') and r.state=='needs_review'
    assert all(row.state=='needs_review' for row in r.rows)


def test_old_price_share_basis_never_uses_current_quantities():
    d=definition();p=prices(d);first=d.holdings[0].instrument.id
    p[first]=PricePoint(Decimal('120.4'),date(2026,10,28),'closed','Fictional fixture','none')
    r=value_portfolio(d,p,DAY)
    assert r.rows[0].value is None and r.total is None and r.priced_count==1


def test_missing_cost_is_distinct_from_zero_and_gains_exclude_cash():
    data=definition().as_record();data['holdings'][1]['cost_basis']=None
    d=PortfolioDefinition.from_mapping(data);r=value_portfolio(d,prices(d),DAY)
    assert r.cost_count==1 and r.gain is None and r.rows[1].gain is None
    data['holdings'][1]['cost_basis']='0';d=PortfolioDefinition.from_mapping(data);r=value_portfolio(d,prices(d),DAY)
    assert r.rows[1].gain==Decimal(320) and r.rows[1].gain_percent is None
    assert r.gain==Decimal('484.20')
    with localcontext(Context(prec=110)):
        assert abs(r.gain_percent-Decimal(2421)/55)<Decimal('1e-65')


def test_cash_only_and_empty_definitions_have_no_network_or_false_returns():
    d=definition(holdings=[],cash='100',quantities_confirmed=False)
    r=value_portfolio(d,{},DAY)
    assert r.total==100 and r.cash_weight==100 and r.state=='cash_only' and r.gain is None
    r=value_portfolio(definition(holdings=[],cash='0',quantities_confirmed=False),{},DAY)
    assert r.total==0 and r.cash_weight is None and r.state=='empty'


@pytest.mark.parametrize('field,value',[('cash',''),('cash','1e3'),('cash',True),('cash','-1'),('cash','0.001'),('cash','1000000000001'),
    ('currency','EUR'),('schema_version',True),('schema_version',2),('pricing_mode','sip'),('quantities_confirmed','true'),('as_of_date','2026-02-30')])
def test_definition_bounds_and_strict_types(field,value):
    data=definition().as_record();data[field]=value
    with pytest.raises(ScenarioError):PortfolioDefinition.from_mapping(data)


@pytest.mark.parametrize('field,value',[('shares','0'),('shares','-1'),('shares','0.0000001'),('shares','1000000001'),
    ('shares',1.5),('cost_basis',''),('cost_basis','NaN'),('cost_basis','1000000000001'),('cost_basis','1.001')])
def test_holding_share_and_cost_bounds(field,value):
    data=definition().as_record();data['holdings'][0][field]=value
    with pytest.raises(ScenarioError):PortfolioDefinition.from_mapping(data)


def test_duplicate_and_oversized_holdings_rejected_and_large_valid_case_exact():
    data=definition().as_record();data['holdings'].append(deepcopy(data['holdings'][0]))
    with pytest.raises(ScenarioError):PortfolioDefinition.from_mapping(data)
    data=definition().as_record();data['holdings']*=11
    with pytest.raises(ScenarioError):PortfolioDefinition.from_mapping(data)
    data=definition().as_record();data['holdings'][0]['shares']='1000000000';data['cash']='1000000000000'
    d=PortfolioDefinition.from_mapping(data);p=prices(d)
    p[d.holdings[0].instrument.id]=PricePoint(Decimal('1000000000000'),DAY,'synthetic','Fictional fixture','none')
    r=value_portfolio(d,p,DAY)
    assert r.total==Decimal('1000000001000000000320')


@pytest.mark.parametrize('update',[{'provider':'Other'},{'feed':'sip'},{'currency':'EUR'},{'adjustment':'split'},{'price_kind':'daily_close'}])
def test_mixed_or_adjusted_price_sources_rejected(update):
    d=definition();p=prices(d);original=p[d.holdings[0].instrument.id]
    from dataclasses import replace
    p[d.holdings[0].instrument.id]=replace(original,**update)
    with pytest.raises(ScenarioError):value_portfolio(d,p,DAY)


@pytest.mark.parametrize('value',[Decimal(0),Decimal(-1),Decimal('NaN'),Decimal('Infinity'),Decimal('1000000000001')])
def test_invalid_captured_prices_never_create_values(value):
    from dataclasses import replace
    d=definition();p=prices(d);identity=d.holdings[0].instrument.id;p[identity]=replace(p[identity],price=value)
    with pytest.raises(ScenarioError):value_portfolio(d,p,DAY)


def test_definition_export_omits_prices_and_import_discards_tampered_results():
    d=definition();record=definition_record(d)
    record.update({'summary':{'total':'999999999'},'capture_id':'forged','rows':[{'price':'999'}]})
    restored=definition_from_record(record)
    assert restored==d
    exported=export_definition(d)
    assert 'capture_id' not in exported and '"rows"' not in exported and '"summary"' not in exported
    assert '"prices_omitted": true' in exported and definition_record(restored)['status']=='unpriced'
    record['model_version']='portfolio-v999'
    with pytest.raises(ScenarioError):definition_from_record(record)


def test_unavailable_or_unknown_positive_price_state_is_not_valued():
    from dataclasses import replace
    d=definition();p=prices(d);identity=d.holdings[0].instrument.id
    p[identity]=replace(p[identity],state='needs_review')
    with pytest.raises(ScenarioError):value_portfolio(d,p,DAY)


def test_display_money_ties_are_half_even_after_unrounded_share_multiplication():
    from econ_sdd.presentation import money_text
    data=definition().as_record();data['holdings'][0]['shares']='1'
    d=PortfolioDefinition.from_mapping(data);p=prices(d)
    p[d.holdings[0].instrument.id]=PricePoint(Decimal('1.005'),DAY,'synthetic','Fictional fixture','none')
    r=value_portfolio(d,p,DAY)
    assert r.rows[0].value==Decimal('1.005') and money_text(r.rows[0].value,'USD')=='$1.00'
