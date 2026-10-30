"""Portfolio definitions are portable; observed prices/totals are never imported or exported."""
from datetime import date
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
import json

from ..finance.portfolios import MODEL_VERSION, PortfolioDefinition
from ..finance.savings import PRECISION, ScenarioError
from ..presentation import money_text


def definition_record(definition):
    return {'schema_version':1,'model_version':MODEL_VERSION,'output_category':'portfolio_definition',
            'definition':definition.as_record(),'status':'unpriced','prices_omitted':True,
            'note':'Definition only. Source prices and valuation results intentionally omitted; refresh explicitly.'}


def definition_from_record(data):
    if not isinstance(data,dict):raise ScenarioError({'file':'Choose a portfolio definition JSON file.'})
    if 'definition' in data or 'model_version' in data:
        if type(data.get('schema_version')) is not int or data['schema_version']!=1 or data.get('model_version')!=MODEL_VERSION:
            raise ScenarioError({'file':'This portfolio schema/model version needs a reviewed migration.'})
        data=data.get('definition')
    return PortfolioDefinition.from_mapping(data)


def export_definition(definition):
    return json.dumps(definition_record(definition),ensure_ascii=False,allow_nan=False,indent=2)+'\n'


def percent(value):
    if value is None:return 'Unavailable'
    with localcontext(Context(prec=PRECISION,rounding=ROUND_HALF_EVEN)):
        rounded=value.quantize(Decimal('.01'))
        if rounded==0:rounded=rounded.copy_abs()
        return format(rounded,'f')+'%'


def valuation_record(result, bundle):
    money=lambda v:money_text(v,'USD') if v is not None else 'Unavailable'
    raw=lambda v:format(v,'f') if v is not None else None
    summary={k:getattr(result,k) for k in ('known_subtotal','total','securities','cash_weight','gain','gain_percent')}
    rows=[]
    for row in result.rows:
        quote=bundle['quotes'].get(row.holding.instrument.id,{})
        rows.append({'instrument':row.holding.instrument.as_record(),'shares':format(row.holding.shares,'f'),
                     'cost_basis':raw(row.holding.cost_basis),'value':raw(row.value),'weight':raw(row.weight),
                     'gain':raw(row.gain),'gain_percent':raw(row.gain_percent),'state':row.state,'quote':quote,
                     'display':{'price':money(Decimal(quote['price'])) if quote.get('price') is not None else 'Unavailable',
                                'value':money(row.value),'weight':percent(row.weight),'gain':money(row.gain),
                                'gain_percent':percent(row.gain_percent)}})
    labels={'live':'Indicative live IEX value','last_observed':'Last observed value — contains older prices',
            'daily':'Provider daily-close value','partial':'Incomplete — known subtotal only',
            'needs_review':'Needs quantity review — no complete total','cash_only':'Cash-only value',
            'empty':'Empty portfolio','synthetic':'Synthetic example — fictional prices'}
    times=[q['event_time_utc'] for q in bundle['quotes'].values() if q.get('event_time_utc')]
    return {'schema_version':1,'model_version':MODEL_VERSION,'output_category':'observed_portfolio_valuation',
            'definition':result.definition.as_record(),'state':result.state,'label':labels[result.state],
            'summary':{k:raw(v) for k,v in summary.items()},'rows':rows,'cash':format(result.definition.cash,'f'),
            'display':{**{k:money(v) for k,v in summary.items() if k not in ('cash_weight','gain_percent')},
                       'cash':money(result.definition.cash),'cash_weight':percent(result.cash_weight),'gain_percent':percent(result.gain_percent)},
            'priced_count':result.priced_count,'holding_count':len(result.rows),'cost_count':result.cost_count,
            'source':bundle['source'],'basis_date':bundle['basis_date'],'captured_at_utc':bundle['captured_at_utc'],
            'earliest_observation_utc':min(times) if times else None,'latest_observation_utc':max(times) if times else None,
            'live_valid_until_utc':bundle.get('live_valid_until_utc'),
            'market_open':bundle.get('market_open',False),'next_open_utc':bundle.get('next_open_utc'),
            'assumptions':['USD source prices; no FX conversion','Manual quantities and total entered cost basis',
                           'Before future sale costs, spreads/slippage and taxes','No dividend income, tax-lot accounting or portfolio return history']}
