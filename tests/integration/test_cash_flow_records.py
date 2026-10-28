import csv
import io
import json
import re

from fastapi.testclient import TestClient
import pytest

from econ_sdd.finance.cash_flow import CashFlowBudget, calculate_cash_flow
from econ_sdd.serialization.cash_flow import budget_from_record, cash_flow_display, export_cash_flow_json
from econ_sdd.serialization.records import MAX_FILE_BYTES
from econ_sdd.web import STATIC, create_app


@pytest.fixture
def client():
    with TestClient(create_app(),base_url='http://127.0.0.1') as client:
        page=client.get('/cash-flow')
        token=re.search(r'name="csrf-token" content="([^"]+)"',page.text).group(1)
        client.headers.update({'X-CSRF-Token':token})
        yield client


def example(**updates):
    data={'schema_version':1,'calculation_mode':'cash_flow','currency':'USD','source':'sample',
          'income':[{'label':'Take-home pay','amount':'4200.10'},{'label':'Other income','amount':'300.20'}],
          'expenses':[{'label':'Housing','amount':'1600.05'},{'label':'Utilities','amount':'200.10'},
                      {'label':'Food','amount':'450.15'},{'label':'Transport','amount':'250.00'},
                      {'label':'Other','amount':'500.00'}]}
    data.update(updates);return data


def test_calculation_endpoint_and_reference(client):
    response=client.post('/api/cash-flow',json=example())
    assert response.status_code==200
    record=response.json()
    assert record['display']['summary']=={'total_income':'$4,500.30','total_expenses':'$3,000.30','net_cash_flow':'$1,500.00'}
    assert record['summary']['status']=='surplus'
    assert record['output_category']=='monthly_budget_calculation'
    assert record['budget']['sample_derived'] is True
    assert record['assumptions']['fx_conversion'] is False
    assert record['assumptions']['daily_timing']=='not_modeled'
    assert record['model_version']=='cash-flow-v1'
    assert isinstance(record['expense_breakdown'][0]['share_percent'],str)


@pytest.mark.parametrize('currency,amount,expected',[('USD','0.01','$0.01'),('JPY','1','¥1'),('KWD','0.001','KWD 0.001')])
def test_currency_minor_units(client,currency,amount,expected):
    data=example(currency=currency,income=[{'label':'One unit','amount':amount}],expenses=[{'label':'None','amount':'0'}])
    record=client.post('/api/cash-flow',json=data).json()
    assert record['display']['summary']['net_cash_flow']==expected
    assert record['expense_breakdown'][0]['share_percent'] is None
    assert record['display']['expenses'][0]['share_percent']=='Not applicable'


def test_zero_income_and_shortfall_do_not_create_nan(client):
    data=example(income=[{'label':'None','amount':'0'}],expenses=[{'label':'Rent','amount':'25'}])
    response=client.post('/api/cash-flow',json=data)
    record=response.json()
    assert record['summary']['status']=='shortfall'
    assert record['summary']['spending_share_percent'] is None
    assert record['display']['summary']['net_cash_flow']=='−$25.00'
    assert 'NaN' not in response.text


def test_saved_derived_values_are_ignored_and_raw_input_loads(client):
    saved=client.post('/api/cash-flow/export/json',json=example())
    assert saved.status_code==200 and 'econ-cash-flow-USD.json' in saved.headers['content-disposition']
    record=saved.json();record['summary']={'net_cash_flow':'9999999'};record['expense_breakdown']=[]
    loaded=client.post('/api/cash-flow/import',json=record)
    assert loaded.json()['display']['summary']['net_cash_flow']=='$1,500.00'
    assert client.post('/api/cash-flow/import',json=record['budget']).status_code==200
    assert CashFlowBudget.from_mapping(record['budget'])==budget_from_record(record)


def test_csv_rows_parity_metadata_and_formula_safe_text(client):
    data=example(income=[{'label':'  =2+2','amount':'100'}],expenses=[{'label':'@SUM(1)','amount':'125'}],name='+Budget')
    response=client.post('/api/cash-flow/export/csv',json=data)
    assert response.status_code==200
    rows=list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows)==2
    assert rows[0]['category']=="'  =2+2" and rows[1]['category']=="'@SUM(1)"
    assert rows[0]['name']=="'+Budget"
    assert [row['type'] for row in rows]==['income','expense']
    assert [row['amount'] for row in rows]==['100.00','125.00']
    assert all(row['net_cash_flow']=='-25.00' and row['status']=='shortfall' for row in rows)
    assert all(row['period']=='monthly' and row['own_account_transfers']=='excluded' for row in rows)
    # JSON retains exact original label text; only CSV requires formula neutralization.
    assert client.post('/api/cash-flow/export/json',json=data).json()['budget']['income'][0]['label']=='  =2+2'


