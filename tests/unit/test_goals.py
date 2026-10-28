from datetime import date
from decimal import Context, Decimal as D, localcontext
from fractions import Fraction
import random

import pytest

from econ_sdd.finance.goals import SavingsGoal, anniversary, complete_months, solve_goal
from econ_sdd.finance.savings import SavingsScenario, ScenarioError, calculate_savings


def goal(p="1000",target="5000",rate="5",start=date(2026,10,27),end=date(2028,10,27),timing="end",currency="USD"):
    return SavingsGoal(D(p),D(target),D(rate),start,end,timing,currency)


def test_independent_goal_cashflow_reference():
    result=solve_goal(goal())
    assert result.required_monthly_contribution==D("154.92")
    assert abs(result.unrounded_monthly_contribution-D("154.9160726514073708011990381906114154018899"))<D("1e-35")
    assert result.projection.final.closing_balance>=5000
    with localcontext(Context(prec=100)):
        q=D('1.05')**(D(1)/12)
        independent=D(1000)*q**24+sum((D('154.92')*q**k for k in range(24)),D(0))
        assert abs(result.projection.final.closing_balance-independent)<D('1e-65')


@pytest.mark.parametrize('currency,expected,final',[('USD','33.34','100.02'),('JPY','34','102'),('KWD','33.334','100.002')])
def test_exact_fraction_rounding_up(currency,expected,final):
    result=solve_goal(goal(p='0',target='100',rate='0',end=date(2027,1,27),currency=currency))
    assert result.required_monthly_contribution==D(expected)
    assert Fraction(expected)*3==Fraction(final)
    assert result.projection.final.closing_balance==D(final)


@pytest.mark.parametrize('timing,target',[('end','1221.10'),('beginning','1223.11')])
def test_exact_rational_inverse(timing,target):
    result=solve_goal(goal(target=target,rate='12.6825030131969720661201',end=date(2026,12,27),timing=timing))
    assert result.required_monthly_contribution==100
    assert result.projection.final.closing_balance==D(target)


@pytest.mark.parametrize('start,target,n,modeled,days',[
    (date(2027,1,31),date(2027,2,28),1,date(2027,2,28),0),
    (date(2027,1,31),date(2027,3,30),1,date(2027,2,28),30),
    (date(2027,1,31),date(2027,3,31),2,date(2027,3,31),0),
    (date(2028,2,29),date(2029,2,28),12,date(2029,2,28),0),
    (date(2026,10,27),date(2026,11,26),0,date(2026,10,27),30),
    (date(2026,10,27),date(2027,10,28),12,date(2027,10,27),1),
])
def test_calendar_contract(start,target,n,modeled,days):
    assert complete_months(start,target)==n
    result=solve_goal(goal(p='100',target='0',start=start,end=target))
    assert result.modeled_end_date==modeled and result.unused_days==days


def test_anniversary_uses_original_anchor():
    anchor=date(2027,1,31)
    assert anniversary(anchor,1)==date(2027,2,28)
    assert anniversary(anchor,2)==date(2027,3,31)


@pytest.mark.parametrize('timing,first,last',[
    ('end',date(2026,11,27),date(2028,10,27)),
    ('beginning',date(2026,10,27),date(2028,9,27))])
def test_deposit_dates(timing,first,last):
    result=solve_goal(goal(timing=timing))
    assert result.first_deposit_date==first and result.last_deposit_date==last


def test_zero_period_funded_and_unfunded():
    result=solve_goal(goal(p='1000',target='1000',end=date(2026,10,27)))
    assert result.required_monthly_contribution==0
    assert result.first_deposit_date is None and result.last_deposit_date is None
    with pytest.raises(ScenarioError):solve_goal(goal(target='1001',end=date(2026,11,26)))


def test_negative_rate_can_require_deposits_even_when_today_balance_exceeds_goal():
    result=solve_goal(goal(p='1100',target='1000',rate='-20',end=date(2027,10,27)))
    assert result.required_monthly_contribution>0
    assert result.projection.final.closing_balance>=1000


def test_growth_can_cover_goal_without_deposits():
    result=solve_goal(goal(p='1000',target='1050',end=date(2027,10,27)))
    assert result.required_monthly_contribution==0
    assert result.first_deposit_date is None and result.last_deposit_date is None


def test_range_limit_is_not_clamped():
    with pytest.raises(ScenarioError):
        solve_goal(goal(p='0',target='1000000000000',rate='-99',end=date(2026,11,27),timing='beginning'))


@pytest.mark.parametrize('rate', ['-99','0','0.000000000000000000000001','100'])
def test_max_horizon_and_contribution_minimality(rate):
    result=solve_goal(goal(p='0',target='5000',rate=rate,end=date(2126,10,27)))
    verify_minimum(result)


def verify_minimum(result):
    assert result.projection.final.closing_balance>=result.goal.goal_amount
    if result.required_monthly_contribution:
        from econ_sdd.finance.currencies import CURRENCIES
        quantum=D(1).scaleb(-CURRENCIES[result.goal.currency].minor_digits)
        s=result.projection.scenario
        lower=SavingsScenario(s.initial_balance,s.monthly_contribution-quantum,s.annual_effective_rate_percent,
                              s.duration_months,s.contribution_timing,s.currency)
        assert calculate_savings(lower).final.closing_balance<result.goal.goal_amount


def test_seeded_minimality_and_timing():
    rng=random.Random(20261027)
    for _ in range(16):
        months=rng.randint(1,60)
        result=solve_goal(goal(p=str(rng.randint(0,5000)),target=str(rng.randint(5001,10000)),
            rate=str(rng.randint(-10,15)),end=anniversary(date(2026,10,27),months),timing=rng.choice(['end','beginning'])))
        verify_minimum(result)


def test_global_context_isolation():
    g=goal();expected=solve_goal(g)
    with localcontext() as c:
        c.prec=6
        assert solve_goal(g)==expected


def data():
    return {'initial_balance':'1000','goal_amount':'5000','annual_effective_rate_percent':'5',
            'start_date':'2026-10-27','target_date':'2028-10-27'}


@pytest.mark.parametrize('key,value',[
    ('goal_amount','NaN'),('goal_amount','-1'),('goal_amount','1000000000001'),('goal_amount','1.001'),
    ('goal_amount',False),('start_date','20261027'),('start_date','2026-02-30'),('start_date',True),
    ('target_date','2020-01-01'),('target_date','2226-10-27'),('target_date','2028-W43-5'),
    ('currency','BAD'),('schema_version',True),('calculation_mode','other'),('monthly_contribution','1')])
def test_invalid_goal_fields(key,value):
    payload=data();payload[key]=value
    with pytest.raises(ScenarioError):SavingsGoal.from_mapping(payload)


def test_goal_roundtrip_and_provenance():
    payload=data();payload['source']='sample'
    g=SavingsGoal.from_mapping(payload)
    assert g.sample_derived and g.currency=='USD'
    assert SavingsGoal.from_mapping(g.as_record())==g
