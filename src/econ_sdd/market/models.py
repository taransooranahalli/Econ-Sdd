"""Strict provider normalization and pure observation presentation."""
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
import re
from uuid import UUID
from zoneinfo import ZoneInfo

from ..presentation import money_text

NY = ZoneInfo('America/New_York')
UTC = timezone.utc
SYMBOL = re.compile(r'[A-Z][A-Z0-9.\-]{0,14}\Z')
VENUES = {'NYSE', 'NASDAQ', 'ARCA', 'AMEX', 'BATS', 'NYSEARCA', 'TXSE'}


class MarketError(ValueError):
    def __init__(self, code, message, status=503, retry_after=None):
        self.code, self.message, self.status, self.retry_after = code, message, status, retry_after
        super().__init__('Market data request could not be completed.')


def malformed():
    return MarketError('invalid_data', 'The provider returned incomplete or invalid data. Try again later.')


def timestamp(value):
    try:
        if not isinstance(value, str) or len(value) > 40:
            raise ValueError
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except (ValueError, TypeError, OverflowError):
        raise malformed() from None


def iso(value):
    return value.astimezone(UTC).isoformat().replace('+00:00', 'Z')


def price(value):
    try:
        if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
            raise ValueError
        if len(str(value)) > 60:
            raise ValueError
        result = Decimal(value)
        if not result.is_finite() or not 0 < result <= Decimal('1000000000000') or result.as_tuple().exponent < -24:
            raise ValueError
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise malformed() from None


def instrument(value):
    if not isinstance(value, dict):
        raise malformed()
    if value.get('class') != 'us_equity' or not isinstance(value.get('exchange'),str) or value['exchange'] not in VENUES or value.get('status') != 'active':
        return None
    if value.get('currency', 'USD') != 'USD':
        return None
    symbol, name = value.get('symbol'), value.get('name')
    if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
        return None
    if not isinstance(name, str) or not 1 <= len(name) <= 512 or any(ord(c) < 32 for c in name):
        raise malformed()
    try:
        identity = str(UUID(value['id']))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise malformed() from None
    return {'id': identity, 'symbol': symbol, 'name': name, 'exchange': value['exchange'],
            'asset_class': 'us_equity', 'subtype': None, 'currency': 'USD', 'provider': 'Alpaca'}


def sessions(value, start, end):
    if not isinstance(value, list) or not value or len(value) > 450:
        raise malformed()
    result = {}
    for row in value:
        try:
            day = date.fromisoformat(row['date'])
            if day.isoformat() != row['date'] or not start <= day <= end or day in result:
                raise ValueError
            # The pinned Alpaca v2 calendar uses New York HH:MM session times.
            if not all(isinstance(row[k], str) and re.fullmatch(r'\d{2}:\d{2}', row[k]) for k in ('open', 'close')):
                raise ValueError
            opening = datetime.combine(day, time.fromisoformat(row['open']), NY).astimezone(UTC)
            closing = datetime.combine(day, time.fromisoformat(row['close']), NY).astimezone(UTC)
            if not opening < closing:
                raise ValueError
            result[day] = (opening, closing)
        except (ValueError, TypeError, KeyError):
            raise malformed() from None
    return result


def observation(raw, fetched_at, now, calendar):
    today = now.astimezone(NY).date()
    window = calendar.get(today)
    opened = window is not None and window[0] <= now < window[1]
    base = {'provider': 'Alpaca', 'feed': 'iex', 'currency': 'USD', 'price_kind': 'eligible_trade',
            'adjustment': 'raw', 'fetched_at_utc': iso(fetched_at), 'market_open': opened,
            'session_date': today.isoformat(), 'next_open_utc': next((iso(v[0]) for d, v in sorted(calendar.items()) if v[0] > now), None),
            'session_close_utc': iso(window[1]) if window else None,
            'cache_age_seconds': max(0, int((now-fetched_at).total_seconds())), 'freshness_rules': 'iex-freshness-v1',
            'price': None, 'display_price': 'Unavailable', 'event_time_utc': None}
    if raw is None:
        return {**base, 'state': 'no_trade', 'label': 'No eligible IEX trade available'}
    if not isinstance(raw, dict) or raw.get('x') != 'V' or raw.get('currency','USD') != 'USD' or raw.get('feed','iex') != 'iex':
        raise malformed()
    value, event = price(raw.get('p')), timestamp(raw.get('t'))
    trade_age = (now-event).total_seconds()
    if trade_age < -5 or (fetched_at-event).total_seconds() < -5:
        raise malformed()
    if not opened:
        state, label = 'closed', 'Market closed / last observation'
    elif trade_age > 120 or event < window[0]:
        state, label = 'no_recent_trade', 'No recent IEX trade'
    elif (now-fetched_at).total_seconds() > 30:
        state, label = 'stale', 'Last observation — refresh needed'
    else:
        state, label = 'live', 'Live IEX feed · limited exchange coverage'
    return {**base, 'price': format(value, 'f'), 'display_price': money_text(value, 'USD'),
            'event_time_utc': iso(event), 'trade_age_seconds': max(0, int(trade_age)), 'state': state, 'label': label}


def normalize_bars(rows, calendar, cutoff):
    if not isinstance(rows, list) or len(rows) > 400:
        raise malformed()
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or row.get('currency','USD') != 'USD' or row.get('feed','iex') != 'iex':
            raise malformed()
        stamp = timestamp(row.get('t'))
        local = stamp.astimezone(NY)
        day = local.date()
        if local.time() != time(0) or day not in calendar or day >= cutoff or day in seen:
            raise malformed()
        close = price(row.get('c'))
        # Reject impossible OHLC instead of plotting a misleading close.
        opening, high, low = (price(row.get(k)) for k in ('o', 'h', 'l'))
        if not low <= min(opening, close) <= max(opening, close) <= high:
            raise malformed()
        seen.add(day)
        result.append({'session_date': day.isoformat(), 'bar_start_utc': iso(stamp),
                       'close': format(close, 'f'), 'display_close': money_text(close, 'USD')})
    if result != sorted(result, key=lambda r: r['session_date']):
        raise malformed()
    return result


def demo():
    values = ['100', '101.25', '99.5', '103', '102.25', '106', '105', '109.5', '108.25', '112', '116.75', '120.40']
    days = ['2026-10-01','2026-10-02','2026-10-05','2026-10-06','2026-10-07','2026-10-08',
            '2026-10-09','2026-10-12','2026-10-13','2026-10-14','2026-10-15','2026-10-16']
    return {'source': 'synthetic', 'instrument': {'symbol':'DEMO-A','name':'Fictional Studio Company','exchange':'Fictional',
            'currency':'USD','asset_class':'fictional','subtype':None,'id':'demo-only'},
            'quote': {'state':'synthetic','label':'Synthetic example · not market data','display_price':'$120.40',
                      'price':'120.40','currency':'USD','provider':'Fictional fixture','feed':'none','price_kind':'fictional',
                      'adjustment':'none','event_time_utc':None,'fetched_at_utc':None,'market_open':False},
            'history': {'points':[{'session_date':d,'close':v,'display_close':money_text(Decimal(v),'USD')} for d,v in zip(days,values)],
                        'provider':'Fictional fixture','feed':'none','adjustment':'none','label':'Fictional price path · not a forecast',
                        'fetched_at_utc':None, 'missing_sessions':[]},
            'change': {'available':False,'reason':'Example only. No real previous-close comparison.'}, 'poll_after_seconds':None}
