"""Synthetic provider fixtures: no network, credentials or real price snapshots."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, getcontext
import json
from uuid import UUID

import pytest

from econ_sdd.market.alpaca import Profile
from econ_sdd.market.config import load_profile
from econ_sdd.market.models import (MarketError, NY, demo, instrument, normalize_bars,
                                    observation, price, sessions)
from econ_sdd.market.service import MarketService

OWNER='11111111-1111-4111-8111-111111111111'
ASSET_ID='22222222-2222-4222-8222-222222222222'
NOW=datetime(2026,10,29,15,0,tzinfo=timezone.utc)
ASSET={'id':ASSET_ID,'symbol':'DEMO','name':'Fictional Test Equity','class':'us_equity','exchange':'NYSE','status':'active'}


def calendar_rows():
    return [{'date':day,'open':'09:30','close':'13:00' if day=='2026-11-27' else '16:00'} for day in
            ('2026-03-06','2026-03-09','2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-10-30','2026-11-02','2026-11-27')]


def calendar():
    return sessions(calendar_rows(),date(2026,1,1),date(2026,12,31))


def bar(day='2026-10-28', close='120.40'):
    local=datetime.combine(date.fromisoformat(day),datetime.min.time(),NY)
    return {'t':local.isoformat(),'o':'100','h':'125','l':'90','c':close}


class FakeTransport:
    def __init__(self, clock=None):
        self.calls=[];self.failure=None;self.clock=clock or (lambda:NOW);self.no_trade=False;self.no_bar=False
        self.catalog=[ASSET]
    def get(self, endpoint, params):
        self.calls.append((endpoint,dict(params)))
        if self.failure:
            raise self.failure
        if endpoint=='assets':return self.catalog
        if endpoint=='calendar':
            return [r for r in calendar_rows() if params['start']<=r['date']<=params['end']]
        if endpoint=='trades':
            return {'trades':{} if self.no_trade else {'DEMO':{'t':(self.clock()-timedelta(seconds=10)).isoformat(),'p':Decimal('120.40'),'x':'V'}}}
        if endpoint=='bars':return {'bars':{'DEMO':[] if self.no_bar else [bar()]},'next_page_token':None}
        raise AssertionError('Unexpected endpoint')


def service():
    now=[NOW];transport=FakeTransport(lambda:now[0]);market=MarketService(Profile(OWNER,'syntheticKEY','syntheticSECRET'),transport=transport,clock=lambda:now[0])
    return market,transport,now


@pytest.mark.parametrize('value',[0,-1,True,None,[],float('nan'),'NaN','Infinity','0.0000000000000000000000001','1000000000001'])
def test_invalid_prices_are_unavailable(value):
    with pytest.raises(MarketError):price(value)


def test_source_precision_and_global_context_are_preserved():
    previous=getcontext().copy()
    raw={'t':NOW.isoformat(),'p':Decimal('113.345'),'x':'V'}
    result=observation(raw,NOW,NOW,calendar())
    assert result['price']=='113.345' and result['display_price']=='$113.34'
    assert getcontext().prec==previous.prec


@pytest.mark.parametrize('change',[{'exchange':'OTC'},{'class':'crypto'},{'status':'inactive'},{'symbol':'BAD/SYMBOL'}])
def test_unsupported_listings_are_excluded(change):
    assert instrument({**ASSET,**change}) is None


def test_asset_identity_and_unknown_subtype_remain_explicit():
    asset=instrument(ASSET)
    assert asset['id']==ASSET_ID and asset['subtype'] is None and asset['currency']=='USD'
    with pytest.raises(MarketError):instrument({**ASSET,'id':'not-an-id'})


def test_calendar_dst_holiday_weekend_and_early_close():
    c=calendar()
    assert c[date(2026,3,6)][0].hour==14
    assert c[date(2026,3,9)][0].hour==13
    assert c[date(2026,11,2)][0].hour==14
    assert c[date(2026,11,27)][1].hour==18
    for now in (datetime(2026,11,26,16,tzinfo=timezone.utc),datetime(2026,10,31,16,tzinfo=timezone.utc),datetime(2026,11,27,19,tzinfo=timezone.utc)):
        result=observation({'p':'100','t':now.isoformat(),'x':'V'},now,now,c)
        assert not result['market_open'] and result['state']=='closed'


@pytest.mark.parametrize('age,state',[(-5,'live'),(-6,None),(0,'live'),(120,'live'),(121,'no_recent_trade')])
def test_live_trade_age_boundaries(age,state):
    raw={'p':'100','t':(NOW-timedelta(seconds=age)).isoformat(),'x':'V'}
    if state is None:
        with pytest.raises(MarketError):observation(raw,NOW,NOW,calendar())
    else:assert observation(raw,NOW,NOW,calendar())['state']==state


def test_cached_fetch_age_does_not_become_live_again():
    raw={'p':'100','t':NOW.isoformat(),'x':'V'}
    assert observation(raw,NOW,NOW+timedelta(seconds=31),calendar())['state']=='stale'
    assert observation(None,NOW,NOW,calendar())['state']=='no_trade'
    with pytest.raises(MarketError):observation({**raw,'x':'N'},NOW,NOW,calendar())


@pytest.mark.parametrize('rows',[[bar('2026-10-29')],[bar(),bar()],[{**bar(),'t':'2026-10-28T14:00:00Z'}],[{**bar(),'c':'130'}],[{**bar(),'c':'0'}]])
def test_current_duplicate_bad_timestamp_and_impossible_bars_rejected(rows):
    with pytest.raises(MarketError):normalize_bars(rows,calendar(),date(2026,10,29))


def test_owner_isolation_precedes_all_provider_requests():
    market,transport,_=service()
    assert not market.status('another-owner')['configured']
    with pytest.raises(MarketError):market.search('another-owner','DEMO')
    with pytest.raises(MarketError):market.detail('another-owner',ASSET_ID)
    assert transport.calls==[]


def test_resolved_identity_explicit_feed_currency_and_completed_history():
    market,transport,_=service()
    result=market.search(OWNER,'Fictional')
    assert result['instruments'][0]['id']==ASSET_ID
    result=market.detail(OWNER,ASSET_ID)
    assert result['quote']['state']=='live' and result['quote']['provider']=='Alpaca'
    assert result['history']['points'][0]['close']=='120.40'
    assert not result['change']['available']
    for endpoint,params in transport.calls:
        if endpoint in ('trades','bars'):
            assert params['feed']=='iex' and params['currency']=='USD'
    bars=next(params for endpoint,params in transport.calls if endpoint=='bars')
    assert bars['adjustment']=='split' and bars['end']<'2026-10-29T04:00:00Z'


def test_cached_requests_coalesce_and_keep_original_retrieval_time():
    market,transport,now=service()
    first=market.detail(OWNER,ASSET_ID)
    count=len(transport.calls);now[0]+=timedelta(seconds=5)
    second=market.detail(OWNER,ASSET_ID)
    assert len(transport.calls)==count
    assert second['quote']['fetched_at_utc']==first['quote']['fetched_at_utc']
    now[0]+=timedelta(seconds=6);market.detail(OWNER,ASSET_ID)
    assert len(transport.calls)==count+1


def test_daily_close_is_raw_and_missing_close_never_uses_old_bar():
    market,transport,_=service()
    result=market.detail(OWNER,ASSET_ID,'daily')
    assert result['quote']['session_date']=='2026-10-28' and result['quote']['state']=='daily'
    assert result['quote']['event_time_utc'] is None
    assert {p['adjustment'] for e,p in transport.calls if e=='bars'}=={'raw','split'}
    market,transport,_=service();transport.no_bar=True
    result=market.detail(OWNER,ASSET_ID,'daily')
    assert result['quote']['state']=='missing_close' and result['quote']['price'] is None


def test_no_trade_or_empty_chart_remains_explicit():
    market,transport,_=service();transport.no_trade=True;transport.no_bar=True
    result=market.detail(OWNER,ASSET_ID)
    assert result['quote']['price'] is None and result['history']['points']==[]
    assert result['history']['missing_sessions']


def test_entitlement_failure_is_latched_without_retries_or_secret_errors():
    market,transport,_=service();transport.failure=MarketError('provider_access','Synthetic access failure')
    for _ in range(2):
        with pytest.raises(MarketError):market.search(OWNER,'DEMO')
    assert len(transport.calls)==1 and market.status(OWNER)['access_failed']


def test_429_cooldown_and_local_request_budget():
    market,transport,now=service();transport.failure=MarketError('provider_limit','Wait',429,120)
    for _ in range(2):
        with pytest.raises(MarketError) as caught:market.search(OWNER,'DEMO')
        assert caught.value.status==429
    assert len(transport.calls)==1
    transport.failure=None;now[0]+=timedelta(seconds=120)
    assert market.search(OWNER,'DEMO')['instruments']
    market._requests=__import__('collections').deque([now[0]]*60)
    with pytest.raises(MarketError) as caught:market._get('trades',{'symbols':'DEMO'},0)
    assert caught.value.code=='request_limit'


@pytest.mark.parametrize('identity,mode,days', [('bad','live',30),(ASSET_ID,'sip',30),(ASSET_ID,'live',True),(ASSET_ID,'live',1000000)])
def test_invalid_client_options_never_reach_provider(identity,mode,days):
    market,transport,_=service()
    with pytest.raises(MarketError):market.detail(OWNER,identity,mode,days)
    assert not transport.calls


def test_catalog_duplicates_and_unknown_ids_fail_closed():
    market,transport,_=service();transport.catalog=[ASSET,ASSET]
    with pytest.raises(MarketError):market.search(OWNER,'DEMO')
    market,transport,_=service()
    with pytest.raises(MarketError):market.detail(OWNER,'33333333-3333-4333-8333-333333333333')
    assert [e for e,_ in transport.calls]==['assets']


def test_synthetic_example_is_not_mislabeled_as_live():
    result=demo()
    assert result['source']=='synthetic' and result['quote']['state']=='synthetic'
    assert result['quote']['provider']=='Fictional fixture' and not result['poll_after_seconds']


def test_profile_permissions_validation_and_redacted_repr(tmp_path):
    path=tmp_path/'alpaca.json'
    assert load_profile(path)==(None,False)
    value={'schema_version':1,'owner_id':OWNER,'key':'syntheticKEY','secret':'syntheticSECRET','personal_display_confirmed':True}
    path.write_text(json.dumps(value));path.chmod(0o600)
    profile,error=load_profile(path)
    assert not error and profile.owner_id==OWNER
    assert value['key'] not in repr(profile) and value['secret'] not in repr(profile)
    path.chmod(0o644);assert load_profile(path)==(None,True)
    path.chmod(0o600);path.write_text(json.dumps({**value,'personal_display_confirmed':False}))
    assert load_profile(path)==(None,True)
    path.write_text('{bad');assert load_profile(path)==(None,True)


def test_calendar_unsupported_year_and_malformed_session_are_unavailable():
    market,_,now=service();now[0]=NOW.replace(year=2030)
    with pytest.raises(MarketError) as caught:market.detail(OWNER,ASSET_ID)
    assert caught.value.code=='calendar_range'
    with pytest.raises(MarketError):sessions([{'date':'2026-10-29','open':'16:00','close':'09:30'}],date(2026,1,1),date(2026,12,31))

@pytest.mark.parametrize('change',[{'feed':'sip'},{'currency':'EUR'}])
def test_wrong_source_or_currency_is_never_a_live_observation(change):
    with pytest.raises(MarketError):observation({'p':'100','t':NOW.isoformat(),'x':'V',**change},NOW,NOW,calendar())


def test_history_pagination_is_bounded_and_does_not_follow_urls():
    market,transport,_=service();original=transport.get
    def get(endpoint,params):
        if endpoint=='bars':return {'bars':{'DEMO':[bar()]},'next_page_token':'https://evil.test/secret'}
        return original(endpoint,params)
    transport.get=get
    result=market.detail(OWNER,ASSET_ID)
    assert result['history']['points']==[] and 'error' in result['history']
    # A repeated token fails rather than following it as a URL or returning partial history.
    assert result['quote']['state']=='live'


def test_provider_history_error_does_not_replace_a_valid_quote():
    market,transport,_=service();original=transport.get
    def get(endpoint,params):
        if endpoint=='bars':raise MarketError('provider_error','History temporarily unavailable')
        return original(endpoint,params)
    transport.get=get
    result=market.detail(OWNER,ASSET_ID)
    assert result['quote']['price']=='120.40'
    assert result['history']['error']=='History temporarily unavailable'


def test_close_missing_on_required_day_does_not_carry_older_price_forward():
    market,transport,_=service();original=transport.get
    def get(endpoint,params):
        if endpoint=='bars':return {'bars':{'DEMO':[bar('2026-10-27')]},'next_page_token':None}
        return original(endpoint,params)
    transport.get=get
    result=market.detail(OWNER,ASSET_ID,'daily')
    assert result['quote']['state']=='missing_close' and result['quote']['price'] is None
    assert result['history']['points'][0]['session_date']=='2026-10-27'


def test_active_instrument_limit_precedes_price_calls():
    market,transport,_=service();market._active={str(UUID(int=i)):NOW for i in range(20)}
    with pytest.raises(MarketError) as caught:market.detail(OWNER,ASSET_ID)
    assert caught.value.code=='active_limit'
    assert [e for e,_ in transport.calls]==['assets']
