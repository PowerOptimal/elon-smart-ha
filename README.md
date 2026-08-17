# Elon Water Heater

Home Assistant integration for the Elon solar/grid smart water heating device.

## Features

- **Water heater entity** exposing the current water temperature *and* an on/off control as a single Apple Home / Matter tile.
- **Grid boost switch** — a plain `switch` entity, so timer add-ons and scheduler cards can drive the geyser directly.
- **Sensors**: water temperature, ambient temperature, power source, heating state, AC current, AC and DC power, last seen.
- **Binary sensors**: connectivity and device alarm, so you can be told when the geyser loses power or faults.
- **Automatic discovery** over mDNS, with recovery when the device is power-cycled or changes address.

## Requirements

- Home Assistant 2024.11 or later. Tested against 2026.8.2.
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

### Automatic discovery

If the device is on the same network as Home Assistant it announces itself over mDNS and appears under **Settings** → **Devices & Services** as a discovered device. Click **Configure** and confirm. Nothing else is needed — the serial number is read from the device's own announcement.

### Manual setup

1. **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Elon Water Heater**.
3. Enter your device serial number (printed on the device label). This is in the form 0000-12345, but don't enter the leading zeros and '-',
   just the numbers which read 12345 in this case.
4. Leave **Host or IP address** blank unless discovery does not work on your network — see [mDNS does not reach the HA host](#mdns-does-not-reach-the-ha-host).
5. **Submit**. A dashboard is created automatically.

## Apple Home / Google / Matter

The integration's `water_heater` entity exposes current temperature and on/off as a single tile — it works in Apple Home, Google Home, and Matter controllers via Home Assistant's standard bridge integrations (HomeKit Bridge, Google Assistant, Matter Server). Configuring those bridges is out of scope here; see the Home Assistant docs for [HomeKit Bridge](https://www.home-assistant.io/integrations/homekit/) or [Matter](https://www.home-assistant.io/integrations/matter/).

## Entities

| Entity                                       | Description                                                            |
| -------------------------------------------- | ---------------------------------------------------------------------- |
| `water_heater.elon_<serial>`                 | Water heater: current temperature + on/off (force / cancel grid heat). |
| `switch.elon_<serial>_grid_boost`            | Grid boost on/off. Same relay as the water heater entity.              |
| `sensor.elon_<serial>_water_temperature`     | Water temperature (°C).                                                |
| `sensor.elon_<serial>_ambient_temperature`   | Ambient temperature (°C).                                              |
| `sensor.elon_<serial>_power_source`          | Power source: DC Solar, AC Grid, Disconnected.                         |
| `sensor.elon_<serial>_heating_state`         | Derived heating state: Heating, Solar, Grid (Idle), Disconnected.      |
| `sensor.elon_<serial>_ac_current`            | AC RMS current (A).                                                    |
| `sensor.elon_<serial>_ac_power`              | Instantaneous AC power draw (W) — derived from AC current × voltage.   |
| `sensor.elon_<serial>_dc_power`              | Instantaneous DC (solar PV) power (W) — derived from DC current × voltage. |
| `sensor.elon_<serial>_last_seen`             | When the device was last polled successfully. Stays available while it is offline. |
| `binary_sensor.elon_<serial>_connectivity`   | On while the device is reachable. Stays available while it is offline. |
| `binary_sensor.elon_<serial>_alarm`          | On when the device reports a fault, such as an element drawing no current. |

### Timed boosts

`switch.elon_<serial>_grid_boost` is an ordinary switch, so anything that drives a switch will drive the geyser — timer helpers, the Simple Timer add-on, scheduler cards, or a two-line automation:

```yaml
automation:
  - alias: Morning geyser boost
    trigger:
      - platform: time
        at: "05:30:00"
    action:
      - action: switch.turn_on
        target:
          entity_id: switch.elon_1234_grid_boost
      - delay: "00:30:00"
      - action: switch.turn_off
        target:
          entity_id: switch.elon_1234_grid_boost
```

The switch and the `water_heater` entity control the same relay and always report the same state; use whichever suits the automation.

### Knowing when the geyser loses power

`binary_sensor.elon_<serial>_connectivity` stays available when the device does not, which makes it the thing to build a notification on:

```yaml
automation:
  - alias: Geyser offline
    trigger:
      - platform: state
        entity_id: binary_sensor.elon_1234_connectivity
        to: "off"
        for: "00:15:00"
    action:
      - action: notify.persistent_notification
        data:
          message: "Elon geyser has been unreachable for 15 minutes — check its power."
```

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

### mDNS does not reach the HA host

Some networks — routed VLANs, guest networks, or setups without an mDNS reflector — will not carry the device's announcements to Home Assistant. In that case:

1. Give the device a fixed DHCP reservation on your router.
2. Add the integration manually and enter that address in the **Host or IP address** field.

The integration then talks to the address directly and never uses mDNS. Note that a fixed address is only as stable as the reservation — if the device later moves, you must update the entry by hand.

### Everything shows "unavailable"

The device is not answering. Check that it has power and is on the network; `binary_sensor.elon_<serial>_connectivity` and `sensor.elon_<serial>_last_seen` remain available and will tell you when contact was lost. The integration re-resolves the address and reconnects on its own once the device returns — restarting Home Assistant is not required.

### The tile turns on but the water is not heating

That is usually correct behaviour, not a fault. The device engages the grid relay on a boost request whether or not the element then draws power, and a tank already at its target temperature draws nothing. Check `sensor.elon_<serial>_heating_state`:

- **Heating** — grid engaged and the element is drawing current.
- **Grid (Idle)** — grid engaged but no meaningful draw, normal at target temperature.

If it reads *Grid (Idle)* on a cold tank, the element or its wiring is suspect; the device will usually raise `binary_sensor.elon_<serial>_alarm` shortly afterwards. That alarm latches and stays on until the device is restarted.

## Development

Repository layout:

```
elon-smart-ha/
├── README.md
├── LICENSE
├── hacs.json
├── justfile
├── pytest.ini
├── requirements-test.txt
├── docs/plans/            # design notes
├── tests/
└── custom_components/
    └── elon_water_heater/
        ├── __init__.py        # integration entry point
        ├── manifest.json
        ├── api.py             # REST client
        ├── coordinator.py     # polling, addressing, boost state
        ├── discovery.py       # mDNS address resolution
        ├── entity.py          # shared entity base
        ├── config_flow.py     # UI setup and discovery flow
        ├── const.py
        ├── dashboard.py       # auto-generated Lovelace dashboard
        ├── binary_sensor.py   # connectivity and alarm
        ├── sensor.py          # sensor entities
        ├── switch.py          # grid boost switch
        └── water_heater.py    # water_heater entity (temp + on/off)
```

### Tests

```sh
just setup   # create .venv and install the HA test harness
just test    # run the suite
```

The fixtures in `tests/conftest.py` are payloads recorded from real hardware, including a unit with no element attached — that is the case which exposed the boost-state bug, because the device engages the grid relay without drawing any current.

## License

Copyright (C) 2026 PowerOptimal.

Licensed under **GNU General Public License v3.0 or later (GPL-3.0-or-later)** — see [`LICENSE`](LICENSE) for the full text.

In short: free to use, modify, and redistribute, but any derivative work you distribute must also be released under GPL-3.0-or-later with source. Provided **as-is, without warranty of any kind**; if it sets fire to your water heater we will send a sympathetic note and decline all liability.
