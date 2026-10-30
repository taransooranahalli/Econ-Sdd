"""PORT-M01: manual holdings valuation; no web, storage or provider dependencies."""
from dataclasses import dataclass
from datetime import date
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
import re
from uuid import UUID

from .savings import ScenarioError, PRECISION, MAX_AMOUNT

MODEL_VERSION = 'portfolio-holdings-v1'
NUMBER = re.compile(r'\d+(?:\.\d+)?\Z', re.ASCII)
SYMBOL = re.compile(r'[A-Z][A-Z0-9.\-]{0,14}\Z')
VENUES = {'NYSE','NASDAQ','ARCA','AMEX','BATS','NYSEARCA','TXSE'}
DEMO_IDS = ('00000000-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000002')


def bad(field, message):
    raise ScenarioError({field:message})


def amount(value, field, digits=2, maximum=MAX_AMOUNT, positive=False):
    if not isinstance(value,str) or len(value)>64 or not NUMBER.fullmatch(value):
        bad(field,'Enter a nonnegative fixed-point decimal; exponent notation is not supported.')
    parsed=Decimal(value)
    if parsed>maximum or (positive and parsed<=0) or parsed.as_tuple().exponent < -digits:
        bad(field,f'Use a {"positive" if positive else "nonnegative"} amount up to {maximum}, with at most {digits} decimal places.')
    return parsed


def text(value, maximum):
    return (isinstance(value,str) and 1<=len(value)<=maximum and bool(value.strip())
            and not any(ord(c)<32 or 127<=ord(c)<=159 or 0xD800<=ord(c)<=0xDFFF for c in value))


@dataclass(frozen=True, slots=True)
class Identity:
    id: str
    symbol: str
    name: str
    exchange: str
    provider: str
    asset_class: str
    currency: str='USD'
    subtype: None=None

    @classmethod
    def from_mapping(cls, data):
        fields={'id','symbol','name','exchange','provider','asset_class','currency','subtype'}
        if not isinstance(data,dict) or set(data)!=fields:
            bad('holdings','Choose a resolved instrument with supported identity fields.')
        try:identity=str(UUID(data['id']))
        except (ValueError,TypeError,AttributeError):bad('holdings','Use a valid stable instrument ID.')
        if not isinstance(data['symbol'],str) or not SYMBOL.fullmatch(data['symbol']) or not text(data['name'],512):
            bad('holdings','Use a valid resolved symbol and plain-text instrument name.')
        fictional=(data['provider']=='Fictional fixture' and identity in DEMO_IDS and
                    data['symbol']==('DEMO-A' if identity==DEMO_IDS[0] else 'DEMO-B') and
                    data['exchange']=='Fictional' and data['asset_class']=='fictional')
        real=(data['provider']=='Alpaca' and data['asset_class']=='us_equity' and
              isinstance(data['exchange'],str) and data['exchange'] in VENUES)
        if not (fictional or real) or data['currency']!='USD' or data['subtype'] is not None:
            bad('holdings','Only resolved USD Alpaca listings or the labeled fictional examples are supported.')
        return cls(identity,data['symbol'],data['name'],data['exchange'],data['provider'],data['asset_class'])

    def as_record(self):
        return {key:getattr(self,key) for key in ('id','symbol','name','exchange','provider','asset_class','currency','subtype')}


@dataclass(frozen=True, slots=True)
class Holding:
    instrument: Identity
    shares: Decimal
    cost_basis: Decimal|None


@dataclass(frozen=True, slots=True)
class PortfolioDefinition:
    holdings: tuple[Holding,...]
    cash: Decimal
    pricing_mode: str
    as_of_date: date
    quantities_confirmed: bool
    source: str='manual'
    sample_derived: bool=False

    @classmethod
    def from_mapping(cls,data):
        fields={'schema_version','currency','holdings','cash','pricing_mode','as_of_date','quantities_confirmed','source','sample_derived'}
        if not isinstance(data,dict) or set(data)!=fields:
            bad('portfolio','Use the required portfolio definition fields only.')
        if type(data['schema_version']) is not int or data['schema_version']!=1 or data['currency']!='USD':
            bad('portfolio','Use portfolio schema 1 and USD source prices.')
        if data['pricing_mode'] not in ('live','daily'):
            bad('pricing_mode','Choose Live IEX or Daily close for the entire portfolio.')
        if type(data['quantities_confirmed']) is not bool or type(data['sample_derived']) is not bool or data['source'] not in ('manual','sample'):
            bad('portfolio','Use explicit confirmation and source flags.')
        try:
            as_of=date.fromisoformat(data['as_of_date'])
            if as_of.isoformat()!=data['as_of_date']:raise ValueError
        except (ValueError,TypeError):bad('as_of_date','Enter a valid ISO holdings-as-of date.')
        rows=data['holdings']
        if not isinstance(rows,list) or len(rows)>20:
            bad('holdings','Use at most 20 unique holdings.')
        parsed=[];ids=set();symbols=set()
        for i,row in enumerate(rows):
            if not isinstance(row,dict) or set(row)!={'instrument','shares','cost_basis'}:
                bad('holdings', 'Each holding needs resolved identity, shares and optional total cost basis.')
            identity=Identity.from_mapping(row['instrument'])
            if identity.id in ids or (identity.provider,identity.symbol) in symbols:
                bad('holdings','This instrument is already included. Edit the existing row.')
            ids.add(identity.id);symbols.add((identity.provider,identity.symbol))
            shares=amount(row['shares'],f'holdings.{i}.shares',6,Decimal('1000000000'),True)
            cost=None if row['cost_basis'] is None else amount(row['cost_basis'],f'holdings.{i}.cost_basis')
            parsed.append(Holding(identity,shares,cost))
        fictional=any(h.instrument.provider=='Fictional fixture' for h in parsed)
        return cls(tuple(parsed),amount(data['cash'],'cash'),data['pricing_mode'],as_of,data['quantities_confirmed'],
                   data['source'],data['sample_derived'] or data['source']=='sample' or fictional)

    def as_record(self):
        return {'schema_version':1,'currency':'USD','pricing_mode':self.pricing_mode,'cash':format(self.cash,'f'),
                'as_of_date':self.as_of_date.isoformat(),'quantities_confirmed':self.quantities_confirmed,
                'source':self.source,'sample_derived':self.sample_derived,
                'holdings':[{'instrument':h.instrument.as_record(),'shares':format(h.shares,'f'),
                             'cost_basis':None if h.cost_basis is None else format(h.cost_basis,'f')} for h in self.holdings]}


