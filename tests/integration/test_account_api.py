import re
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from econ_sdd.accounts import AccountStore,IDLE_SECONDS,initialize_files
from econ_sdd.security import Keyring
from econ_sdd.web import create_app,STATIC

PASSWORD='synthetic integration password 892!'
NEW_PASSWORD='synthetic replacement password 912!'


@pytest.fixture
def service(tmp_path):
    store=initialize_files(tmp_path/'data'/'users.sqlite3',tmp_path/'keys'/'ring.json')
    now=[1800000000];store.clock=lambda:now[0]
    return store,now,create_app(account_store=store)


def client_for(app,base='http://127.0.0.1'):
    client=TestClient(app,base_url=base)
    page=client.get('/account')
    client.headers['X-CSRF-Token']=re.search(r'name="csrf-token" content="([^"]+)"',page.text).group(1)
    return client


def register(client,username='Alice_QA'):
    response=client.post('/api/account/register',json={'username':username,'password':PASSWORD})
    assert response.status_code==200,response.text
    client.headers['X-Account-CSRF']=response.json()['csrf_token']
    return response


def payload(kind='savings'):
    inputs={
        'investment_growth':{'initial_balance':'1000','monthly_contribution':'100','annual_return_percent':'5','annual_fee_percent':'0','annual_inflation_percent':'2','duration_months':12},
        'savings':{'initial_balance':'1000','monthly_contribution':'100','annual_effective_rate_percent':'5','duration_months':12,'currency':'USD'},
        'goal':{'initial_balance':'1000','goal_amount':'5000','annual_effective_rate_percent':'5','start_date':'2026-10-28','target_date':'2028-10-28','currency':'USD'},
        'cash_flow':{'income':[{'label':'Synthetic pay','amount':'4500'}],'expenses':[{'label':'Synthetic costs','amount':'3000'}],'currency':'USD'},
    }
    return {'title':'Private '+kind,'kind':kind,'inputs':inputs[kind]}


def test_registration_cookie_login_rotation_logout_and_hash_only_database(service):
    store,_,app=service;client=client_for(app);response=register(client)
    assert response.json()['authenticated'] and len(response.json()['recovery_code'])==43
    cookie=response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Path=/' in cookie and 'Secure' not in cookie
    old=client.cookies.get('econ_dev_session')
    assert client.get('/api/account/session').json()['user']['username']=='Alice_QA'
    response=client.post('/api/account/login',json={'username':'ALICE_qa','password':PASSWORD})
    assert response.status_code==200 and client.cookies.get('econ_dev_session')!=old
    client.headers['X-Account-CSRF']=response.json()['csrf_token']
    assert store.session(old) is None
    token=client.cookies.get('econ_dev_session')
    assert client.post('/api/account/logout',json={}).status_code==200
    assert store.session(token) is None and not client.get('/api/account/session').json()['authenticated']
    assert PASSWORD.encode() not in store.path.read_bytes()


@pytest.mark.parametrize('kind,expected',[('savings','$2,277.26'),('goal','$154.92'),('cash_flow','$1,500.00'),('investment_growth','$2,277.26')])
def test_each_calculator_saves_inputs_reopens_recomputes_and_survives_app_restart(service,kind,expected):
    store,_,app=service;client=client_for(app);register(client)
    response=client.post('/api/plans',json=payload(kind));assert response.status_code==200
    saved=response.json()['plan'];assert saved['revision']==1
    record=client.get('/api/plans/'+saved['id']).json()['calculation']
    actual=record['display']['goal']['required_monthly_contribution'] if kind=='goal' else record['display']['summary']['net_cash_flow' if kind=='cash_flow' else 'ending_balance']
    assert actual==expected
    with store.db() as con:row=con.execute('SELECT * FROM plans').fetchone()
    original=store.keys.decrypt(row['ciphertext'],store._plan_aad(row['user_id'],row['id'],row['revision']))
    assert set(original)=={'title','kind','model_version','inputs'} and 'summary' not in original
    restarted=client_for(create_app(account_store=AccountStore(store.path,store.keys,clock=store.clock)))
    restarted.cookies.update(client.cookies)
    assert restarted.get('/api/plans/'+saved['id']).status_code==200
    assert restarted.get('/api/plans').json()['plans'][0]['title']==payload(kind)['title']


