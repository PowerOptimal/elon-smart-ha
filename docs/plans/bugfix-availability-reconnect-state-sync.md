# Bug fixes: availability, mDNS reconnect, app→HA state sync, switch entity

**Date:** 2026-08-17
**Branch:** main
**Status:** proposed

## Problem

Six field reports against the Elon HA integration reduce to three defects and one feature
request. The device never reports itself offline when unpowered, it cannot re-establish a
connection without an HA restart, and boost state changed from the Elon phone app is invisible
to HA. Separately, users want a `switch` entity so third-party timer add-ons can drive the
grid boost.

All three defects were reproduced or root-caused against live hardware during planning
(units 7343 and 5570 on the local network).

## Findings from hardware probe

Both units were exercised through a full `ForceReheat` → `CancelGridHeating` cycle. 7343 has
no element and no solar connection; 5570 is a fully connected installation.

| Observation | 7343 (no element) | 5570 (element) |
|---|---|---|
| Baseline | `powerSource 1`, AC 0.000A | `powerSource 1`, AC 0.000A |
| After ForceReheat (≤10s) | `powerSource 2`, AC 0.013A | `powerSource 2`, AC 13.848A @ 233.3V |
| `reheatTime` throughout | `0` | `0` |
| After Cancel (≤8s) | `powerSource 1` | `powerSource 1` |
| `hasOpenAlarms` | `false → true` at T+30s | stayed `false` |

Conclusions:

1. **`reheatTime` is never set.** It is always `0`, including mid-boost. Despite the project
   brief describing the status query as "including the reheat status", this field carries no
   information on this firmware. Do not build on it.
2. **`powerSource` is the boost signal**, and it is independent of load — it read `2` at both
   0.013A and 13.8A. It transitions within ~10s in both directions.
3. **`hasOpenAlarms` genuinely fires.** It went true on 7343 when the element drew no current
   under boost. The integration currently ignores it.
4. **`lastComms` is a device-side tick, not wall-clock** (209137344 → 209137944, advancing
   irregularly). Unusable as a staleness source.
5. **Action endpoints return `{"actionResult","seqNo","failureReason"}`.** The client discards
   this and returns `True` unconditionally.
6. **Measurements response shape is `{"measurements":[{"sensorId":N,"value":V}]}`.** Sensor 9
   (element resistance) does not exist on this firmware — requesting it returns `sensorId: 0`.
7. **mDNS**: instance `ELON-<serial>` on `_http._tcp.local.`, target `ELON-<serial>.local:80`,
   A-record TTL 120s. The instance name carries the serial.
8. AC voltage (sensor 6) reads `0` when the relay is open and 233.3V when closed.
9. `DeviceStatus.waterTemperature` and sensor 1 disagree slightly and refresh on different
   cadences (58.5 vs 58.7 simultaneously).

## Root causes

**Availability (report 1, and the "no offline warning" observation)**
`coordinator.py:69-74` catches the fetch exception and returns the previous payload whenever
`self.data` is already populated. `last_update_success` therefore stays `True` and
`coordinator.data` never returns to `None`. Entity availability is `coordinator.data is not
None` (`water_heater.py:136`, `button.py:65`), so it is permanently `True`. The sensor classes
in `sensor.py` never override `available` at all, so they display their last reading forever.

**Reconnect (reports 2 and 3)**
The reported error `[DNS server returned answer with no data]` is a c-ares NODATA reply,
meaning `.local` is being resolved through unicast DNS rather than mDNS. The integration also
builds its own `ClientSession` (`__init__.py:53-57`) rather than using HA's shared one; that
session is closed only on setup failure, never in `async_unload_entry`, so every reload strands
one. The precise cache holding state across the device power-cycle was not isolated, but
resolving through HA's zeroconf and re-resolving on failure removes the dependency on whatever
it is.

**App→HA state (report 4)**
`_device_operation()` (`water_heater.py:162-167`) requires `powerSource == AC_GRID` **and**
`ac_current > HEATING_CURRENT_THRESHOLD`. Per finding 2 these answer different questions:
`powerSource` reports whether grid boost is engaged, current reports whether the element is
firing. A tank at target under an app-initiated boost sits at `powerSource 2` with low current
and reads as off. HA→app works only because HA latches its own optimistic flag on its own
actions and so never has to ask the device.

## Constraints

- Must remain a HACS-installable custom component; no user-facing git steps.
- `water_heater` entity must survive — it exists so HomeKit Bridge / Matter exports one
  accessory carrying both temperature and control (`water_heater.py:13-32`).
- Minimum HA version is pinned at `2024.11.0` (`hacs.json`).
- No test infrastructure exists in the repo today.

## Decisions taken during planning

| Decision | Choice |
|---|---|
| Address resolution | Zeroconf discovery + optional manual host/IP override |
| Switch entity | Added alongside `water_heater`, not replacing it |
| Tests | Add `pytest-homeassistant-custom-component` |
| Extra entities | Connectivity, alarm (`hasOpenAlarms`), last-seen timestamp |
| Grid-supply sensor (`acNotPresent`) | Rejected — unexercised in probe |
| Sensor polling | Trim to sensors actually backing entities |

## Approach

1. **Test harness.** Add `pytest-homeassistant-custom-component` with a fixture serving the
   recorded payloads from the probe above.
   → verify: `pytest` runs green against the current code with one xfail per known defect.

2. **Availability.** Coordinator raises `UpdateFailed` on status-fetch failure instead of
   returning stale data. Migrate all entities to `CoordinatorEntity` so `available` derives
   from `last_update_success`. This also fixes the discarded `async_add_listener` return value,
   since the base class owns subscribe/unsubscribe.
   → verify: test asserting every entity goes `unavailable` after a failed refresh; xfail from
   step 1 clears.

