from decimal import Decimal, getcontext, localcontext
from fractions import Fraction
import random

import pytest

from econ_sdd.finance.cash_flow import CashFlowBudget, CashFlowItem, calculate_cash_flow
from econ_sdd.finance.savings import ScenarioError


def budget(income=('4200.10','300.20'), expenses=('1600.05','200.10','450.15','250.00','500.00'), **updates):
    data={'income':[{'label':f'Income {i+1}','amount':value} for i,value in enumerate(income)],
          'expenses':[{'label':f'Expense {i+1}','amount':value} for i,value in enumerate(expenses)]}
    data.update(updates)
    return CashFlowBudget.from_mapping(data)


def test_independent_integer_cent_reference():
    result=calculate_cash_flow(budget())
    assert result.total_income == Decimal(450030)/100
    assert result.total_expenses == Decimal(sum([160005,20010,45015,25000,50000]))/100
    assert result.net_cash_flow == Decimal(150000)/100
    assert result.status == 'surplus'
    assert abs(Fraction(result.spending_share_percent)-Fraction(300030,450030)*100)<Fraction(1,10**75)


@pytest.mark.parametrize('income,expenses,net,status,share',[
    ('100','125','-25','shortfall','125'),('0','25','-25','shortfall',None),
    ('0','0','0','balanced',None),('125','125','0','balanced','100'),('100','0','100','surplus','0'),
])
def test_signed_status_and_zero_denominators(income,expenses,net,status,share):
    result=calculate_cash_flow(budget((income,),(expenses,)))
    assert result.net_cash_flow==Decimal(net) and result.status==status
    assert result.spending_share_percent==(Decimal(share) if share is not None else None)
    assert result.expense_shares_percent==((Decimal(100),) if Decimal(expenses) else (None,))


@pytest.mark.parametrize('currency,digits', [('USD',2),('JPY',0),('KWD',3)])
def test_seeded_integer_unit_oracle_and_invariants(currency,digits):
    rng=random.Random(71)
    scale=10**digits
    def text(units):return format(Decimal(units)/scale,f'.{digits}f')
    for _ in range(20):
        incoming=[rng.randrange(0,10**9) for _ in range(8)]
        outgoing=[rng.randrange(0,10**9) for _ in range(12)]
        result=calculate_cash_flow(budget(tuple(map(text,incoming)),tuple(map(text,outgoing)),currency=currency))
        assert result.net_cash_flow==Decimal(sum(incoming)-sum(outgoing))/scale
        reordered=calculate_cash_flow(budget(tuple(map(text,incoming[::-1])),tuple(map(text,outgoing[::-1])),currency=currency))
        assert reordered.net_cash_flow==result.net_cash_flow
        more=calculate_cash_flow(budget(tuple(map(text,incoming+[7])),tuple(map(text,outgoing+[7])),currency=currency))
        assert more.net_cash_flow==result.net_cash_flow
        unit=calculate_cash_flow(budget(tuple(map(text,incoming)),tuple(map(text,outgoing+[1])),currency=currency))
        assert unit.net_cash_flow==result.net_cash_flow-Decimal(1)/scale


def test_global_decimal_context_is_unchanged_and_does_not_reduce_precision():
    original=getcontext().copy()
    with localcontext() as context:
        context.prec=3
        result=calculate_cash_flow(budget())
        assert result.net_cash_flow==Decimal('1500.00')
        assert context.prec==3
    assert getcontext().prec==original.prec


def test_maximum_supported_lists_and_amounts_are_exact():
    result=calculate_cash_flow(budget(('1000000000000',)*50,('0',)*50))
    assert result.total_income==Decimal('50000000000000')
    assert result.net_cash_flow==result.total_income


@pytest.mark.parametrize('value', ['',None,5,True,'NaN','Infinity','1e3','-0.01','1000000000000.01','0.001','0.000'])
def test_invalid_required_currency_amounts(value):
    with pytest.raises(ScenarioError) as error:budget((value,),('0',))
    assert 'income.0.amount' in error.value.errors


@pytest.mark.parametrize('currency,amount',[('JPY','1.0'),('JPY','0.1'),('KWD','1.0001')])
def test_minor_unit_validation(currency,amount):
    with pytest.raises(ScenarioError):budget((amount,),('0',),currency=currency)


@pytest.mark.parametrize('label',['',' ','x'*81,'line\nbreak','\x7f','\ud800'])
def test_bad_labels_are_rejected_without_echo(label):
    with pytest.raises(ScenarioError) as error:
        CashFlowBudget.from_mapping({'income':[{'label':label,'amount':'0'}],'expenses':[{'label':'None','amount':'0'}]})
    assert error.value.errors=={'income.0.label':'Enter a plain-text category of 1 to 80 characters.'}


@pytest.mark.parametrize('updates',[{'currency':'ZZZ'},{'source':'bank'},{'sample_derived':1},{'name':'\n'},
    {'schema_version':True},{'schema_version':2},{'calculation_mode':'goal'},{'unexpected':1},
    {'income':[]},{'expenses':None},{'income':[{'label':'X','amount':'0'}]*51},
    {'income':[{'label':'X'}]},{'income':[{'label':'X','amount':'0','extra':True}]}])
def test_malformed_budget_contract(updates):
    data=budget().as_record();data.update(updates)
    with pytest.raises(ScenarioError):CashFlowBudget.from_mapping(data)


def test_direct_construction_cannot_bypass_validation():
    with pytest.raises(ScenarioError):CashFlowBudget((CashFlowItem('bad',Decimal('NaN')),),(CashFlowItem('none',Decimal(0)),))
    with pytest.raises(ScenarioError):CashFlowBudget([],())
    with pytest.raises(TypeError):calculate_cash_flow({})


def test_provenance_round_trip_and_duplicate_labels():
    value=budget(source='sample')
    assert value.sample_derived is True
    assert CashFlowBudget.from_mapping(value.as_record())==value
    value=CashFlowBudget.from_mapping({'income':[{'label':'Same','amount':'1'},{'label':'Same','amount':'2'}],
                                     'expenses':[{'label':'None','amount':'0'}]})
    assert calculate_cash_flow(value).total_income==3
