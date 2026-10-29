"""Transport boundaries verified with synthetic responses, never the live service."""
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from econ_sdd.market.alpaca import AlpacaTransport, NoRedirect, Profile
from econ_sdd.market.models import MarketError


class Response:
    def __init__(self,body=b'{"trades":{}}',content_type='application/json'):
        self.body=body;self.headers=Message();self.headers['Content-Type']=content_type;self.reads=[]
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,limit):self.reads.append(limit);return self.body[:limit]


class Opener:
    def __init__(self,response):self.response=response;self.requests=[]
    def open(self,request,timeout):
        self.requests.append((request,timeout))
        if isinstance(self.response,Exception):raise self.response
        return self.response


def transport(response):
    result=AlpacaTransport(Profile('owner','syntheticKEY','syntheticSECRET'))
    result._opener=Opener(response)
    return result


def test_fixed_https_get_headers_and_exact_decimal_parsing():
    client=transport(Response(b'{"price":123.456789012345678901234}'))
    result=client.get('trades',{'symbols':'DEMO','feed':'iex','currency':'USD'})
    assert str(result['price'])=='123.456789012345678901234'
    request,timeout=client._opener.requests[0]
    assert request.full_url=='https://data.alpaca.markets/v2/stocks/trades/latest?symbols=DEMO&feed=iex&currency=USD'
    assert request.get_method()=='GET' and timeout==10
    assert request.get_header('Apca-api-key-id')=='syntheticKEY'


@pytest.mark.parametrize('endpoint',['https://evil.test','orders','positions','account','/v2/assets'])
def test_unknown_endpoint_cannot_use_credentials(endpoint):
    client=transport(Response())
    with pytest.raises(MarketError):client.get(endpoint,{})
    assert not client._opener.requests


@pytest.mark.parametrize('body',[b'not json',b'{"p":NaN}',b'{"p":1,"p":2}',b'x'*(256*1024+1)])
def test_invalid_duplicate_nonfinite_and_oversize_responses(body):
    client=transport(Response(body))
    with pytest.raises(MarketError):client.get('trades',{})
    assert client._opener.response.reads==[256*1024+1]


@pytest.mark.parametrize('status,code',[(401,'provider_access'),(403,'provider_access'),(429,'provider_limit'),(404,'provider_missing'),(500,'provider_error'),(302,'provider_error')])
def test_provider_errors_are_safe_and_do_not_echo_response(status,code):
    headers=Message();headers['Retry-After']='120'
    error=HTTPError('https://provider.test/private',status,'syntheticSECRET',headers,BytesIO(b'syntheticKEY secret response'))
    client=transport(error)
    with pytest.raises(MarketError) as caught:client.get('trades',{})
    assert caught.value.code==code
    assert 'syntheticKEY' not in caught.value.message and 'syntheticSECRET' not in str(caught.value)
    if status==429:assert caught.value.retry_after==120


@pytest.mark.parametrize('error',[URLError('syntheticSECRET'),TimeoutError('syntheticSECRET')])
def test_network_and_timeout_errors_are_sanitized(error):
    client=transport(error)
    with pytest.raises(MarketError) as caught:client.get('assets',{})
    assert caught.value.code=='network' and 'syntheticSECRET' not in caught.value.message


def test_redirects_and_non_json_content_are_rejected():
    assert NoRedirect().redirect_request(None,None,302,'',{},'https://evil.test') is None
    with pytest.raises(MarketError):transport(Response(b'{}','text/html')).get('trades',{})
