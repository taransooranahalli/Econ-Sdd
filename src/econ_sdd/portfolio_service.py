"""Private, temporary price captures. Shared market caches never receive financial inputs."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import secrets
from threading import RLock

from .finance.portfolios import DEMO_IDS, PortfolioDefinition, PricePoint, value_portfolio
from .market.models import MarketError, NY, iso, timestamp
from .serialization.portfolios import valuation_record


def definition_hash(definition):
    return hashlib.sha256(json.dumps(definition.as_record(),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def revision_number(value):
    if type(value) is not int or not 0<=value<=9007199254740991:
        raise MarketError('revision','Use a valid portfolio input revision.',422)


def example_definition(today):
    def identity(index):
        return {'id':DEMO_IDS[index],'symbol':'DEMO-A' if index==0 else 'DEMO-B',
                'name':'Fictional Studio Company A' if index==0 else 'Fictional Studio Company B',
                'exchange':'Fictional','provider':'Fictional fixture','asset_class':'fictional','currency':'USD','subtype':None}
    return PortfolioDefinition.from_mapping({'schema_version':1,'currency':'USD','pricing_mode':'live','cash':'415.80',
        'as_of_date':today.isoformat(),'quantities_confirmed':True,'source':'sample','sample_derived':True,
        'holdings':[{'instrument':identity(0),'shares':'10.5','cost_basis':'1100'},
                    {'instrument':identity(1),'shares':'4','cost_basis':'360'}]})


class PortfolioService:
    def __init__(self, market):
        self.market=market;self._captures=OrderedDict();self._lock=RLock()

    def _fictional(self, definition):
        if any(h.instrument.provider!='Fictional fixture' for h in definition.holdings):
            raise MarketError('sample','Fictional and real holdings cannot share a price bundle. Remove the example holdings first.',422)
        now=self.market.clock();quotes={}
        for h in definition.holdings:
            quotes[h.instrument.id]={'price':'120.40' if h.instrument.id==DEMO_IDS[0] else '80',
                'state':'synthetic','provider':'Fictional fixture','feed':'none','currency':'USD','adjustment':'raw',
                'price_kind':'eligible_trade' if definition.pricing_mode=='live' else 'daily_close',
                'session_date':definition.as_of_date.isoformat(),'event_time_utc':None,'fetched_at_utc':None,
                'label':'Fictional example price — not market data'}
        return {'source':'synthetic','quotes':quotes,'basis_date':definition.as_of_date.isoformat(),
                'captured_at_utc':iso(now),'market_open':False,'next_open_utc':None}

    def example(self, definition=None):
        definition=definition or example_definition(self.market.clock().astimezone(NY).date())
        bundle=self._fictional(definition)
        return self._value(definition,bundle)

    def capture(self, session, definition, input_revision):
        revision_number(input_revision)
        if not definition.holdings:
            now=self.market.clock();bundle={'source':'cash','quotes':{},'basis_date':now.astimezone(NY).date().isoformat(),
                'captured_at_utc':iso(now),'market_open':False,'next_open_utc':None}
        elif any(h.instrument.provider=='Fictional fixture' for h in definition.holdings):
            bundle=self._fictional(definition)
        else:
            bundle=self.market.portfolio_prices(session.user_id,[h.instrument for h in definition.holdings],definition.pricing_mode)
        capture_id=secrets.token_urlsafe(24);now=self.market.clock()
        with self._lock:
            self._captures=OrderedDict((k,v) for k,v in self._captures.items() if v['expires']>now)
            owned=[k for k,v in self._captures.items() if v['owner']==session.user_id]
            for k in owned[:-7]:self._captures.pop(k)
            self._captures[capture_id]={'owner':session.user_id,'session':session.token_hash,'hash':definition_hash(definition),
                'revision':input_revision,'expires':now+timedelta(minutes=5),'bundle':deepcopy(bundle)}
            while len(self._captures)>64:self._captures.popitem(last=False)
        signature_data={k:{field:q.get(field) for field in ('price','state','event_time_utc','session_date')} for k,q in bundle['quotes'].items()}
        signature=hashlib.sha256(json.dumps(signature_data,sort_keys=True).encode()).hexdigest()
        return {'capture_id':capture_id,'input_revision':input_revision,'signature':signature,
                'basis_date':bundle['basis_date'],'captured_at_utc':bundle['captured_at_utc'],
                'source':bundle['source'],'market_open':bundle.get('market_open',False),'next_open_utc':bundle.get('next_open_utc')}

    def value(self, session, definition, capture_id, input_revision):
        revision_number(input_revision)
        if not isinstance(capture_id,str) or len(capture_id)>100:
            raise MarketError('capture','Refresh prices before valuing this portfolio.',409)
        with self._lock:
            captured=self._captures.get(capture_id)
            if (not captured or captured['owner']!=session.user_id or captured['session']!=session.token_hash
                    or captured['expires']<=self.market.clock()):
                raise MarketError('capture','Prices expired or are unavailable. Refresh prices and revalue.',409)
            if captured['revision']!=input_revision or not secrets.compare_digest(captured['hash'],definition_hash(definition)):
                raise MarketError('capture_changed','The portfolio changed after price capture. Refresh prices and revalue.',409)
            bundle=deepcopy(captured['bundle'])
        return self._value(definition,bundle)

    def _value(self, definition, bundle):
        from datetime import date
        now=self.market.clock();points={};deadlines=[]
        for identity,q in bundle['quotes'].items():
            value=Decimal(q['price']) if q.get('price') is not None else None
            basis=date.fromisoformat(q['session_date']) if q.get('session_date') else None
            if q.get('event_time_utc'):
                event=timestamp(q['event_time_utc']);basis=event.astimezone(NY).date()
                fetched=timestamp(q['fetched_at_utc'])
                close=timestamp(q['session_close_utc']) if q.get('session_close_utc') else None
                if q['state']=='live':
                    if close and now>=close or now.astimezone(NY).date()!=date.fromisoformat(q['session_date']):q['state']='closed'
                    elif (now-event).total_seconds()>120 or (now-fetched).total_seconds()>30:q['state']='stale'
                # An observation captured before the next session never acquires a live badge by waiting.
                if q['state']=='closed' and q.get('next_open_utc') and now>=timestamp(q['next_open_utc']):q['state']='stale'
                if q['state']=='live':
                    deadlines.extend([fetched+timedelta(seconds=30),event+timedelta(seconds=120)])
                    if close:deadlines.append(close)
            if q['state']=='stale':q['label']='Last observation — captured freshness expired'
            elif q['state']=='closed':q['label']='Market closed / last observation'
            points[identity]=PricePoint(value,basis,q['state'],q['provider'],q['feed'],q['currency'],q['adjustment'],q['price_kind'])
        bundle['live_valid_until_utc']=iso(min(deadlines)) if deadlines else None
        result=value_portfolio(definition,points,date.fromisoformat(bundle['basis_date']))
        record=valuation_record(result,bundle)
        record['valued_at_utc']=iso(now)
        return record
