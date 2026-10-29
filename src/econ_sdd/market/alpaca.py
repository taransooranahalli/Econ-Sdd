"""Bounded HTTPS GET transport. No trading SDK or configurable destination."""
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request

import truststore
from .models import MarketError, malformed

ALLOWED = {
    'assets': ('paper-api.alpaca.markets', '/v2/assets', 20*1024*1024),
    'calendar': ('paper-api.alpaca.markets', '/v2/calendar', 256*1024),
    'trades': ('data.alpaca.markets', '/v2/stocks/trades/latest', 256*1024),
    'bars': ('data.alpaca.markets', '/v2/stocks/bars', 1024*1024),
}


@dataclass(frozen=True)
class Profile:
    owner_id: str
    key: str = field(repr=False)
    secret: str = field(repr=False)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def reject_constant(_):
    raise ValueError('Nonfinite JSON value')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


class AlpacaTransport:
    def __init__(self, profile):
        self._profile = profile
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context), NoRedirect())

    def get(self, endpoint, params):
        if endpoint not in ALLOWED:
            raise MarketError('blocked_endpoint', 'This provider operation is unavailable.', 422)
        host, path, maximum = ALLOWED[endpoint]
        # All params originate in the adapter; client URLs and pagination URLs are never followed.
        request = Request('https://'+host+path+'?'+urlencode(params), headers={
            'APCA-API-KEY-ID':self._profile.key, 'APCA-API-SECRET-KEY':self._profile.secret,
            'Accept':'application/json', 'User-Agent':'Finance-personal-research/0.6'}, method='GET')
        try:
            with self._opener.open(request, timeout=10) as response:
                if response.headers.get_content_type() != 'application/json':
                    raise malformed()
                body = response.read(maximum+1)
                if len(body) > maximum:
                    raise malformed()
                return json.loads(body, parse_float=Decimal, parse_constant=reject_constant, object_pairs_hook=unique_object)
        except HTTPError as error:
            code = error.code
            retry = error.headers.get('Retry-After', '60')
            error.close()
            if code in (401, 403):
                raise MarketError('provider_access', 'Alpaca rejected access. Check your paper keys and free IEX permissions locally.', 503) from None
            if code == 429:
                seconds = 60
                try:
                    if retry.isascii() and retry.isdigit() and len(retry) <= 6:
                        seconds = int(retry)
                    elif len(retry) <= 80:
                        until = parsedate_to_datetime(retry)
                        if until.tzinfo is not None:
                            seconds = int((until-datetime.now(timezone.utc)).total_seconds())+1
                except (ValueError, TypeError, OverflowError):
                    pass
                seconds = min(900, max(60, seconds))
                raise MarketError('provider_limit', 'Alpaca is limiting requests. Wait before retrying.', 429, seconds) from None
            if code == 404:
                raise MarketError('provider_missing', 'This data is unavailable from Alpaca.', 503) from None
            raise MarketError('provider_error', 'Alpaca could not complete the request. Try again later.', 503) from None
        except (URLError, TimeoutError, OSError):
            raise MarketError('network', 'Cannot reach Alpaca securely. Check your connection and try again.', 503) from None
        except (ValueError, RecursionError, UnicodeError):
            raise malformed() from None
