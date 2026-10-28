"""Independent cash-flow sums and exact rationals, not copies of the monthly loop."""
from decimal import Decimal as D, getcontext, localcontext
from fractions import Fraction as F
import random
import pytest

from econ_sdd.finance.investments import InvestmentScenario, calculate_investments
from econ_sdd.finance.savings import ScenarioError, calculate_savings
from econ_sdd.presentation import amount_text


def inputs(**updates):
    data = dict(initial_balance='1000', monthly_contribution='100', annual_return_percent='5',
                annual_fee_percent='1.2', annual_inflation_percent='2', duration_months=12)
    return {**data, **updates}


def project(**updates):
    return calculate_investments(InvestmentScenario.from_mapping(inputs(**updates)))


def close(actual, expected):
    with localcontext() as ctx:
        ctx.prec = 110
        assert abs(actual-expected) <= max(D('1e-65'), abs(expected)*D('1e-65'))


@pytest.mark.parametrize('timing', ['end', 'beginning'])
def test_exact_fraction_cash_flows_and_cost_accounting(timing):
    rate='12.6825030131969720661201'
    result=project(annual_return_percent=rate,annual_inflation_percent=rate,contribution_timing=timing)
    g=F(101,100);q=g*F(999,1000)
    expected=1000*q**12+100*sum(q**k for k in range(0 if timing=='end' else 1,12 if timing=='end' else 13))
    start=0 if timing=='end' else 1
    exact_fees=sum((1000*q**k+100*sum((q**j for j in range(start,k+start)),F(0))
                    +(100 if timing=='beginning' else 0))*g*F(1,1000) for k in range(12))
    with localcontext() as ctx:
        ctx.prec=110
        close(result.final.cumulative_fees,D(exact_fees.numerator)/D(exact_fees.denominator))
        close(result.final.closing_balance,D(expected.numerator)/D(expected.denominator))
        close(sum((row.gross_gain-row.fee for row in result.rows),D(0)),result.final.net_gain)
    if timing=='end':
        assert [amount_text(v,'USD') for v in [result.final.closing_balance,result.final.cumulative_fees,
               result.final.no_fee_balance,result.fee_impact,result.purchasing_power]]==['2374.53','19.61','2395.08','20.55','2107.27']


@pytest.mark.parametrize('rate,fee,inflation,n,timing', [('5','0.75','2.5',37,'beginning'),('-30','4','-2',19,'end'),
    ('0','100','100',1200,'beginning'),('100','100','-99',1200,'end'),('-99','100','100',1200,'end'),
    ('0.000000000000000000000001','0.000000000000000000000001','-0.000000000000000000000001',1200,'end')])
def test_independent_high_precision_cash_flow_reference(rate,fee,inflation,n,timing):
    result=project(annual_return_percent=rate,annual_fee_percent=fee,annual_inflation_percent=inflation,
                   duration_months=n,contribution_timing=timing)
    with localcontext() as ctx:
        ctx.prec=110
        g=(1+D(rate)/100)**(D(1)/12);q=g*(1-D(fee)/1200)
        expected=D(1000)*q**n+sum((D(100)*q**k for k in range(0 if timing=='end' else 1,n if timing=='end' else n+1)),D(0))
        close(result.final.closing_balance,expected)
        close(result.purchasing_power,expected/(1+D(inflation)/100)**(D(n)/12))


@pytest.mark.parametrize('rate,n,timing,c',[('5',12,'end','100'),('-99',1200,'beginning','0'),
    ('100',1200,'end','1000000000000'),('0',0,'end','100'),('0',12,'beginning','100')])
def test_zero_fee_matches_unchanged_savings_engine(rate,n,timing,c):
    result=project(annual_fee_percent='0',annual_return_percent=rate,duration_months=n,contribution_timing=timing,monthly_contribution=c)
    savings=calculate_savings(result.scenario.savings_scenario())
    assert [row.closing_balance for row in result.rows]==[row.closing_balance for row in savings.rows]
    assert result.fee_impact==0 and result.final.cumulative_fees==0


def test_zero_periods_and_no_money():
    result=project(duration_months=0)
    assert len(result.rows)==1 and result.final.closing_balance==1000 and result.purchasing_power==1000
    assert result.final.contribution==1000 and result.final.net_gain==result.final.cumulative_fees==0
    assert project(initial_balance='0',monthly_contribution='0').final.closing_balance==0
    assert project(annual_return_percent='-50').final.net_gain<0


@pytest.mark.parametrize('currency,initial,expected',[('USD','1.00','1.00'),('JPY','1','1'),('KWD','1.000','1.000')])
def test_minor_units_and_half_even_ties(currency,initial,expected):
    result=project(initial_balance=initial,monthly_contribution='0',annual_return_percent='0',annual_fee_percent='0',currency=currency)
    assert amount_text(result.final.closing_balance,currency)==expected
    assert amount_text(project(initial_balance='1',monthly_contribution='0',annual_return_percent='0.5',annual_fee_percent='0').final.closing_balance,'USD')=='1.00'
    assert amount_text(project(initial_balance='1',monthly_contribution='0',annual_return_percent='1.5',annual_fee_percent='0').final.closing_balance,'USD')=='1.02'


@pytest.mark.parametrize('field,value', [('initial_balance',''),('monthly_contribution',True),('annual_return_percent','NaN'),
 ('annual_fee_percent','-0.1'),('annual_fee_percent','101'),('annual_inflation_percent','-100'),
 ('annual_inflation_percent','1e2'),('annual_return_percent','101'),('annual_return_percent','-100'),
 ('annual_inflation_percent','0.'+'0'*24+'1'),('duration_months',True),('duration_months',1201),
 ('contribution_timing','mid'),('currency','BTC'),('source','live'),('sample_derived','true'),('name','\x00')])
def test_validation_fields(field,value):
    with pytest.raises(ScenarioError) as exc:project(**{field:value})
    assert field in exc.value.errors


@pytest.mark.parametrize('field', ['initial_balance','monthly_contribution','annual_return_percent','annual_fee_percent','annual_inflation_percent','duration_months'])
def test_missing_never_becomes_zero(field):
    data=inputs();del data[field]
    with pytest.raises(ScenarioError) as exc:InvestmentScenario.from_mapping(data)
    assert field in exc.value.errors


@pytest.mark.parametrize('value', [[],None,{'unexpected':'x'},{'schema_version':True},{'calculation_mode':'goal'}])
def test_bad_schema(value):
    with pytest.raises(ScenarioError):InvestmentScenario.from_mapping(value)


def test_provenance_precision_context_and_invariants():
    original=getcontext().copy()
    try:
        getcontext().prec=6
        base=project(source='sample')
        assert base.scenario.sample_derived is True and getcontext().prec==6
        assert project(annual_inflation_percent='-2').final==base.final
        assert project(annual_inflation_percent='0').purchasing_power==base.final.closing_balance
        with pytest.raises(ScenarioError):project(currency='JPY',initial_balance='1.01')
    finally:
        getcontext().prec=original.prec
    rng=random.Random(37)
    for _ in range(15):
        data=dict(initial_balance=str(rng.randrange(10000)),monthly_contribution=str(rng.randrange(1000)),
                  annual_return_percent=str(rng.randrange(-90,100)),duration_months=rng.randrange(1,80))
        low=project(**data,annual_fee_percent='1');high=project(**data,annual_fee_percent='2')
        assert high.final.closing_balance<=low.final.closing_balance<=low.final.no_fee_balance
        assert high.final.cumulative_fees>=0
