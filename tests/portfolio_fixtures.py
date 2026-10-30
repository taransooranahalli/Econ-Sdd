"""Shared fictional market transport; never calls a provider or loads real keys."""
from datetime import date, datetime, timedelta, timezone
from econ_sdd.accounts import Session
from econ_sdd.finance.portfolios import PortfolioDefinition
from econ_sdd.portfolio_service import example_definition

NOW=datetime(2026,10,29,15,0,tzinfo=timezone.utc)
OWNER='11111111-1111-4111-8111-111111111111'
SESSION=Session(OWNER,'Synthetic_QA','synthetic-session-hash','synthetic-csrf')


def real_definition(**changes):
    data=example_definition(date(2026,10,29)).as_record()
    for i,row in enumerate(data['holdings']):
        row['instrument'].update({'provider':'Alpaca','asset_class':'us_equity','symbol':'SYN-A' if i==0 else 'SYN-B','exchange':'NYSE'})
    data.update({'source':'manual','sample_derived':False,**changes})
    return PortfolioDefinition.from_mapping(data)


class Transport:
    def __init__(self, clock, definition):
        self.clock=clock;self.calls=[];self.missing=set();self.old=set();self.invalid=set()
        self.assets=[{'id':h.instrument.id,'symbol':h.instrument.symbol,'name':h.instrument.name,
                      'exchange':h.instrument.exchange,'class':'us_equity','status':'active'} for h in definition.holdings]
    def get(self,endpoint,params):
        self.calls.append((endpoint,dict(params)))
        if endpoint=='assets':return self.assets
        if endpoint=='calendar':return [{'date':d,'open':'09:30','close':'16:00'} for d in ('2026-10-27','2026-10-28','2026-10-29','2026-10-30')]
        if endpoint=='trades':
            return {'trades':{s:{'p':'0' if s in self.invalid else '120.40' if s=='SYN-A' else '80',
                    't':(self.clock()-timedelta(days=1) if s in self.old else self.clock()-timedelta(seconds=10)).isoformat(),'x':'V'}
                    for s in params['symbols'].split(',') if s not in self.missing}}
        if endpoint=='bars':
            symbol=params['symbols']
            return {'bars':{symbol:[] if symbol in self.missing else [{'t':'2026-10-28T04:00:00Z','o':'100','h':'150','l':'1',
                    'c':'120.40' if symbol=='SYN-A' else '80'}]},'next_page_token':None}
        raise AssertionError('Unexpected provider endpoint')