@pytest.mark.parametrize('kind',['savings','investment_growth'])
def test_two_users_cannot_read_update_delete_or_list_each_others_data(service,kind):
    _,_,app=service;a=client_for(app);b=client_for(app);register(a);register(b,'Bob_QA')
    saved=a.post('/api/plans',json=payload(kind)).json()['plan'];url='/api/plans/'+saved['id']
    assert b.get('/api/plans').json()=={'plans':[]}
    expected={'errors':{'form':'Saved plan not found.'}}
    for response in [b.get(url),b.get('/api/plans/'+str(uuid4())),
                     b.post(url+'/replace',json={**payload(kind),'revision':1}),b.post(url+'/delete',json={'revision':1})]:
        assert response.status_code==404 and response.json()==expected
    assert a.get(url).status_code==200


@pytest.mark.parametrize('kind',['savings','investment_growth'])
def test_revisions_prevent_lost_updates_and_wrong_deletes(service,kind):
    _,_,app=service;c=client_for(app);register(c);saved=c.post('/api/plans',json=payload(kind)).json()['plan'];url='/api/plans/'+saved['id']
    response=c.post(url+'/replace',json={**payload(kind),'title':'Renamed plan','revision':1})
    assert response.status_code==200 and response.json()['plan']['revision']==2
    assert c.post(url+'/replace',json={**payload(kind),'revision':1}).status_code==409
    assert c.post(url+'/delete',json={'revision':True}).status_code==409
    assert c.post(url+'/delete',json={'revision':2}).status_code==200
    assert c.get(url).status_code==404


def test_account_csrf_is_bound_to_session_and_public_csrf_is_still_required(service):
    _,_,app=service;a=client_for(app);b=client_for(app);register(a);register(b,'Bob_QA')
    for csrf in ['',b.headers['X-Account-CSRF'],b'\xc3\xa9'*64]:
        response=a.post('/api/plans',json=payload(),headers={'X-Account-CSRF':csrf})
        assert response.status_code==403 and response.headers['cache-control']=='no-store'
    assert a.post('/api/plans',json=payload(),headers={'X-CSRF-Token':''}).status_code==403
    assert a.post('/api/plans',json=payload()).status_code==200


@pytest.mark.parametrize('route',['/api/account/register','/api/account/login','/api/account/recover','/api/account/logout',
    '/api/account/password','/api/plans','/api/plans/not-an-id/replace','/api/plans/not-an-id/delete'])
def test_all_mutations_reject_cross_origin_missing_csrf_and_wrong_content_type(service,route):
    _,_,app=service;c=client_for(app);register(c)
    for headers in [{'Origin':'https://evil.example'},{'Sec-Fetch-Site':'cross-site'},{'X-CSRF-Token':''}]:
        response=c.post(route,json={},headers=headers)
        assert response.status_code==403 and 'no-store' in response.headers['cache-control']
    assert c.post(route,content='a=1',headers={'Content-Type':'text/plain'}).status_code==415
    assert c.post(route,content=b' '*(1024*1024+1),headers={'Content-Type':'application/json'}).status_code==413
    assert c.post(route,content=b'{"a":1,"a":2}',headers={'Content-Type':'application/json'}).status_code==422


def test_anonymous_and_disabled_accounts_are_safe(service):
    _,_,app=service;c=client_for(app)
    assert c.get('/api/plans').status_code==401
    assert c.get('/api/plans/'+str(uuid4())).status_code==401
    assert c.post('/api/plans',json=payload()).status_code==401
    disabled=client_for(create_app())
    assert disabled.get('/api/account/session').json()=={'available':False,'authenticated':False}
    assert disabled.post('/api/account/register',json={'username':'Alice_QA','password':PASSWORD}).status_code==503
    assert disabled.post('/api/calculate',json=payload()['inputs']).status_code==200


def test_password_change_and_one_use_recovery_via_api(service):
    _,_,app=service;c=client_for(app);recovery=register(c).json()['recovery_code']
    saved=c.post('/api/plans',json=payload()).json()['plan'];old_cookie=c.cookies.get('econ_dev_session')
    response=c.post('/api/account/password',json={'current_password':PASSWORD,'password':NEW_PASSWORD})
    assert response.status_code==200 and response.json()['recovery_code']!=recovery
    recovery=response.json()['recovery_code'];c.headers['X-Account-CSRF']=response.json()['csrf_token']
    another=client_for(app);another.cookies.set('econ_dev_session',old_cookie)
    assert another.get('/api/plans').status_code==401
    response=c.post('/api/account/recover',json={'username':'Alice_QA','recovery_code':recovery,'password':PASSWORD})
    assert response.status_code==200 and response.json()['recovery_code']!=recovery
    c.headers['X-Account-CSRF']=response.json()['csrf_token']
    assert c.get('/api/plans/'+saved['id']).status_code==200
    assert c.post('/api/account/recover',json={'username':'Alice_QA','recovery_code':recovery,'password':PASSWORD}).status_code==401