@pytest.mark.parametrize('model',['cash-flow-v999','savings-v1','savings-goal-v1'])
def test_unsupported_and_wrong_calculator_files(client,model):
    data=client.post('/api/cash-flow/export/json',json=example()).json();data['model_version']=model
    response=client.post('/api/cash-flow/import',json=data)
    assert response.status_code==422 and 'file' in response.json()['errors']
    data['model_version']='cash-flow-v1';data['schema_version']=True
    assert client.post('/api/cash-flow/import',json=data).status_code==422


@pytest.mark.parametrize('route',['','/import','/export/json','/export/csv'])
def test_request_guards_on_all_cash_flow_routes(client,route):
    path='/api/cash-flow'+route
    assert client.post(path,json=example(),headers={'X-CSRF-Token':''}).status_code==403
    assert client.post(path,json=example(),headers={'Origin':'https://example.org'}).status_code==403
    assert client.post(path,content='a=1',headers={'Content-Type':'application/x-www-form-urlencoded'}).status_code==415
    duplicate=b'{"income":[],"income":[]}'
    assert client.post(path,content=duplicate,headers={'Content-Type':'application/json'}).status_code==422
    assert client.post(path,content=b' '*(MAX_FILE_BYTES+1),headers={'Content-Type':'application/json'}).status_code==413


def test_errors_are_row_specific_and_do_not_log_amounts(client,caplog):
    marker='4815162342.12'
    data=example(income=[{'label':'Private category','amount':marker}])
    assert client.post('/api/cash-flow',json=data).status_code==200
    assert marker not in caplog.text and 'Private category' not in caplog.text
    data['income'][0]['amount']=''
    response=client.post('/api/cash-flow',json=data)
    assert response.status_code==422 and 'income.0.amount' in response.json()['errors']
    assert 'Private category' not in response.text


def test_cash_flow_page_static_contract_and_local_resources(client):
    page=client.get('/cash-flow')
    assert page.status_code==200 and '__CSRF_TOKEN__' not in page.text
    assert 'id="result-content" hidden' in page.text and 'href="/"' in page.text
    assert 'aria-current="page">Cash flow' in page.text
    assert 'href="/cash-flow"' in client.get('/').text
    script=client.get('/static/cash-flow.js').text
    ids=set(re.findall(r'\bid="([^"]+)"',page.text))
    assert len(ids)==len(re.findall(r'\bid="([^"]+)"',page.text))
    assert set(re.findall(r"\$\('([^']+)'\)",script))<=ids
    assert 'https://' not in page.text+script
    assert 'localStorage' not in script and 'sessionStorage' not in script
    assert '.innerHTML' not in script
    assert 'no-store' in page.headers['cache-control']
    assert "connect-src 'self'" in page.headers['content-security-policy']
    assert client.get('/cash-flow',headers={'Host':'example.org'}).status_code==400
    assert client.get('/api/config').json()['cash_flow_model_version']=='cash-flow-v1'


def test_maximum_size_export_can_be_imported_and_displayed(client):
    data=example(income=[{'label':'I'*80,'amount':'1000000000000'}]*50,
                 expenses=[{'label':'E'*80,'amount':'0.000'}]*50,currency='KWD')
    result=calculate_cash_flow(CashFlowBudget.from_mapping(data))
    encoded=export_cash_flow_json(result).encode()
    assert len(encoded)<MAX_FILE_BYTES
    assert client.post('/api/cash-flow/import',content=encoded,headers={'Content-Type':'application/json'}).status_code==200
    assert cash_flow_display(result)['summary']['net_cash_flow']=='KWD 50,000,000,000,000.000'


def test_savings_goal_regression_and_cross_file_rejection(client):
    savings={'initial_balance':'1000','monthly_contribution':'100','annual_effective_rate_percent':'5','duration_months':12}
    assert client.post('/api/calculate',json=savings).json()['display']['summary']['ending_balance']=='$2,277.26'
    goal={'calculation_mode':'goal','initial_balance':'1000','goal_amount':'5000','annual_effective_rate_percent':'5',
          'start_date':'2026-10-27','target_date':'2028-10-27'}
    assert client.post('/api/goal',json=goal).json()['display']['goal']['required_monthly_contribution']=='$154.92'
    cash=client.post('/api/cash-flow/export/json',json=example()).json()
    assert client.post('/api/import',json=cash).status_code==422
    savings_record=client.post('/api/export/json',json=savings).json()
    assert client.post('/api/cash-flow/import',json=savings_record).status_code==422
    assert client.post('/api/cash-flow/export/pdf',json=example()).status_code==404
