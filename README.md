# Elon Water Heater

Home Assistant integration for the Elon solar/grid smart water heating device.

## Features

- **Sensors**: Water temperature, ambient temperature, power source, heating state, AC current
- **Controls**: Button to trigger or cancel immediate grid heating
- **Auto-discovery**: Communicates with device via mDNS at `ELON-{serial}.local`

## Requirements

- Home Assistant 2024.11 or later
- Python 3.11+
- Elon water heater device on your network

## Installation
Until this gets published to HACS, you can install it directly from this repository as follows:
- Go to **Settings** → **Add-ons** → **HACS** → **Repositories**
- Add: `https://github.com/yourrepo/elon_water_heater`
- Install from the Integrations tab



### Option 1: HACS (Recommended)
When we get this registered, this will work too
1. Open Home Assistant
2. Go to **Settings** → **Add-ons** → **HACS**
3. Click the **+** button
4. Search for "Elon Water Heater" and install



### Option 2: Manual
For developers, do the folloing 

Copy the `elon_water_heater` folder to your Home Assistant config directory and restart Home Assistant:
```shell
scp -r * root@<your ha instance>:~/config/custom_components/elon_water_heater/
ssh root@<your ha instance> 'ha core restart'
```

## Configuration

### Option A: UI

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Elon Water Heater"
4. Enter your device serial number (found on the device label)
5. Click **Submit**

### Option B: YAML

Add to your `configuration.yaml`:

```yaml
elon_water_heater:
  serial_number: "1234"
```

Replace `1234` with your device serial number.  Restart Home Assistant after adding configuration. It should automatically
add a dashboard for you.

## Entities

| Entity | Description |
|--------|-------------|
| `sensor.elon_water_heater_water_temperature` | Current water temperature (°C) |
| `sensor.elon_water_heater_ambient_temperature` | Ambient temperature (°C) |
| `sensor.elon_water_heater_power_source` | Power source: DC Solar, AC Grid, or Disconnected |
| `sensor.elon_water_heater_heating_state` | Current state: Heating, Solar, Grid (Idle), or Disconnected |
| `sensor.elon_water_heater_ac_current` | AC RMS current (A) |
| `button.elon_water_heater_grid_heating` | Trigger/cancel grid heating |

## Troubleshooting

### Device not found

- Verify the device is powered on and connected to the same network
- Check the serial number is correct
- Ensure mDNS/bonjour is working on your network

### "Failed to connect"

- The device hostname format is `ELON-{serial}.local`
- Try accessing `http://ELON-1234.local/V1/DeviceStatus/Query` in your browser to verify connectivity

## Development

```
elon_water_heater/
├── __init__.py       # Integration entry point
├── api.py            # REST API client
├── button.py         # Button entities
├── config_flow.py    # Configuration flow
├── const.py         # Constants
├── coordinator.py    # Data coordinator
└── sensor.py        # Sensor entities
```

## License

Copyright (C) 2026 PowerOptimal.

This project is licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)** — see [`LICENSE`](LICENSE) for the full text.

In short: you are free to use, modify, and redistribute this software, but any derivative work you distribute must also be released under GPL-3.0-or-later with source. The software is provided **as-is, without warranty of any kind**; if it sets fire to your water heater we will send a sympathetic note and decline all liability.