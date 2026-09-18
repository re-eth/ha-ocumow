"""Tests for vendor-response normalisation that do not require hardware."""

from custom_components.ocumow.api import extract_properties, find_first_key, unwrap_envelope


def test_find_nested_token() -> None:
    assert find_first_key({"data": {"accessToken": "abc"}}, ("accessToken",)) == "abc"


def test_unwrap_envelope() -> None:
    assert unwrap_envelope({"code": 0, "data": {"result": {"Soc": 87}}}) == {"Soc": 87}


def test_extract_property_list() -> None:
    payload = {
        "properties": [
            {"code": "Soc", "value": 87},
            {"code": "Status", "value": "mowing"},
        ]
    }
    assert extract_properties(payload) == {"Soc": 87, "Status": "mowing"}
