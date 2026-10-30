"""Portfolio API/save/reopen checks use private temporary stores and fictional holdings."""
from copy import deepcopy
from datetime import timedelta
import json
import re

from fastapi.testclient import TestClient
import pytest

from econ_sdd.accounts import initialize_files
from econ_sdd.market.alpaca import Profile
from econ_sdd.market.service import MarketService
from econ_sdd.web import create_app
from tests.portfolio_fixtures import NOW, Transport, real_definition

PASSWORD='synthetic portfolio password 42!'


def client(app):
    c=TestClient(app,base_url='http://127.0.0.1')
    c.headers['X-CSRF-Token']=re.search(r'name="csrf-token" content="([^"]+)"',c.get('/portfolios').text).group(1)
    return c


def register(c,username):
    response=c.post('/api/account/register',json={'username':username,'password':PASSWORD})
    assert response.status_code==200
    c.headers['X-Account-CSRF']=response.json()['csrf_token']
    return response.json()['user']['id']


@pytest.fixture
def environment(tmp_path):
    store=initialize_files(tmp_path/'db'/'accounts.sqlite3',tmp_path/'keys'/'keyring.json')
    now=[NOW];transport=Transport(lambda:now[0],real_definition());market=MarketService(transport=transport,clock=lambda:now[0])
    app=create_app(account_store=store,market_service=market);a=client(app);b=client(app)
    owner=register(a,'Portfolio_QA');register(b,'Other_QA')
    market.profile=Profile(owner,'syntheticKEY','syntheticSECRET')
    return store,app,a,b,transport,now


def capture(a,definition=None,revision=1):
    d=(definition or real_definition()).as_record()
    response=a.post('/api/portfolios/capture',json={'definition':d,'input_revision':revision})
    assert response.status_code==200,response.text
    return {'definition':d,'input_revision':revision,'capture_id':response.json()['capture_id']}


def plan(d=None,title='Private original holdings'):
    return {'title':title,'kind':'portfolio_holdings','inputs':(d or real_definition()).as_record()}


def test_authoritative_capture_and_value_end_to_end(environment):
    _,_,a,_,transport,_=environment
    request=capture(a);response=a.post('/api/portfolios/value',json=request)
    assert response.status_code==200
    data=response.json()
    assert data['display']['total']=='$2,000.00' and data['display']['gain']=='$124.20'
    assert data['rows'][0]['display']['weight']=='63.21%' and data['state']=='live'
    assert len([e for e,_ in transport.calls if e=='trades'])==1
    assert a.post('/api/portfolios/value',json={**request,'prices':{'SYN-A':'99999'}}).status_code==422


def test_provider_and_capture_owner_session_boundaries(environment):
    _,app,a,b,transport,_=environment
    anon=client(app);body={'definition':real_definition().as_record(),'input_revision':1}
    assert anon.post('/api/portfolios/capture',json=body).status_code==401
    assert b.post('/api/portfolios/capture',json=body).status_code==503
    assert not transport.calls
    request=capture(a);count=len(transport.calls)
    assert b.post('/api/portfolios/value',json=request).status_code==409
    assert a.post('/api/account/logout',json={}).status_code==200
    assert a.post('/api/portfolios/value',json=request).status_code==401
    assert len(transport.calls)==count


def test_definitions_save_encrypted_reopen_unpriced_without_network_or_prices(environment):
    store,app,a,_,transport,_=environment
    response=a.post('/api/plans',json=plan())
    assert response.status_code==200
    saved=response.json()['plan'];url='/api/plans/'+saved['id']
    assert not transport.calls
    opened=a.get(url).json()
    assert opened['calculation']['status']=='unpriced' and opened['calculation']['prices_omitted']
    assert opened['calculation']['definition']==real_definition().as_record()
    assert not transport.calls
    with store.db() as con:row=con.execute('SELECT * FROM plans').fetchone()
    encrypted=store.keys.decrypt(row['ciphertext'],store._plan_aad(row['user_id'],row['id'],row['revision']))
    assert set(encrypted)=={'title','kind','model_version','inputs'}
    assert 'quotes' not in json.dumps(encrypted) and 'capture_id' not in json.dumps(encrypted)
    body=store.path.read_bytes()
    assert b'Private original holdings' not in body and b'415.80' not in body
    restarted=client(create_app(account_store=store));restarted.cookies.update(a.cookies)
    response=restarted.get(url)
    assert response.status_code==200 and response.json()['calculation']['status']=='unpriced'
    assert not transport.calls


