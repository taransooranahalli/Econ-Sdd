"""Owner-scoped market service with bounded requests and in-memory caches."""
from collections import deque
from datetime import datetime, timedelta, timezone
import re
from threading import RLock
from uuid import UUID

from .alpaca import AlpacaTransport
from .models import (NY, MarketError, instrument, iso, malformed, normalize_bars,
                     observation, sessions)


class MarketService:
    def __init__(self, profile=None, *, transport=None, clock=None, setup_error=False):
        self.profile, self.setup_error = profile, setup_error
        self.transport = transport or (AlpacaTransport(profile) if profile else None)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock, self._cache, self._requests = RLock(), {}, deque()
        self._cooldown = None
        self._access_failed = False
        self._active = {}

    def status(self, owner_id):
        ready = bool(self.profile and owner_id == self.profile.owner_id)
        return {'configured':ready, 'provider':'Alpaca', 'feed':'iex', 'currency':'USD',
                'poll_seconds':15, 'setup_error':bool(self.setup_error and owner_id),
                'access_failed':self._access_failed if ready else False}

    def require_owner(self, owner_id):
        if not self.profile or owner_id != self.profile.owner_id:
            raise MarketError('setup_required', 'Alpaca is not configured for this account. Open Setup instructions.', 503)

    def _get(self, endpoint, params, ttl):
        now = self.clock()
        key = (endpoint, tuple(sorted(params.items())))
        cached = self._cache.get(key)
        if cached and 0 <= (now-cached[1]).total_seconds() < ttl:
            return cached
        if self._access_failed:
            raise MarketError('provider_access', 'Check the Alpaca keys and permissions locally, then restart Finance.', 503)
        if self._cooldown and now < self._cooldown:
            raise MarketError('provider_limit', 'Requests are paused. Wait before retrying.', 429,
                              max(1, int((self._cooldown-now).total_seconds())))
        while self._requests and (now-self._requests[0]).total_seconds() >= 60:
            self._requests.popleft()
        if len(self._requests) >= 60:
            raise MarketError('request_limit', 'Too many market requests. Wait one minute.', 429, 60)
        self._requests.append(now)
        try:
            result = self.transport.get(endpoint, params)
        except MarketError as exc:
            if exc.code == 'provider_access':
                self._access_failed = True
            self._cooldown = now+timedelta(seconds=exc.retry_after or 15)
            raise
        fetched = self.clock()
        self._cache[key] = (result, fetched)
        # Bound memory independently of browser/tab behavior.
        if len(self._cache) > 100:
            oldest = min(self._cache, key=lambda k:self._cache[k][1])
            del self._cache[oldest]
        return result, fetched

    def _catalog(self):
        data, _ = self._get('assets', {'status':'active','asset_class':'us_equity'}, 86400)
        if not isinstance(data, list) or len(data) > 100000:
            raise malformed()
        result, ids, symbols = [], set(), set()
        for row in data:
            asset = instrument(row)
            if asset is not None:
                if asset['id'] in ids or asset['symbol'] in symbols:
                    raise malformed()
                result.append(asset)
                ids.add(asset['id']); symbols.add(asset['symbol'])
        return result

    def search(self, owner_id, query):
        self.require_owner(owner_id)
        if not isinstance(query, str) or not re.fullmatch(r'[\w .&\-]{1,60}', query, flags=re.ASCII) or not query.strip():
            raise MarketError('query', 'Enter a ticker or company name, up to 60 letters, numbers or spaces.', 422)
        with self._lock:
            assets = self._catalog()
            needle = query.strip().casefold()
            found = [a for a in assets if needle in a['symbol'].casefold() or needle in a['name'].casefold()]
            found.sort(key=lambda a:(a['symbol'].casefold()!=needle, not a['symbol'].casefold().startswith(needle), a['symbol']))
            return {'instruments':found[:20], 'more_results':len(found)>20, 'provider':'Alpaca', 'source':'provider'}

    def _calendar(self, now):
        today = now.astimezone(NY).date()
        if not 1971 <= today.year <= 2029:
            raise MarketError('calendar_range', 'The reviewed market calendar does not cover this date.', 503)
        start, end = today-timedelta(days=400), min(today+timedelta(days=14), today.replace(month=12,day=31))
        raw, _ = self._get('calendar', {'start':start.isoformat(),'end':end.isoformat(),'date_type':'TRADING'}, 3600)
        return sessions(raw, start, end)

    def _bars(self, asset, days, adjustment, calendar, now):
        cutoff = now.astimezone(NY).date()
        first = cutoff-timedelta(days=days)
        end = datetime.combine(cutoff, datetime.min.time(), NY).astimezone(timezone.utc)-timedelta(microseconds=1)
        # One symbol x <=365 daily points should fit; paginate defensively, never follow URLs.
        params = {'symbols':asset['symbol'], 'timeframe':'1Day','start':first.isoformat(),'end':iso(end),
                  'adjustment':adjustment, 'feed':'iex', 'currency':'USD', 'sort':'asc', 'limit':1000,
                  'asof':cutoff.isoformat()}
        points, tokens, fetched_times = [], set(), []
        for _ in range(3):
            raw, fetched = self._get('bars', params, 1800)
            if not isinstance(raw, dict) or raw.get('feed','iex') != 'iex' or raw.get('currency','USD') != 'USD' or not isinstance(raw.get('bars'), dict) or set(raw['bars'])-{asset['symbol']}:
                raise malformed()
            rows = raw['bars'].get(asset['symbol'], [])
            points.extend(normalize_bars(rows, calendar, cutoff))
            fetched_times.append(fetched)
            token = raw.get('next_page_token')
            if token is None:
                break
            if not isinstance(token, str) or not 1 <= len(token) <= 2048 or token in tokens:
                raise malformed()
            tokens.add(token); params = {**params,'page_token':token}
        else:
            raise MarketError('pagination', 'The provider result is too large. Choose a shorter history range.', 503)
        if len(points) > 400 or len({p['session_date'] for p in points}) != len(points) or points != sorted(points, key=lambda p:p['session_date']):
            raise malformed()
        if any(p['session_date'] < first.isoformat() for p in points):
            raise malformed()
        expected = {d.isoformat() for d in calendar if first <= d < cutoff}
        actual = {p['session_date'] for p in points}
        return {'points':points, 'provider':'Alpaca','feed':'iex','currency':'USD','adjustment':adjustment,
                'fetched_at_utc':iso(min(fetched_times)), 'missing_sessions':sorted(expected-actual),
                'label':'Split-adjusted daily IEX closes · price only, excludes dividend income' if adjustment=='split' else 'Unadjusted daily IEX closes'}

    def detail(self, owner_id, identity, mode='live', days=30):
        self.require_owner(owner_id)
        try:
            identity = str(UUID(identity))
        except (ValueError, TypeError, AttributeError):
            raise MarketError('instrument', 'Choose a listing from the search results.', 422) from None
        if mode not in ('live','daily') or type(days) is not int or days not in (30,90,365):
            raise MarketError('selection', 'Choose Live IEX or Daily close and a supported history range.', 422)
        with self._lock:
            asset = next((a for a in self._catalog() if a['id']==identity), None)
            if asset is None:
                raise MarketError('instrument', 'This listing is unsupported or no longer active. Search again.', 422)
            now = self.clock()
            self._active = {k:v for k,v in self._active.items() if (now-v).total_seconds() < 90}
            if identity not in self._active and len(self._active) >= 20:
                raise MarketError('active_limit', 'At most 20 instruments can refresh across tabs. Close other market views and wait 90 seconds.', 429, 90)
            self._active[identity] = now
            calendar = self._calendar(now)
            if mode == 'live':
                raw, fetched = self._get('trades', {'symbols':asset['symbol'],'feed':'iex','currency':'USD'}, 10)
                if not isinstance(raw, dict) or raw.get('feed','iex') != 'iex' or raw.get('currency','USD') != 'USD' or not isinstance(raw.get('trades'), dict) or set(raw['trades'])-{asset['symbol']}:
                    raise malformed()
                quote = observation(raw['trades'].get(asset['symbol']), fetched, self.clock(), calendar)
            else:
                raw_history = self._bars(asset, 30, 'raw', calendar, now)
                cutoff = now.astimezone(NY).date()
                eligible = [d for d in calendar if d < cutoff]
                required = max(eligible) if eligible else None
                row = next((p for p in raw_history['points'] if p['session_date']==str(required)), None)
                quote = {'state':'daily' if row else 'missing_close', 'price':row['close'] if row else None,
                         'display_price':row['display_close'] if row else 'Unavailable',
                         'label':'Provider daily close for '+str(required) if row else 'Completed session close unavailable',
                         'provider':'Alpaca','feed':'iex','currency':'USD','price_kind':'daily_close','adjustment':'raw',
                         'session_date':str(required) if required else None, 'event_time_utc':None,
                         'fetched_at_utc':raw_history['fetched_at_utc'], 'market_open':False,
                         'same_day_close_pending':bool(cutoff in calendar and now >= calendar[cutoff][1])}
            # History failure must not erase a separately valid latest trade.
            try:
                history = self._bars(asset, days, 'split', calendar, now)
            except MarketError as exc:
                history = {'points':[], 'provider':'Alpaca','feed':'iex','adjustment':'split',
                           'label':'Price history unavailable', 'error':exc.message, 'missing_sessions':[], 'fetched_at_utc':None}
            return {'source':'provider','instrument':asset,'quote':quote,'history':history,
                    'change':{'available':False,'reason':'Day change is unavailable until a comparable previous-close share basis is verified.'},
                    'poll_after_seconds':15 if quote['market_open'] else None}
