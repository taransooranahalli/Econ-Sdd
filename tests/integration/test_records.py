import csv
from datetime import datetime, timezone
from decimal import Decimal as D
import io
import json

import pytest

from econ_sdd.finance.savings import ScenarioError, SavingsScenario, calculate_savings
from econ_sdd.serialization.records import export_csv, export_json, load_json, projection_record, scenario_from_record
from econ_sdd.presentation import amount_text


def projection(currency="USD", months=12):
    return calculate_savings(SavingsScenario(D("1000"), D("100"), D("5"), months, currency=currency,
                                            source="manual", sample_derived=True, name="Synthetic savings"))


@pytest.mark.parametrize("currency", ["USD", "EUR", "GBP", "CAD", "AUD", "INR", "JPY", "KWD"])
def test_json_roundtrip_preserves_scenario_and_recomputes(currency):
    original=projection(currency)
    data=load_json(export_json(original).encode())
    assert isinstance(data["summary"]["ending_balance"],str)
    assert data["scenario"]["currency"] == currency
    data["summary"]={"ending_balance":"999999999"}
    data["rows"]="tampered and ignored"
    restored=calculate_savings(scenario_from_record(data))
    assert restored == original
    assert restored.scenario.sample_derived


@pytest.mark.parametrize("currency", ["USD", "JPY", "KWD"])
def test_csv_every_row_and_metadata_match_python(currency):
    original=projection(currency)
    rows=list(csv.DictReader(io.StringIO(export_csv(original))))
    assert len(rows)==13
    for raw,expected in zip(rows,original.rows):
        assert raw["currency"]==currency
        assert raw["closing_balance"]==amount_text(expected.closing_balance,currency)
        assert raw["cumulative_interest"]==amount_text(expected.cumulative_interest,currency)
        assert raw["output_category"]=="conditional_projection"
        assert raw["sample_derived"]=="true"
        assert raw["model_version"]=="savings-v1"
        assert "name" not in raw


def test_maximum_export_can_be_reimported():
    s=SavingsScenario(D("1000000000000"),D("1000000000000"),D("100"),1200)
    result=calculate_savings(s)
    saved=export_json(result).encode()
    assert len(saved)<=1024*1024
    assert scenario_from_record(load_json(saved))==s


@pytest.mark.parametrize("body", [b'[]',b'null',b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}',
    b'{broken',b'{} {}',b'\xff',b'{"a":{"x":1,"x":2}}',b'['*2000+b']'*2000])
def test_invalid_json_is_a_safe_error(body):
    with pytest.raises(ScenarioError):load_json(body)


def test_import_version_guards():
    record=projection_record(projection())
    for field,value in [("schema_version",True),("schema_version",2),("model_version","unknown")]:
        modified={**record,field:value}
        with pytest.raises(ScenarioError):scenario_from_record(modified)


def test_record_provenance_and_utc_metadata():
    now=datetime(2026,10,27,5,0,tzinfo=timezone.utc)
    record=projection_record(projection(),now=now)
    assert record["calculated_at_utc"]=="2026-10-27T05:00:00+00:00"
    assert record["assumptions"]["fx_conversion"] is False
    assert all(record["assumptions"][key]=="not_modeled" for key in ("taxes","fees","inflation"))
    assert record["output_category"]=="conditional_projection"