def test_library_ownership_revisions_and_quota_apply_to_portfolios(environment):
    store,_,a,b,transport,_=environment
    saved=a.post('/api/plans',json=plan()).json()['plan'];url='/api/plans/'+saved['id']
    assert b.get(url).status_code==404 and b.get('/api/plans').json()['plans']==[]
    changed=plan(real_definition(cash='500'),title='Updated private portfolio')
    assert a.post(url+'/replace',json={**changed,'revision':1}).json()['plan']['revision']==2
    assert a.post(url+'/replace',json={**changed,'revision':1}).status_code==409
    assert b.post(url+'/delete',json={'revision':2}).status_code==404
    assert a.post(url+'/delete',json={'revision':1}).status_code==409
    session=store.session(a.cookies.get('econ_dev_session'))
    from econ_sdd.account_api import normalize_plan
    for _ in range(99):store.save_plan(session,normalize_plan(plan()))
    assert a.post('/api/plans',json=plan()).status_code==422
    assert len(a.get('/api/plans').json()['plans'])==100 and not transport.calls


def test_import_export_definition_only_and_ignore_forged_derived_results(environment):
    _,_,a,_,transport,_=environment
    response=a.post('/api/portfolios/export',json={'definition':real_definition().as_record()})
    assert response.status_code==200 and 'attachment;' in response.headers['content-disposition']
    record=response.json();assert record['prices_omitted'] and 'summary' not in record
    record.update({'summary':{'total':'99999999'},'rows':[{'price':'999'}],'capture_id':'forged'})
    restored=a.post('/api/portfolios/import',json=record).json()
    assert restored['status']=='unpriced' and restored['definition']==real_definition().as_record()
    assert 'summary' not in restored and not transport.calls
    record['model_version']='portfolio-v999'
    assert a.post('/api/portfolios/import',json=record).status_code==422


@pytest.mark.parametrize('route,body',[
    ('/api/portfolios/validate',{'definition':real_definition().as_record()}),
    ('/api/portfolios/import',real_definition().as_record()),
    ('/api/portfolios/export',{'definition':real_definition().as_record()}),
    ('/api/portfolios/capture',{'definition':real_definition().as_record(),'input_revision':1}),
    ('/api/portfolios/value',{'definition':real_definition().as_record(),'input_revision':1,'capture_id':'fake'}),
    ('/api/portfolios/example',{})])
def test_all_portfolio_posts_use_process_csrf_origin_json_size_and_duplicate_guards(environment,route,body):
    _,_,a,_,transport,_=environment
    for headers in ({'X-CSRF-Token':''},{'Origin':'https://evil.test'},{'Sec-Fetch-Site':'cross-site'}):
        assert a.post(route,json=body,headers=headers).status_code==403
    assert a.post(route,content='x',headers={'Content-Type':'text/plain'}).status_code==415
    assert a.post(route,content=b' '*(1048576+1),headers={'Content-Type':'application/json'}).status_code==413
    assert a.post(route,content=b'{"x":1,"x":2}',headers={'Content-Type':'application/json'}).status_code==422
    assert not transport.calls


def test_market_capture_and_value_require_account_csrf_and_detect_changed_input(environment):
    _,_,a,_,transport,_=environment
    d=real_definition().as_record();body={'definition':d,'input_revision':1}
    assert a.post('/api/portfolios/capture',json=body,headers={'X-Account-CSRF':''}).status_code==403
    request=capture(a)
    assert a.post('/api/portfolios/value',json=request,headers={'X-Account-CSRF':''}).status_code==403
    request['definition']['cash']='999'
    assert a.post('/api/portfolios/value',json=request).status_code==409


def test_anonymous_fictional_example_does_not_request_provider_or_accept_real_instruments(environment):
    _,app,_,_,transport,_=environment;anon=client(app)
    value=anon.post('/api/portfolios/example',json={}).json()
    assert value['source']=='synthetic' and value['display']['total']=='$2,000.00'
    assert anon.post('/api/portfolios/example',json={'definition':real_definition().as_record()}).status_code==422
    assert not transport.calls


def test_prices_and_private_values_are_not_logged_and_static_navigation_is_available(environment,caplog):
    _,app,a,_,_,_=environment
    request=capture(a);a.post('/api/portfolios/value',json=request)
    assert PASSWORD not in caplog.text and '415.80' not in caplog.text and 'syntheticSECRET' not in caplog.text
    c=client(app);html=c.get('/portfolios').text;script=c.get('/static/portfolios.js').text
    assert '<title>Finance</title>' in html and 'portfolio-holdings-v1' in html
    assert 'innerHTML' not in script and 'localStorage' not in script and 'sessionStorage' not in script
    assert 'https://' not in script and 'APCA-API' not in script
    for route in ('/stocks','/investments'):
        assert 'href="/portfolios"' in c.get(route).text


def test_capture_expiry_and_daily_share_basis_are_visible(environment):
    _,_,a,_,_,now=environment
    request=capture(a);now[0]+=timedelta(seconds=301)
    assert a.post('/api/portfolios/value',json=request).status_code==409
    now[0]=NOW
    request=capture(a,real_definition(pricing_mode='daily'))
    value=a.post('/api/portfolios/value',json=request).json()
    assert value['state']=='needs_review' and value['summary']['total'] is None
    request=capture(a,real_definition(pricing_mode='daily',as_of_date='2026-10-28'),revision=2)
    assert a.post('/api/portfolios/value',json=request).json()['display']['total']=='$2,000.00'