def test_login_failure_rate_limit_and_expired_session(service):
    _,now,app=service;c=client_for(app);register(c)
    for _ in range(5):assert c.post('/api/account/login',json={'username':'Alice_QA','password':'wrong'}).status_code==401
    response=c.post('/api/account/login',json={'username':'Alice_QA','password':PASSWORD})
    assert response.status_code==429
    now[0]+=IDLE_SECONDS
    assert c.get('/api/plans').status_code==401


def test_tampered_ciphertext_safe_error_and_model_migration_rejection(service):
    store,_,app=service;c=client_for(app);register(c);saved=c.post('/api/plans',json=payload()).json()['plan'];url='/api/plans/'+saved['id']
    with store.db(write=True) as con:
        row=con.execute('SELECT * FROM plans').fetchone();aad=store._plan_aad(row['user_id'],row['id'],row['revision'])
        value=store.keys.decrypt(row['ciphertext'],aad);value['model_version']='savings-v999'
        con.execute('UPDATE plans SET ciphertext=?',(store.keys.encrypt(value,aad),))
    assert c.get(url).status_code==422
    with store.db(write=True) as con:con.execute('UPDATE plans SET ciphertext=?',('1:not-valid',))
    response=c.get(url)
    assert response.status_code==503 and 'not-valid' not in response.text and 'Traceback' not in response.text


@pytest.mark.parametrize('change',[{'title':''},{'title':'\n'},{'title':'x'*81},{'kind':'options'},
    {'kind':[]},{'owner_id':'another-user'},{'inputs':{'initial_balance':'-1'}}])
def test_invalid_saves_and_overposting_do_not_persist(service,change):
    _,_,app=service;c=client_for(app);register(c)
    assert c.post('/api/plans',json={**payload(),**change}).status_code==422
    assert c.get('/api/plans').json()=={'plans':[]}


def test_private_values_and_credentials_do_not_appear_in_logs_or_errors(service,caplog):
    _,_,app=service;c=client_for(app);response=register(c)
    secret=response.json()['recovery_code'];value=payload();value['title']="safe'; DROP TABLE users; --"
    value['inputs']['initial_balance']='4815162342.12'
    assert c.post('/api/plans',json=value).status_code==200
    assert c.get('/api/account/session').json()['authenticated']
    for marker in [PASSWORD,secret,value['title'],'4815162342.12',c.cookies.get('econ_dev_session')]:assert marker not in caplog.text


def test_explicit_https_config_has_secure_host_cookie_and_rejects_http(service):
    store,_,_=service;app=create_app(account_store=store,public_origin='https://econ.example')
    c=client_for(app,'https://econ.example');response=register(c)
    assert '__Host-econ_session=' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
    assert 'Domain=' not in response.headers['set-cookie'] and response.headers['strict-transport-security']
    assert c.get('/api/plans').status_code==200
    insecure=TestClient(app,base_url='http://econ.example')
    assert insecure.get('/account').status_code==426
    assert c.get('/account',headers={'Host':'evil.example'}).status_code==400
    assert c.post('/api/plans',json=payload(),headers={'Origin':'https://wrong.example'}).status_code==403


@pytest.mark.parametrize('origin',['http://econ.example','https://econ.example/path','https://*.example','https://u:p@econ.example'])
def test_bad_public_origin_fails_closed(origin):
    with pytest.raises(ValueError):create_app(public_origin=origin)


def test_account_pages_have_local_assets_unique_ids_and_safe_text_rendering(service):
    _,_,app=service;c=client_for(app)
    for route in ['/account','/plans','/','/cash-flow']:
        page=c.get(route);assert page.status_code==200 and '__CSRF_TOKEN__' not in page.text
        ids=re.findall(r'\bid="([^"]+)"',page.text);assert len(ids)==len(set(ids))
        assert '/static/account.js' in page.text and '/plans' in page.text
        assert 'https://' not in page.text and page.headers['cache-control']=='no-store'
    script=(STATIC/'account.js').read_text()
    assert 'localStorage' not in script and 'sessionStorage' not in script and 'innerHTML' not in script
    all_ids=set()
    for f in ['index.html','cash-flow.html','account.html','plans.html']:all_ids.update(re.findall(r'\bid="([^"]+)"',(STATIC/f).read_text()))
    literal_ids=set(re.findall(r"\bel\('([^']+)'\)",script));assert literal_ids<=all_ids
