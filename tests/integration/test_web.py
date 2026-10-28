import csv
import io
import json
from pathlib import Path
import re

from fastapi.testclient import TestClient
import pytest

from econ_sdd.web import create_app, STATIC


@pytest.fixture
def client():
    with TestClient(create_app(),base_url="http://127.0.0.1") as client:
        page=client.get("/")
        token=re.search(r'name="csrf-token" content="([^"]+)"',page.text).group(1)
        client.headers.update({"X-CSRF-Token":token})
        yield client


def example(**updates):
    data={"schema_version":1,"initial_balance":"1000","monthly_contribution":"100",
          "annual_effective_rate_percent":"5","duration_months":12,"currency":"USD",
          "contribution_timing":"end","source":"sample","sample_derived":True}
    data.update(updates)
    return data


def test_local_page_assets_and_no_external_runtime_resources(client):
    page=client.get("/")
    assert page.status_code==200 and "__CSRF_TOKEN__" not in page.text
    assert "Savings" in page.text and 'id="currency"' in page.text
    assert 'id="empty-result"' in page.text
    assert 'id="result-content" hidden' in page.text
    assert "no-store" in page.headers["cache-control"]
    assert page.headers["x-frame-options"]=="DENY"
    assert "connect-src 'self'" in page.headers["content-security-policy"]
    for asset in ["styles.css","app.js","fonts/Poppins-400.ttf","fonts/OFL.txt"]:
        assert client.get("/static/"+asset).status_code==200
    script=client.get("/static/app.js").text
    css=client.get("/static/styles.css").text
    assert "https://" not in script+css+page.text
    assert "Math.expm1" not in script and "Math.log1p" not in script
    assert "localStorage" not in script and "sessionStorage" not in script
    assert client.get("/static/../web.py").status_code==404


def test_configuration_currency_contract(client):
    config=client.get("/api/config").json()
    assert config["default_currency"]=="USD"
    assert {c["code"]:c["minor_digits"] for c in config["currencies"]}=={
        "USD":2,"EUR":2,"GBP":2,"CAD":2,"AUD":2,"INR":2,"JPY":0,"KWD":3}


def test_calculation_returns_raw_decimal_and_server_display(client):
    response=client.post("/api/calculate",json=example())
    assert response.status_code==200
    data=response.json()
    assert data["display"]["summary"]["ending_balance"]=="$2,277.26"
    assert data["display"]["summary"]["interest"]=="$77.26"
    assert isinstance(data["summary"]["ending_balance"],str)
    assert len(data["rows"])==len(data["display"]["rows"])==13
    assert data["scenario"]["sample_derived"] is True
    assert data["scenario"]["currency"]=="USD"


@pytest.mark.parametrize("currency,expected", [("USD","$2,277.26"),("EUR","€2,277.26"),
    ("JPY","¥2,277"),("KWD","KWD 2,277.258")])
def test_currency_selection_changes_denomination_without_fx(client,currency,expected):
    data=client.post("/api/calculate",json=example(currency=currency)).json()
    assert data["display"]["summary"]["ending_balance"]==expected
    assert data["assumptions"]["fx_conversion"] is False


def test_invalid_fields_and_currency_precision_are_safe(client):
    value="99999999999999999999.314159"
    response=client.post("/api/calculate",json=example(initial_balance=value))
    assert response.status_code==422
    assert value not in response.text
    assert "initial_balance" in response.json()["errors"]
    response=client.post("/api/calculate",json=example(currency="JPY",monthly_contribution="100.25"))
    assert response.status_code==422
    assert "monthly_contribution" in response.json()["errors"]


def test_exports_and_reimport(client):
    saved=client.post("/api/export/json",json=example())
    assert saved.status_code==200 and saved.headers["content-disposition"].endswith('USD.json"')
    data=saved.json();data["summary"]["ending_balance"]="0"
    loaded=client.post("/api/import",json=data)
    assert loaded.status_code==200
    assert loaded.json()["display"]["summary"]["ending_balance"]=="$2,277.26"
    exported=client.post("/api/export/csv",json=example())
    rows=list(csv.DictReader(io.StringIO(exported.text)))
    assert exported.status_code==200 and len(rows)==13
    assert rows[-1]["closing_balance"]=="2277.26"
    assert all(row["currency"]=="USD" for row in rows)


@pytest.mark.parametrize("route", ["calculate","import","export/json","export/csv"])
def test_duplicate_fields_rejected_everywhere(client,route):
    response=client.post("/api/"+route,content=b'{"initial_balance":"1","initial_balance":"2"}',headers={"Content-Type":"application/json"})
    assert response.status_code==422
    assert "Duplicate" in response.json()["errors"]["file"]


def test_csrf_origin_host_and_content_type_guards(client):
    assert client.post("/api/calculate",json=example(),headers={"X-CSRF-Token":""}).status_code==403
    assert client.post("/api/calculate",json=example(),headers={"Origin":"https://example.org"}).status_code==403
    assert client.post("/api/calculate",json=example(),headers={"Origin":"null"}).status_code==403
    assert client.post("/api/calculate",json=example(),headers={"Sec-Fetch-Site":"cross-site"}).status_code==403
    assert client.post("/api/calculate",content="x=1",headers={"Content-Type":"application/x-www-form-urlencoded"}).status_code==415
    assert client.get("/",headers={"Host":"example.org"}).status_code==400
    assert client.post("/api/calculate",json=example(),headers={"Origin":"http://127.0.0.1"}).status_code==200
    assert "access-control-allow-origin" not in client.options("/api/calculate",headers={"Origin":"https://example.org"}).headers


def test_request_size_and_model_version_guards(client):
    response=client.post("/api/import",content=b" "*(1024*1024+1),headers={"Content-Type":"application/json"})
    assert response.status_code==413
    record=client.post("/api/export/json",json=example()).json()
    record["model_version"]="savings-v999"
    assert client.post("/api/import",json=record).status_code==422


def test_no_financial_values_in_logs_or_errors(client,caplog):
    marker="4815162342.12"
    assert client.post("/api/calculate",json=example(initial_balance=marker)).status_code==200
    assert marker not in caplog.text


def test_browser_script_literal_ids_exist():
    page=(STATIC/"index.html").read_text()
    script=(STATIC/"app.js").read_text()
    ids=set(re.findall(r'\bid="([^"]+)"',page))
    literal_ids=set(re.findall(r"\$\('([^']+)'\)",script))
    assert literal_ids<=ids, literal_ids-ids


@pytest.mark.parametrize("updates,expected,negative,zero", [
    ({"initial_balance":"0","monthly_contribution":"0","duration_months":0},"$0.00",False,True),
    ({"duration_months":0},"$1,000.00",False,False),
    ({"annual_effective_rate_percent":"-5"},None,True,False),
])
def test_zero_duration_and_loss_display_states(client,updates,expected,negative,zero):
    response=client.post("/api/calculate",json=example(**updates))
    assert response.status_code==200
    display=response.json()["display"]
    if expected is not None:assert display["summary"]["ending_balance"]==expected
    assert display["interest_negative"] is negative
    assert display["balance_zero"] is zero
