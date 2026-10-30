"""Synthetic batch provider and private capture ownership/freshness boundaries."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from econ_sdd.accounts import Session
from econ_sdd.finance.portfolios import PortfolioDefinition
from econ_sdd.market.alpaca import Profile
from econ_sdd.market.models import MarketError
from econ_sdd.market.service import MarketService
from econ_sdd.portfolio_service import PortfolioService, example_definition

from tests.portfolio_fixtures import NOW, OWNER, SESSION, Transport, real_definition


def environment():
    now=[NOW];d=real_definition();transport=Transport(lambda:now[0],d)
    market=MarketService(Profile(OWNER,'syntheticKEY','syntheticSECRET'),transport=transport,clock=lambda:now[0])
    return PortfolioService(market),d,transport,now


def test_batch_quotes_and_public_only_provider_parameters():
    service,d,transport,_=environment();cap=service.capture(SESSION,d,4);value=service.value(SESSION,d,cap['capture_id'],4)
    assert value['display']['total']=='$2,000.00' and value['state']=='live'
    calls=[p for e,p in transport.calls if e=='trades']
    assert len(calls)==1 and calls[0]=={'symbols':'SYN-A,SYN-B','feed':'iex','currency':'USD'}
    assert not any(set(p)&{'shares','cash','cost_basis','holdings','definition','username'} for _,p in transport.calls)
    capture=next(iter(service._captures.values()))
    assert set(capture)=={'owner','session','hash','revision','expires','bundle'}
    assert all('shares' not in q and 'cost_basis' not in q for q in capture['bundle']['quotes'].values())


def test_capture_owner_session_definition_and_revision_binding():
    service,d,transport,_=environment();cap=service.capture(SESSION,d,2);count=len(transport.calls)
    for session,definition,revision in ((Session('other','Other','token','csrf'),d,2),(Session(OWNER,'Synthetic_QA','rotated','csrf'),d,2),
            (SESSION,real_definition(cash='999'),2),(SESSION,d,3)):
        with pytest.raises(MarketError) as caught:service.value(session,definition,cap['capture_id'],revision)
        assert caught.value.status==409
    assert len(transport.calls)==count


def test_capture_expiry_and_freshness_are_distinct():
    service,d,_,now=environment();cap=service.capture(SESSION,d,1)
    now[0]+=timedelta(seconds=31)
    r=service.value(SESSION,d,cap['capture_id'],1)
    assert r['state']=='last_observed' and r['live_valid_until_utc'] is None
    assert all(row['quote']['state']=='stale' and 'Live' not in row['quote']['label'] for row in r['rows'])
    now[0]+=timedelta(seconds=269)
    with pytest.raises(MarketError):service.value(SESSION,d,cap['capture_id'],1)


def test_market_close_reclassifies_capture_without_repricing():
    service,d,_,now=environment();now[0]=NOW.replace(hour=19,minute=59,second=50)
    cap=service.capture(SESSION,d,1);now[0]+=timedelta(seconds=11)
    r=service.value(SESSION,d,cap['capture_id'],1)
    assert r['state']=='last_observed' and all(row['quote']['state']=='closed' for row in r['rows'])


@pytest.mark.parametrize('problem',['missing','invalid','old'])
def test_missing_invalid_or_different_basis_rows_never_create_a_complete_total(problem):
    service,d,transport,_=environment()
    getattr(transport,problem).add('SYN-B')
    cap=service.capture(SESSION,d,1);r=service.value(SESSION,d,cap['capture_id'],1)
    assert r['summary']['total'] is None and r['priced_count']==1
    assert r['display']['known_subtotal']=='$1,680.00'
    assert all(row['weight'] is None for row in r['rows'])


def test_daily_close_requires_same_user_confirmed_date():
    service,_,_,_=environment();d=real_definition(pricing_mode='daily')
    cap=service.capture(SESSION,d,1);r=service.value(SESSION,d,cap['capture_id'],1)
    assert cap['basis_date']=='2026-10-28' and r['state']=='needs_review'
    d=real_definition(pricing_mode='daily',as_of_date='2026-10-28')
    cap=service.capture(SESSION,d,2);r=service.value(SESSION,d,cap['capture_id'],2)
    assert r['state']=='daily' and r['display']['total']=='$2,000.00'


def test_changed_listing_withholds_that_holding_and_does_not_reassign_it():
    service,d,transport,_=environment();transport.assets[1]['symbol']='NEW-NAME'
    cap=service.capture(SESSION,d,1);r=service.value(SESSION,d,cap['capture_id'],1)
    assert r['rows'][1]['quote']['state']=='listing_review' and r['summary']['total'] is None
    assert [p['symbols'] for e,p in transport.calls if e=='trades']==['SYN-A']


def test_cash_only_does_not_need_provider_profile():
    market=MarketService();service=PortfolioService(market)
    d=real_definition(holdings=[],cash='100',quantities_confirmed=False)
    cap=service.capture(SESSION,d,1);r=service.value(SESSION,d,cap['capture_id'],1)
    assert r['state']=='cash_only' and r['display']['total']=='$100.00'


def test_captures_are_bounded_and_unknown_keys_fail_safely():
    service,d,_,_=environment();first=service.capture(SESSION,d,0)
    for rev in range(1,10):service.capture(SESSION,d,rev)
    assert len(service._captures)==8
    with pytest.raises(MarketError):service.value(SESSION,d,first['capture_id'],0)
    with pytest.raises(MarketError):service.value(SESSION,d,[],0)


def test_other_owner_cannot_trigger_provider_requests():
    service,d,transport,_=environment()
    with pytest.raises(MarketError):service.capture(Session('other','Other','hash','csrf'),d,1)
    assert not transport.calls