3. **Boost state predicate.** Extract a single `is_grid_boost_active(data) -> bool` returning
   `data.get("powerSource") == PowerSource.AC_GRID`. Consume it from `water_heater`, the new
   `switch`, and `button` if retained. Current draw stays a separate concept feeding
   `HeatingStateSensor` and `ACPowerSensor`.
   → verify: test asserting boost is active at `powerSource 2` with `ac_current 0.013` (the
   7343 case) and inactive at `powerSource 1`.

4. **Post-action refresh.** After force/cancel, schedule a refresh ~15s out so the real
   transition is picked up well before the next 60s poll and the optimistic override drops.
   → verify: test asserting a refresh is scheduled after `async_turn_on`.

5. **Zeroconf resolution.** Add `zeroconf` to manifest `dependencies` and a discovery block for
   `_http._tcp.local.` matching `elon-*`. Resolve to an IP via HA's zeroconf instance, cache it,
   and force re-resolution on `ClientConnectorError`. Switch to
   `homeassistant.helpers.aiohttp_client.async_get_clientsession` and drop the hand-rolled
   session.
   → verify: discovery flow test using the recorded service record; manual test — pull power,
   confirm entities go unavailable, restore power, confirm recovery with no HA restart.

6. **Config flow.** Auto-populate serial from the discovered instance name; add an optional
   host/IP override field.
   → verify: flow tests for the discovery path and the manual-override path.

7. **Switch platform.** `switch.py` exposing grid boost via the step-3 predicate, sharing the
   optimistic-state handling with `water_heater`.
   → verify: test asserting the switch and water_heater report identical state from the same
   payload; manual test driving it from a timer helper.

8. **New entities.** `binary_sensor.py` with connectivity (`CONNECTIVITY`) and alarm
   (`PROBLEM` from `hasOpenAlarms`); a last-seen `TIMESTAMP` sensor from the coordinator's last
   successful update.
   → verify: test asserting the alarm sensor tracks `hasOpenAlarms` and connectivity tracks
   `last_update_success`.

9. **API hardening.** Pin measurement parsing to `measurements`/`sensorId`/`value`, deleting the
   four-key and three-field-name guessing at `api.py:91-111`. Trim the requested set to
   `[2,3,4,6,7]`. Raise on `actionResult != "Okay"`, surfacing `failureReason`.
   → verify: test asserting a non-`Okay` envelope raises with the reason attached.

10. **Release.** Bump manifest `0.2.0` → `0.3.0`, `just tag`, push tag for HACS.
    → verify: HACS offers the update on a test HA instance.

## Files likely touched

- `custom_components/elon_water_heater/coordinator.py` — raise `UpdateFailed`; expose last-success time
- `custom_components/elon_water_heater/__init__.py` — shared session; add platforms; close-on-unload
- `custom_components/elon_water_heater/api.py` — pin parsing; check `actionResult`; IP-based host
- `custom_components/elon_water_heater/water_heater.py` — state predicate; `CoordinatorEntity`
- `custom_components/elon_water_heater/sensor.py` — `CoordinatorEntity`; last-seen sensor
- `custom_components/elon_water_heater/switch.py` — new
- `custom_components/elon_water_heater/binary_sensor.py` — new
- `custom_components/elon_water_heater/config_flow.py` — discovery step; host override
- `custom_components/elon_water_heater/const.py` — trimmed sensor set; drop unused IDs
- `custom_components/elon_water_heater/manifest.json` — zeroconf, dependencies, version
- `tests/` — new

## Open questions

- [ ] **Poll interval.** Keep 60s and rely on the step-4 post-action refresh, or drop to 30s for
      general responsiveness to app-side changes? Recommendation: keep 60s. The tank is a slow
      system, the post-action refresh covers the case users actually notice, and trimming the
      sensor set already speeds up the slow call.
- [ ] **`button.py`.** Already dead — not listed in `PLATFORMS` (`__init__.py:24`) — and the new
      switch supersedes it. Delete as part of this work, or leave untouched?
- [ ] Does `hasOpenAlarms` self-clear, or does it latch until acknowledged? It was still true on
      7343 after cancel and after current returned to zero. No clear-alarm endpoint is documented.
      Affects whether the alarm sensor needs a companion action.
- [ ] Is `powerSource == 2` also set for device-initiated thermostatic grid heating, not just
      user/app-requested boost? If so the switch will read on during automatic grid heating.
      Arguably correct, but it should be a deliberate choice.

## Risks / unknowns

- The exact cache behind the reboot-only recovery was never isolated. Zeroconf resolution should
  make it moot, but if recovery still fails after step 5, the next suspect is HA's own zeroconf
  record cache and the 120s A-record TTL. Mitigation: the manual host/IP override bypasses
  resolution entirely.
- Adding a `switch` alongside `water_heater` means HomeKit Bridge exports two controls for one
  function. Mitigation: document excluding the switch from the bridge config.
- `pytest-homeassistant-custom-component` pins tightly to an HA version; it may force the
  supported floor above `2024.11.0`. Check before committing to it.
- Migrating to `CoordinatorEntity` touches every entity class. Unique IDs must not change or
  users lose history and automations.

## Out of scope

- Savings calculation and energy logging.
- Weekly temperature history chart.
- The Elon phone app showing a stale temperature with no offline warning — different codebase.
- `acNotPresent` grid-supply sensor — considered and rejected.
- `dashboard.py` behaviour, unchanged by this work.
