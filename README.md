# Elon Water Heater

Home Assistant integration for the Elon solar/grid smart water heating device.

## Features

- **Water heater entity** exposing the current water temperature *and* an on/off control as a single Apple Home / Matter tile.
- **Sensors**: water temperature, ambient temperature, power source, heating state, AC current.
- **Local polling** over the device's REST interface; auto-discovered on the LAN at `ELON-{serial}.local`.

## Requirements

- Home Assistant 2024.11 or later.
- An Elon water heater on the same LAN, reachable at `ELON-{serial}.local`.

## Installation

There are two supported paths. Pick one.

### Option 1 — HACS (custom repository)

Until this integration is listed in the HACS default repos, you can add it as a custom repository. The screenshots below are for HACS 2.0.x — earlier versions had a separate "Integrations" tab; the steps are the same in spirit.

1. Make sure [HACS](https://hacs.xyz/) is installed and running in your Home Assistant instance, and that you are logged in as an admin / owner.
2. Open **HACS** from the sidebar. You'll land on the main HACS page (sections: *Pending*, *Downloaded*, *New*).
3. On the **page header strip** (the bar containing the "HACS" title), click the **⋮** at the far right — *not* the ⋮ on any individual repository card.
4. Choose **Custom repositories**. A dialog opens with two fields: *Repository* and *Type*.
5. Fill in:
   - **Repository:** `https://github.com/PowerOptimal/elon-smart-ha`
   - **Type:** `Integration`

   Click **Add**.
6. Close the dialog. The Elon Water Heater entry will now show up in HACS — easiest is to search "Elon" from the main page.
7. Click the entry → **Download** → pick the latest version.
8. **Restart Home Assistant** when HACS prompts you to.
9. Continue at [Configuration](#configuration) below.

> If HACS reports the repository as invalid, double-check the URL and that you selected the *Integration* type. HACS reads `hacs.json` at the repo root and the manifest at `custom_components/elon_water_heater/manifest.json`; both must be present (they are, in this repo).

### Option 2 — Manual / development install

For development, or for users without HACS, copy the integration directly onto the Home Assistant host.

From a checkout of this repo:

```sh
# Replace <ha-host> with the hostname or IP of your HA instance.
scp -r custom_components/elon_water_heater  root@<ha-host>:/config/custom_components/

ssh root@<ha-host> 'ha core restart'
```

Only the `custom_components/elon_water_heater/` directory needs to land in `/config/custom_components/` on the host — nothing else from the repo root is required at runtime.

Then continue at [Configuration](#configuration).

## Configuration

### UI (recommended)

1. **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Elon Water Heater**.
3. Enter your device serial number (printed on the device label).
4. **Submit**. A dashboard is created automatically.

### YAML (legacy)

```yaml
elon_water_heater:
  serial_number: "1234"
```

Replace `1234` with the serial number on the device label. Restart Home Assistant.

## Apple Home / Google / Matter

The integration's `water_heater` entity exposes current temperature and on/off as a single tile — it works in Apple Home, Google Home, and Matter controllers via Home Assistant's standard bridge integrations (HomeKit Bridge, Google Assistant, Matter Server). Configuring those bridges is out of scope here; see the Home Assistant docs for [HomeKit Bridge](https://www.home-assistant.io/integrations/homekit/) or [Matter](https://www.home-assistant.io/integrations/matter/).

## Entities

| Entity                                         | Description                                                                |
| ---------------------------------------------- | -------------------------------------------------------------------------- |
| `water_heater.elon_<serial>`                   | Water heater: current temperature + on/off (force / cancel grid heat).     |
| `sensor.elon_<serial>_water_temperature`       | Water temperature (°C).                                                    |
| `sensor.elon_<serial>_ambient_temperature`     | Ambient temperature (°C).                                                  |
| `sensor.elon_<serial>_power_source`            | Power source: DC Solar, AC Grid, Disconnected.                             |
| `sensor.elon_<serial>_heating_state`           | Derived heating state: Heating, Solar, Grid (Idle), Disconnected.          |
| `sensor.elon_<serial>_ac_current`              | AC RMS current (A).                                                        |

## Troubleshooting

### HACS reports a 404 / "repository structure is not valid"

The repo URL must be the canonical one, with the integration at `custom_components/elon_water_heater/`. If you forked the repo and moved files, HACS will refuse it.

### "Device not found" during setup

- The device hostname is `ELON-<serial>.local`. Confirm with:
  ```sh
  curl -X POST -H 'Content-Type: application/json' \
       http://ELON-<serial>.local/V1/DeviceStatus/Query
  ```
- Verify mDNS/Bonjour reaches the HA host (some VLAN setups block it).
- Re-check the serial number is exactly as printed on the device label.

### Heat-now button doesn't light up when pressed

The device's `ForceReheat` call is a no-op when the water is already at the AC target temperature. The tile will show an optimistic *on* state for ~90 s and then revert; this is by design.

## Development

Repository layout:

```
elon-smart-ha/
├── README.md
├── LICENSE
├── hacs.json
└── custom_components/
    └── elon_water_heater/
        ├── __init__.py        # integration entry point
        ├── manifest.json
        ├── api.py             # REST client
        ├── coordinator.py     # data update coordinator
        ├── config_flow.py     # UI setup flow
        ├── const.py
        ├── dashboard.py       # auto-generated Lovelace dashboard
        ├── sensor.py          # sensor entities
        └── water_heater.py    # water_heater entity (temp + on/off)
```

## License

Copyright (C) 2026 PowerOptimal.

Licensed under **GNU General Public License v3.0 or later (GPL-3.0-or-later)** — see [`LICENSE`](LICENSE) for the full text.

In short: free to use, modify, and redistribute, but any derivative work you distribute must also be released under GPL-3.0-or-later with source. Provided **as-is, without warranty of any kind**; if it sets fire to your water heater we will send a sympathetic note and decline all liability.
