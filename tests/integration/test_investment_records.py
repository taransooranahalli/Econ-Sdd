import csv
import io
import re
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from econ_sdd.finance.investments import InvestmentScenario, calculate_investments
from econ_sdd.serialization.investments import export_investment_json
from econ_sdd.serialization.records import MAX_FILE_BYTES
from econ_sdd.web import create_app


def example(**changes):
    return {'initial_balance':'1000','monthly_contribution':'100','annual_return_percent':'12.6825030131969720661201',
            'annual_fee_percent':'1.2','annual_inflation_percent':'12.6825030131969720661201','duration_months':12,
            'source':'sample',**changes}


@pytest.fixture
def client():
    with TestClient(create_app(),base_url='http://127.0.0.1') as client:
        page=client.get('/investments')
        client.headers['X-CSRF-Token']=re.search('name="csrf-token" content="([^"]+)"',page.text).group(1)
        yield client


def test_endpoint_reference_and_metadata(client):
    response=client.post('/api/investments',json=example());assert response.status_code==200
    data=response.json()
    assert data['display']['summary']==dict(ending_balance='$2,374.53',total_contributed='$2,200.00',net_gain='$174.53',
        cumulative_fees='$19.61',no_fee_balance='$2,395.08',fee_impact='$20.55',purchasing_power='$2,107.27')
    assert data['model_version']=='investment-growth-v1' and data['scenario']['sample_derived'] is True
    assert data['output_category']=='conditional_projection' and data['assumptions']['market_data']=='none'
    assert len(data['rows'])==13 and data['rows'][0]['gross_gain']=='0'


@pytest.mark.parametrize('currency,p,expected',[('USD','0.01','$0.01'),('JPY','1','¥1'),('KWD','0.001','KWD 0.001')])
def test_currency_zero_period_round_trip(client,currency,p,expected):
    data=example(initial_balance=p,monthly_contribution='0',currency=currency,duration_months=0)
    saved=client.post('/api/investments/export/json',json=data)
    assert 'econ-investments-'+currency+'.json' in saved.headers['content-disposition']
    record=saved.json();record['summary']={'ending_balance':'999999'};record['rows']=[]
    restored=client.post('/api/investments/import',json=record)
    assert restored.json()['display']['summary']['ending_balance']==expected
    assert client.post('/api/investments/import',json=record['scenario']).status_code==200


def test_csv_parity_and_conventions(client):
    response=client.post('/api/investments/export/csv',json=example(name='=private'))
    rows=list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows)==13 and 'name' not in rows[0]
    assert rows[-1]['closing_balance']=='2374.53' and rows[-1]['fee_impact_on_ending_value']=='20.55'
    assert rows[-1]['cumulative_fees']=='19.61' and rows[-1]['start_period_purchasing_power']=='2107.27'
    assert rows[0]['contribution']=='1000.00' and rows[1]['contribution']=='100.00'
    assert all(row['tax']=='not_modeled' and row['model_version']=='investment-growth-v1' for row in rows)


@pytest.mark.parametrize('route',['','/import','/export/json','/export/csv'])
def test_guards(client,route):
    path='/api/investments'+route
    assert client.post(path,json=example(),headers={'X-CSRF-Token':''}).status_code==403
    assert client.post(path,json=example(),headers={'Origin':'https://example.org'}).status_code==403
    assert client.post(path,content='x',headers={'Content-Type':'text/plain'}).status_code==415
    assert client.post(path,content='{"currency":"USD","currency":"EUR"}',headers={'Content-Type':'application/json'}).status_code==422
    assert client.post(path,content=b' '*(MAX_FILE_BYTES+1),headers={'Content-Type':'application/json'}).status_code==413


@pytest.mark.parametrize('model',['savings-v1','savings-goal-v1','cash-flow-v1','investment-growth-v2'])
def test_model_versions_and_cross_calculator_files(client,model):
    record=client.post('/api/investments/export/json',json=example()).json();record['model_version']=model
    assert client.post('/api/investments/import',json=record).status_code==422
    record['model_version']='investment-growth-v1';record['schema_version']=True
    assert client.post('/api/investments/import',json=record).status_code==422


@pytest.mark.parametrize('rate,inflation,fee',[('100','-99','99.123456789012345678901234'),('-99','100','100'),('0','0','0'),('100','-99','0.000000000000000000000001')])
def test_largest_export_fits_import_cap(client,rate,inflation,fee):
    scenario=InvestmentScenario.from_mapping(example(initial_balance='1000000000000',monthly_contribution='1000000000000',
        duration_months=1200,annual_return_percent=rate,annual_inflation_percent=inflation,annual_fee_percent=fee))
    encoded=export_investment_json(calculate_investments(scenario)).encode()
    assert len(encoded)<MAX_FILE_BYTES
    assert client.post('/api/investments/import',content=encoded,headers={'Content-Type':'application/json'}).status_code==200


def test_static_contract_navigation_and_privacy(client,caplog):
    page=client.get('/investments');script=client.get('/static/investments.js').text
    ids=re.findall(r'\bid="([^"]+)"',page.text)
    assert len(ids)==len(set(ids))
    assert set(re.findall(r"\$\('([^']+)'\)",script))<=set(ids)
    assert '__CSRF_TOKEN__' not in page.text and 'id="result-content" hidden' in page.text
    for path in ['/','/cash-flow','/plans','/account']:
        assert 'href="/investments"' in client.get(path).text
    assert 'https://' not in page.text and '.innerHTML' not in script
    assert 'localStorage' not in script and 'sessionStorage' not in script
    assert client.get('/api/config').json()['investment_model_version']=='investment-growth-v1'
    assert client.get('/investments',headers={'Host':'example.org'}).status_code==400
    assert 'no-store' in page.headers['cache-control']
    response=client.post('/api/investments',json=example(initial_balance='4815162342.12',name='Private marker'))
    assert response.status_code==200
    assert '4815162342.12' not in caplog.text and 'Private marker' not in caplog.text
    assert client.post('/api/investments/export/pdf',json=example()).status_code==404
    assert 'annual_fee_percent' in client.post('/api/investments',json=example(annual_fee_percent='')).json()['errors']
