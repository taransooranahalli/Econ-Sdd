"""Valid tiny rates must survive file and encrypted-plan reopening."""
import re
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest

from econ_sdd.accounts import initialize_files
from econ_sdd.web import create_app


@pytest.mark.parametrize('kind', ['savings', 'goal', 'investment_growth'])
@pytest.mark.parametrize('rate', ['0.00000001', '-0.000000000000000000000001'])
def test_tiny_rate_survives_exports_and_encrypted_saved_plan(tmp_path, kind, rate):
    store = initialize_files(tmp_path/'data'/'test.sqlite3', tmp_path/'keys'/'test.json')
    app = create_app(account_store=store)
    inputs = {'initial_balance':'1000', 'monthly_contribution':'100',
              'annual_effective_rate_percent':rate, 'duration_months':12}
    rate_key = 'annual_effective_rate_percent'
    input_key = 'scenario'
    export_route, import_route = '/api/export/json', '/api/import'
    if kind == 'goal':
        inputs = {'calculation_mode':'goal', 'initial_balance':'1000', 'goal_amount':'5000',
                  rate_key:rate, 'start_date':'2026-10-29', 'target_date':'2028-10-29'}
        input_key = 'goal'
    elif kind == 'investment_growth':
        del inputs[rate_key]
        rate_key = 'annual_return_percent'
        inputs.update({rate_key:rate, 'annual_fee_percent':'0', 'annual_inflation_percent':'2'})
        export_route, import_route = '/api/investments/export/json', '/api/investments/import'
    with TestClient(app, base_url='http://127.0.0.1') as client:
        client.headers['X-CSRF-Token'] = re.search('name="csrf-token" content="([^"]+)"',client.get('/').text).group(1)
        exported = client.post(export_route, json=inputs)
        assert exported.status_code == 200
        record = exported.json()
        assert record[input_key][rate_key] == rate
        reopened = client.post(import_route, json=record)
        assert reopened.status_code == 200
        assert reopened.json()['summary'] == record['summary']
        if kind in {'savings','goal'}:
            # Reproduce the original server-generated notation, while manual inputs stay strict.
            legacy = exported.json()
            legacy[input_key][rate_key] = str(Decimal(rate))
            restored_legacy = client.post(import_route, json=legacy)
            assert restored_legacy.status_code == 200
            assert restored_legacy.json()[input_key][rate_key] == rate
            assert client.post(export_route,json={**inputs,rate_key:str(Decimal(rate))}).status_code == 422
        registered = client.post('/api/account/register', json={'username':'Synthetic_QA','password':'synthetic verification passphrase 694!'})
        assert registered.status_code == 200
        client.headers['X-Account-CSRF'] = registered.json()['csrf_token']
        saved = client.post('/api/plans', json={'title':'Synthetic tiny-rate plan','kind':kind,'inputs':inputs})
        assert saved.status_code == 200
        if kind in {'savings','goal'}:
            with store.db(write=True) as con:
                row=con.execute('SELECT * FROM plans').fetchone()
                aad=store._plan_aad(row['user_id'],row['id'],row['revision'])
                legacy=store.keys.decrypt(row['ciphertext'],aad)
                legacy['inputs'][rate_key]=str(Decimal(rate))
                con.execute('UPDATE plans SET ciphertext=?',(store.keys.encrypt(legacy,aad),))
        calculation = client.get('/api/plans/'+saved.json()['plan']['id']).json()['calculation']
        assert calculation[input_key][rate_key] == rate
        assert calculation['summary'] == record['summary']


@pytest.mark.parametrize('rate',['1E-99999999','1E+99','1E-25','-1E+2'])
def test_invalid_legacy_saved_rates_remain_rejected(rate):
    with TestClient(create_app(),base_url='http://127.0.0.1') as client:
        client.headers['X-CSRF-Token']=re.search('name="csrf-token" content="([^"]+)"',client.get('/').text).group(1)
        data={'initial_balance':'1000','monthly_contribution':'100','annual_effective_rate_percent':'5','duration_months':12}
        record=client.post('/api/export/json',json=data).json()
        record['scenario']['annual_effective_rate_percent']=rate
        assert client.post('/api/import',json=record).status_code==422
