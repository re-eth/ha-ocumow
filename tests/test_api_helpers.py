"""Tests for vendor-response normalisation that do not require hardware."""

from hashlib import sha256

from custom_components.ocumow.api import (
    build_login_payload,
    extract_devices,
    extract_properties,
    find_first_key,
    unwrap_envelope,
)
from custom_components.ocumow.const import API_USER_DOMAIN, API_USER_DOMAIN_SECRET


def test_build_login_payload_matches_apk_algorithm() -> None:
    payload = build_login_payload("owner@example.com", "secret")

    assert payload == {
        "email": "owner@example.com",
        "pwd": "secret",
        "signature": sha256(
            f"owner@example.comsecret{API_USER_DOMAIN_SECRET}".encode()
        ).hexdigest(),
        "userDomain": API_USER_DOMAIN,
    }


def test_find_nested_token() -> None:
    assert find_first_key({"data": {"accessToken": "abc"}}, ("accessToken",)) == "abc"


def test_find_wrapped_access_token() -> None:
    assert (
        find_first_key(
            {"data": {"accessToken": {"expirationTime": 123, "token": "abc"}}},
            ("accessToken", "token"),
        )
        == "abc"
    )


def test_extract_devices() -> None:
    devices = extract_devices(
        {
            "code": 200,
            "data": {
                "rows": [
                    {"deviceId": 123, "deviceName": "Back garden"},
                    {"deviceId": "456", "productName": "OcuMow 18B"},
                    {"deviceName": "Missing ID"},
                ]
            },
        }
    )

    assert [(device.device_id, device.name) for device in devices] == [
        ("123", "Back garden"),
        ("456", "OcuMow 18B"),
    ]


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
