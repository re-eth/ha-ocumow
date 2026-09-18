# OcuMow for Home Assistant

Experimental Home Assistant custom integration for CLEVA/LawnMaster OcuMow
robot mowers.

> [!IMPORTANT]
> This is an early reverse-engineering release. Monitoring is implemented
> against the Cleva cloud API. Start, pause, stop and dock commands are kept
> disabled until their payloads have been verified on real hardware.

## Current features

- UI configuration flow using the email and password from the OcuMow app
- One `lawn_mower` entity per configured mower
- Battery, status, signal, fault, area, temperature, runtime, distance and
  firmware sensors when supplied by the mower
- Diagnostics download with credentials and token-like values redacted
- Reauthentication flow
- No external Python package dependency

## Installation with HACS

1. In HACS, open **Integrations**.
2. Select the three-dot menu, then **Custom repositories**.
3. Add this repository as an **Integration**.
4. Install **OcuMow**, restart Home Assistant, then go to
   **Settings → Devices & services → Add integration → OcuMow**.

The setup form signs in with the account used by the OcuMow app and discovers
its associated mowers automatically. If the account contains one mower it is
added immediately; if it contains several, the setup flow asks which one to
add.

```yaml
logger:
  logs:
    custom_components.ocumow: debug
```

## Before publishing this repository

Replace every `YOUR_GITHUB_USERNAME` value in `manifest.json` with the real
GitHub username.
Add a repository topic of `home-assistant` and create a GitHub release whose
tag matches the version in `manifest.json`.

## Known limitations

- This integration currently depends on the Cleva/Quectel cloud path. It is
  not a local-LAN or BLE integration.
- Cleva does not publish this API. It may change without notice.
- The login request and response parser are based on APK analysis and accept
  several common response-envelope shapes. The first real-account test may
  reveal an additional header or envelope field.
- Numeric status codes are exposed as `idle` until their meanings are
  confirmed. The raw status remains available in diagnostics.
- Control commands are intentionally unavailable in this release.

## Development

Copy `custom_components/ocumow` into a Home Assistant development instance.
The cloud-facing code is isolated in `api.py`; entity code never depends on
the vendor's raw response shape directly.

Please attach a redacted diagnostics download when opening an issue. Never
post your password, access token, refresh token, device secret, or PIN.

## Legal

This community project is not affiliated with or endorsed by CLEVA,
LawnMaster, OcuMow, or Quectel. Product names are used only to identify
compatible equipment.

Released under the MIT License.
