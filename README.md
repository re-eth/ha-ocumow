# OcuMow for Home Assistant

An experimental Home Assistant custom integration for CLEVA/LawnMaster OcuMow
robot mowers.

> [!IMPORTANT]
> This integration was created by reverse engineering the OcuMow app and uses
> the unofficial CLEVA/Quectel cloud services. It has primarily been tested
> with an OcuMow 18B. Other models may expose different properties or command
> behaviour.

## Features

- Configuration through the Home Assistant UI using the email address and
  password from the OcuMow app
- Automatic discovery of mowers associated with the account
- One `lawn_mower` entity per configured mower, with start/resume, pause and
  return-to-dock controls
- Persistent cloud WebSocket updates with one-minute polling as a fallback
- Immediate command feedback with short-lived faster polling while the cloud
  catches up
- Battery level and translated mower status
- Mowing area shown as **Main** or **Other**, matching the app
- Blade time, running time and startup/powered-on time
- Total travelled distance and working distance
- Mainboard and battery temperatures
- Signal quality, firmware, fault description, and cloud connection history
- Weekly schedule summary and calculated next cut
- Rain-sensor enabled state and configured post-rain delay
- Online connectivity and stopped-state binary sensors
- A button to reset the blade-time counter
- Diagnostics downloads with credentials, device secrets and tokens redacted
- Reauthentication when the stored account credentials are rejected
- Automatic renewal of expired cloud access tokens
- No external Python package dependency

Entities are shown as unavailable when the mower or cloud does not supply the
corresponding property.

## Installation with HACS

Until this repository is included in the default HACS catalogue, add it as a
custom repository:

1. Open **HACS**.
2. Select the three-dot menu in the top-right corner, then
   **Custom repositories**.
3. Enter `https://github.com/re-eth/ha-ocumow`.
4. Select **Integration** and choose **Add**.
5. Find and install **OcuMow**.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration → OcuMow**.

The setup form signs in with the same account used by the OcuMow app. The
integration uses the European cloud endpoint selected by the app. If the
account contains one mower, it is added immediately; if it contains several,
Home Assistant asks which mower to add.

## Entities

The exact entities available depend on the information returned by the mower.

| Entity | Description |
| --- | --- |
| Lawn mower | Current activity and start, pause and dock controls |
| Battery | Remaining battery percentage |
| Status | Human-readable mower state, such as Standby, Charging or Automatically mowing |
| Mowing area | Selected **Main** or **Other** mowing area |
| Blade time | Time accumulated by the current blades; reset after replacing them |
| Running time | Total time the mower has operated |
| Startup time | Cumulative powered-on time reported by the app |
| Total travelled distance | Overall distance reported by the mower |
| Working distance | Separate working-distance counter exposed by the cloud |
| Schedules | Enabled weekly mowing periods; full details are also stored in its attributes |
| Schedule mode | Shows whether automatic scheduled mowing is enabled and allows it to be switched on or off |
| Next cut | Next enabled schedule start, calculated in the Home Assistant timezone |
| Rain sensor enabled | Whether the mower's rain-sensor setting is enabled |
| Rain delay | Configured delay before mowing resumes after rain |
| Online | Whether the mower is connected to the vendor cloud |
| Stopped | Raw stopped flag reported by the mower |
| Fault | Human-readable fault description, while retaining unknown numeric codes |
| Reset blade time | Sends the same blade-counter reset command used by the app |

Temperature, signal-quality, firmware, cloud-connected-since, and last-cloud-
disconnection diagnostic entities are also provided when available.

## Command behaviour

Live mower changes and controls use the cloud WebSocket protocol observed in
OcuMow app version 1.3.15. A command can be accepted by the cloud but refused
by the mower, for example when mowing is not allowed at night or another
operating restriction is active. Home Assistant preserves the mower's fault
state so the reason can be inspected.

The blade-time reset is also cloud controlled. The statistics endpoint can
lag behind a successful reset acknowledgement, so its displayed value may
take a short time to update.

Individual schedule times and rain settings are currently read-only in Home Assistant.

## Troubleshooting

Enable debug logging if you need to diagnose cloud communication:

```yaml
logger:
  logs:
    custom_components.ocumow: debug
```

After restarting Home Assistant, reproduce the issue and download diagnostics
from the OcuMow device page. Attach the redacted diagnostics file when opening
an issue.

Never post your password, access token, refresh token, device secret or mower
PIN. Although the integration redacts known sensitive fields, check a
diagnostics file before sharing it publicly.

## Known limitations

- This is a cloud integration, not a local-LAN or Bluetooth
  integration. Internet and vendor-cloud availability are required.
- CLEVA does not publish or support this API, so it may change without notice.
- Compatibility and command behaviour may vary between mower models and
  firmware versions.
- The integration currently uses the European cloud configuration recovered
  from the app.
- Schedule-time and rain-setting changes must still be made in the OcuMow app.

## Development

Copy `custom_components/ocumow` into a Home Assistant development instance.
The cloud-facing code is isolated in `api.py`; entity code does not depend on
the vendor's raw response envelope directly.

## Legal

This community project is not affiliated with or endorsed by CLEVA,
LawnMaster, OcuMow or Quectel. Product names are used only to identify
compatible equipment.

Released under the MIT License.
