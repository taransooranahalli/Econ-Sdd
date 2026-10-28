import csv
from decimal import Decimal as D
from datetime import date
import io
import json
import re

from fastapi.testclient import TestClient
import pytest

from econ_sdd.finance.goals import SavingsGoal, solve_goal
from econ_sdd.serialization.records import calculation_from_record, export_json, export_csv, load_json
from econ_sdd.web import create_app


def data(**changes):
    value={'schema_version':1,'calculation_mode':'goal','initial_balance':'1000','goal_amount':'5000',
           'annual_effective_rate_percent':'5','start_date':'2026-10-27','target_date':'2028-10-27',
           'currency':'USD','contribution_timing':'end','source':'sample','sample_derived':True}
    value.update(changes)
    return value


@pytest.fixture
def client():
    with TestClient(create_app(),base_url='http://127.0.0.1') as c:
        token=re.search(r'name="csrf-token" content="([^"]+)"',c.get('/').text).group(1)
        c.headers['X-CSRF-Token']=token
        yield c


def test_goal_api_and_original_projection_regression(client):
    r=client.post('/api/goal',json=data())
    assert r.status_code==200
    value=r.json()
    assert value['model_version']=='savings-goal-v1'
    assert value['projection_model_version']=='savings-v1'
    assert value['display']['goal']['required_monthly_contribution']=='$154.92'
    assert value['goal_result']['goal_met'] is True
    assert value['goal_result']['complete_months']==24
    assert value['rows'][0]['closing_date']=='2026-10-27'
    assert value['rows'][1]['deposit_date']=='2026-11-27'
    original=client.post('/api/calculate',json={'initial_balance':'1000','monthly_contribution':'100',
        'annual_effective_rate_percent':'5','duration_months':12}).json()
    assert original['model_version']=='savings-v1'
    assert original['display']['summary']['ending_balance']=='$2,277.26'


@pytest.mark.parametrize('currency,payment',[('USD','$33.34'),('JPY','¥34'),('KWD','KWD 33.334')])
def test_goal_currency_and_upward_rounding(client,currency,payment):
    r=client.post('/api/goal',json=data(currency=currency,initial_balance='0',goal_amount='100',
        annual_effective_rate_percent='0',target_date='2027-01-27'))
    assert r.status_code==200
    assert r.json()['display']['goal']['required_monthly_contribution']==payment


def test_goal_json_roundtrip_ignores_saved_results(client):
    saved=client.post('/api/export/json',json=data())
    assert saved.status_code==200
    record=saved.json()
    original_goal=record['goal'].copy()
    record['goal_result']['required_monthly_contribution']='0'
    record['scenario']['monthly_contribution']='0'
    record['summary']['ending_balance']='999999'
    record['rows']=None
    loaded=client.post('/api/import',json=record)
    assert loaded.status_code==200
    assert loaded.json()['goal']==original_goal
    assert loaded.json()['goal_result']['required_monthly_contribution']=='154.92'
    assert loaded.json()['display']['goal']['required_monthly_contribution']=='$154.92'
    raw=client.post('/api/import',json=data())
    assert raw.status_code==200 and raw.json()['model_version']=='savings-goal-v1'


def test_goal_csv_dates_metadata_and_row_values(client):
    saved=client.post('/api/export/csv',json=data(contribution_timing='beginning'))
    assert saved.status_code==200
    rows=list(csv.DictReader(io.StringIO(saved.text)))
    assert len(rows)==25
    assert rows[0]['deposit_date']==''
    assert rows[1]['deposit_date']=='2026-10-27'
    assert rows[-1]['deposit_date']=='2028-09-27'
    assert rows[-1]['closing_date']=='2028-10-27'
    assert rows[-1]['goal_amount']=='5000.00'
    assert rows[-1]['model_version']=='savings-goal-v1'
    assert rows[-1]['currency']=='USD'
    assert D(rows[-1]['closing_balance'])>=5000


def test_partial_month_and_zero_period_responses(client):
    r=client.post('/api/goal',json=data(start_date='2027-01-31',target_date='2027-03-30')).json()
    assert r['goal_result']['complete_months']==1
    assert r['goal_result']['modeled_end_date']=='2027-02-28'
    assert r['goal_result']['unused_days']==30
    covered=client.post('/api/goal',json=data(goal_amount='1000',target_date='2026-10-27')).json()
    assert covered['goal_result']['status']=='no_additional_deposit'
    assert covered['display']['goal']['required_monthly_contribution']=='$0.00'
    assert covered['goal_result']['first_deposit_date'] is None
    unfunded=client.post('/api/goal',json=data(target_date='2026-11-26'))
    assert unfunded.status_code==422 and 'target_date' in unfunded.json()['errors']


@pytest.mark.parametrize('update,field',[({'target_date':'bad'},'target_date'),({'target_date':'2020-01-01'},'target_date'),
    ({'goal_amount':'1.001'},'goal_amount'),({'goal_amount':'-1'},'goal_amount'),
    ({'currency':'JPY','goal_amount':'5000.10'},'goal_amount'),({'annual_effective_rate_percent':'NaN'},'annual_effective_rate_percent')])
def test_goal_field_errors(client,update,field):
    r=client.post('/api/goal',json=data(**update))
    assert r.status_code==422 and field in r.json()['errors']


@pytest.mark.parametrize('route',['goal','import','export/json','export/csv'])
def test_goal_routes_privacy_guards_and_strict_json(client,route):
    assert client.post('/api/'+route,json=data(),headers={'X-CSRF-Token':''}).status_code==403
    assert client.post('/api/'+route,json=data(),headers={'Origin':'https://example.org'}).status_code==403
    duplicate=client.post('/api/'+route,content=b'{"goal_amount":"1","goal_amount":"2"}',headers={'Content-Type':'application/json'})
    assert duplicate.status_code==422


@pytest.mark.parametrize('key,value',[('model_version','savings-goal-v999'),('schema_version',2),('schema_version',True)])
def test_goal_model_version_guards(client,key,value):
    saved=client.post('/api/export/json',json=data()).json()
    saved[key]=value
    assert client.post('/api/import',json=saved).status_code==422


def test_old_savings_file_stays_supported(client):
    original={'schema_version':1,'model_version':'savings-v1','app_version':'0.1.0',
        'scenario':{'schema_version':1,'initial_balance':'1000','monthly_contribution':'100',
                    'annual_effective_rate_percent':'5','duration_months':12}}
    r=client.post('/api/import',json=original)
    assert r.status_code==200
    assert r.json()['display']['summary']['ending_balance']=='$2,277.26'
    assert 'goal' not in r.json()


def test_max_goal_export_fits_existing_import_cap():
    goal=SavingsGoal.from_mapping(data(initial_balance='1000000000000',goal_amount='1000000000000',
        annual_effective_rate_percent='100',target_date='2126-10-27'))
    solution=solve_goal(goal)
    payload=export_json(solution).encode()
    assert len(payload)<=1024*1024
    assert calculation_from_record(load_json(payload))==goal


def test_no_goal_inputs_in_error_logs(client,caplog):
    value='4815162342.12'
    r=client.post('/api/goal',json=data(goal_amount=value))
    assert r.status_code==200
    assert value not in caplog.text
