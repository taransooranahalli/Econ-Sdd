"""Market APIs require the same signed-in owner and CSRF protections as private plans."""
import re
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from econ_sdd.accounts import initialize_files
from econ_sdd.market.alpaca import Profile
from econ_sdd.market.service import MarketService
from econ_sdd.web import create_app


class NoNetwork:
    def __init__(self):self.calls=[]
    def get(self,endpoint,params):
        self.calls.append(endpoint)
        return []


def client(app):
    result=TestClient(app,base_url='http://127.0.0.1')
    result.headers['X-CSRF-Token']=re.search(r'name="csrf-token" content="([^"]+)"',result.get('/stocks').text).group(1)
    return result


def register(c,name):
    response=c.post('/api/account/register',json={'username':name,'password':'synthetic market password 42!'})
    assert response.status_code==200
    c.headers['X-Account-CSRF']=response.json()['csrf_token']
    return response.json()['user']['id']


@pytest.fixture
def setup(tmp_path):
    store=initialize_files(tmp_path/'db'/'accounts.sqlite3',tmp_path/'keys'/'keyring.json')
    transport=NoNetwork();market=MarketService(transport=transport)
    app=create_app(account_store=store,market_service=market)
    owner=client(app);other=client(app)
    identity=register(owner,'Market_QA');register(other,'Other_QA')
    market.profile=Profile(identity,'syntheticKEY','syntheticSECRET')
    return app,owner,other,transport


def test_anonymous_page_and_synthetic_preview_work_without_provider():
    c=client(create_app())
    response=c.get('/stocks')
    assert response.status_code==200 and '<title>Finance</title>' in response.text
    assert 'IEX coverage only' in response.text and 'Synthetic' not in response.text.split('<title>')[1].split('</title>')[0]
    assert 'connect-src \'self\'' in response.headers['content-security-policy']
    assert c.get('/api/market/status').json()=={'authenticated':False,'configured':False,'accounts_available':False}
    value=c.post('/api/market/example',json={}).json()
    assert value['source']=='synthetic' and value['quote']['state']=='synthetic'
    assert c.post('/api/market/search',json={'query':'DEMO'}).status_code==503


def test_owner_profile_isolation_and_no_credentials_in_status_or_errors(setup,caplog):
    app,owner,other,transport=setup
    assert owner.get('/api/market/status').json()['configured']
    assert not other.get('/api/market/status').json()['configured']
    response=other.post('/api/market/search',json={'query':'DEMO'})
    assert response.status_code==503 and response.json()['code']=='setup_required'
    assert transport.calls==[]
    response=owner.post('/api/market/search',json={'query':'DEMO'})
    assert response.status_code==200 and response.json()['instruments']==[]
    assert transport.calls==['assets']
    for body in (owner.get('/api/market/status').text,response.text,caplog.text):
        assert 'syntheticKEY' not in body and 'syntheticSECRET' not in body
    anon=client(app)
    assert anon.post('/api/market/search',json={'query':'DEMO'}).status_code==401


@pytest.mark.parametrize('route,body',[('/api/market/search',{'query':'DEMO'}),('/api/market/prices',{'instrument_id':'bad','mode':'live','days':30})])
def test_market_reads_require_both_csrf_tokens_and_same_origin(setup,route,body):
    _,owner,_,transport=setup
    for headers in ({'X-CSRF-Token':''},{'X-Account-CSRF':''},{'Origin':'https://evil.test'},{'Sec-Fetch-Site':'cross-site'}):
        assert owner.post(route,json=body,headers=headers).status_code==403
    assert owner.post(route,content='x',headers={'Content-Type':'text/plain'}).status_code==415
    assert not transport.calls


def test_payload_bounds_unknown_fields_and_no_arbitrary_urls(setup):
    app,owner,_,transport=setup
    for body in ({'query':'DEMO','url':'https://evil.test'},{'query':None},{'query':'x'*61},{'query':'https://evil.test'}):
        assert owner.post('/api/market/search',json=body).status_code==422
    assert owner.post('/api/market/search',content=b'{"query":"a","query":"b"}',headers={'Content-Type':'application/json'}).status_code==422
    assert owner.post('/api/market/search',content=b' '*(1024*1024+1),headers={'Content-Type':'application/json'}).status_code==413
    assert not transport.calls
    assert owner.post('/api/market/prices',json={'instrument_id':'https://evil.test','mode':'live','days':30}).status_code==422


def test_demo_rejects_overposting_and_cross_origin(setup):
    app,_,_,transport=setup;c=client(app)
    assert c.post('/api/market/example',json={'live':True}).status_code==422
    assert c.post('/api/market/example',json={},headers={'Origin':'https://evil.test'}).status_code==403
    assert c.post('/api/market/example',json={}).status_code==200
    assert not transport.calls


def test_stock_assets_use_local_resources_and_browser_has_no_provider_keys(setup):
    app,_,_,_=setup;c=client(app)
    script=c.get('/static/stocks.js').text
    assert 'APCA-API' not in script and 'https://' not in script
    assert 'localStorage' not in script and 'sessionStorage' not in script
    assert 'innerHTML' not in script
    assert 'document.hidden' in script and 'navigator.locks' in script
    for route in ('/investments','/stocks'):
        html=c.get(route).text
        assert 'aria-label="Investment tools"' in html and 'href="/stocks"' in html
    assert 'aria-current="page">Stocks' in c.get('/stocks').text


def test_signed_in_end_to_end_search_price_daily_history_and_logout(setup):
    from datetime import datetime, timezone
    from decimal import Decimal
    app,owner,other,transport=setup
    identity='22222222-2222-4222-8222-222222222222'
    asset={'id':identity,'symbol':'DEMO','name':'Fictional test stock','exchange':'NYSE','class':'us_equity','status':'active'}
    def get(endpoint,params):
        transport.calls.append(endpoint)
        if endpoint=='assets':return [asset]
        if endpoint=='calendar':return [{'date':'2026-10-28','open':'09:30','close':'16:00'},{'date':'2026-10-29','open':'09:30','close':'16:00'},{'date':'2026-10-30','open':'09:30','close':'16:00'}]
        if endpoint=='trades':return {'trades':{'DEMO':{'t':'2026-10-29T14:59:55Z','p':Decimal('120.40'),'x':'V'}}}
        if endpoint=='bars':return {'bars':{'DEMO':[{'t':'2026-10-28T04:00:00Z','c':'119.25','o':'118','h':'120','l':'117'}]},'next_page_token':None}
        raise AssertionError(endpoint)
    transport.get=get
    app.state.market_service.clock=lambda:datetime(2026,10,29,15,tzinfo=timezone.utc)
    response=owner.post('/api/market/search',json={'query':'test stock'})
    assert response.json()['instruments'][0]['id']==identity
    request={'instrument_id':identity,'mode':'live','days':30}
    result=owner.post('/api/market/prices',json=request)
    assert result.status_code==200
    assert result.json()['quote']['state']=='live' and result.json()['quote']['display_price']=='$120.40'
    assert result.json()['history']['points'][0]['display_close']=='$119.25'
    assert other.post('/api/market/prices',json=request).status_code==503
    daily=owner.post('/api/market/prices',json={**request,'mode':'daily'})
    assert daily.json()['quote']['state']=='daily' and daily.json()['quote']['display_price']=='$119.25'
    count=len(transport.calls)
    assert owner.post('/api/account/logout',json={}).status_code==200
    assert owner.post('/api/market/prices',json=request).status_code==401
    assert len(transport.calls)==count