@dataclass(frozen=True, slots=True)
class PricePoint:
    price: Decimal|None
    basis_date: date|None
    state: str
    provider: str='Alpaca'
    feed: str='iex'
    currency: str='USD'
    adjustment: str='raw'
    price_kind: str='eligible_trade'


@dataclass(frozen=True, slots=True)
class HoldingValue:
    holding: Holding
    value: Decimal|None
    weight: Decimal|None
    gain: Decimal|None
    gain_percent: Decimal|None
    state: str


@dataclass(frozen=True, slots=True)
class PortfolioValue:
    definition: PortfolioDefinition
    rows: tuple[HoldingValue,...]
    known_subtotal: Decimal
    total: Decimal|None
    securities: Decimal|None
    cash_weight: Decimal|None
    gain: Decimal|None
    gain_percent: Decimal|None
    priced_count: int
    cost_count: int
    state: str


def value_portfolio(definition, prices, basis_date):
    if not isinstance(definition,PortfolioDefinition) or not isinstance(basis_date,date) or not isinstance(prices,dict):
        raise TypeError('Use a validated portfolio, price mapping and price basis date.')
    # Revalidate even directly constructed definitions; context and boundary stay local.
    definition=PortfolioDefinition.from_mapping(definition.as_record())
    identifiers={h.instrument.id for h in definition.holdings}
    if set(prices)-identifiers:bad('prices','Unexpected instrument in the captured price bundle.')
    with localcontext(Context(prec=PRECISION,rounding=ROUND_HALF_EVEN)):
        raw=[];subtotal=definition.cash;states=[]
        for h in definition.holdings:
            p=prices.get(h.instrument.id)
            value=gain=gain_percent=None;state='unpriced'
            if p is not None:
                if not isinstance(p,PricePoint):bad('prices','Use validated captured observations.')
                expected=('Fictional fixture','none') if h.instrument.provider=='Fictional fixture' else ('Alpaca','iex')
                if (p.provider,p.feed)!=expected or p.currency!='USD' or p.adjustment!='raw':
                    bad('prices','Captured prices must share the selected USD source/feed and unadjusted share basis.')
                expected_kind='daily_close' if definition.pricing_mode=='daily' else 'eligible_trade'
                if p.price_kind!=expected_kind:bad('prices','Do not mix daily closes and latest trades.')
                if p.price is not None:
                    if p.state not in ('live','daily','closed','no_recent_trade','stale','synthetic'):
                        bad('prices','This captured observation is unavailable or needs review.')
                    if (not isinstance(p.price,Decimal) or not p.price.is_finite() or not 0<p.price<=MAX_AMOUNT or p.price.as_tuple().exponent < -24):
                        bad('prices','Captured prices must be finite positive decimals within the reviewed bounds.')
                    if (not definition.quantities_confirmed or definition.as_of_date!=basis_date or p.basis_date!=basis_date):
                        state='needs_review'
                    else:
                        value=h.shares*p.price;subtotal+=value;state='priced';states.append(p.state)
                        if h.cost_basis is not None:
                            gain=value-h.cost_basis
                            gain_percent=100*gain/h.cost_basis if h.cost_basis else None
            raw.append((h,value,gain,gain_percent,state))
        complete=all(row[1] is not None for row in raw)
        total=subtotal if complete else None
        securities=(total-definition.cash) if total is not None else None
        cost_count=sum(h.cost_basis is not None for h in definition.holdings)
        all_costs=bool(raw) and complete and cost_count==len(raw)
        gain=sum((row[2] for row in raw),Decimal(0)) if all_costs else None
        costs=sum((h.cost_basis for h in definition.holdings),Decimal(0)) if all_costs else None
        gain_percent=100*gain/costs if costs else None
        rows=tuple(HoldingValue(h,v,100*v/total if total else None,g,gp,state) for h,v,g,gp,state in raw)
        if not complete:state='needs_review' if any(r.state=='needs_review' for r in rows) else 'partial'
        elif not raw:state='cash_only' if definition.cash else 'empty'
        elif all(h.instrument.provider=='Fictional fixture' for h in definition.holdings):state='synthetic'
        elif definition.pricing_mode=='daily':state='daily'
        elif all(s=='live' for s in states):state='live'
        else:state='last_observed'
        return PortfolioValue(definition,rows,subtotal,total,securities,100*definition.cash/total if total else None,
                              gain,gain_percent,sum(r.value is not None for r in rows),cost_count,state)
