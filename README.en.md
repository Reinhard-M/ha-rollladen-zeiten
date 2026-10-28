# Rollladen Zeiten (Shutter Times)

*Deutsche Version: [README.md](README.md)*

![Rollladen Zeiten card](docs/karte.png)

Calculates **day/night** from the sun position and the **drive times for morning and evening**, takes **days off** (weekend, public holidays, vacation, shift work) into account and provides everything as entities for automations and for the **Rollladen Steuerung** integration.
Can be instantiated any number of times (Settings → Devices & services → Add integration → "Rollladen Zeiten"), e.g. one instance each for the south, east and north side. When adding an instance you only choose name, device type, weekend days and calendars; **all settings are entities of the device afterwards** (dashboard friendly, kept across restarts). Location and time zone come from the HA general settings.

> Note: entity names and the card are localized in German and English.

## Setup (when adding the instance)

Only the **name** is **mandatory**. Everything else is **optional** or has a default and can be changed later via "Configure".

| Field | Mandatory? | Notes |
|---|---|---|
| Name | **mandatory** | Device name of the instance (empty = "Rollladen Zeiten") |
| Device type | default *Shutter / blind* | *Shutter / blind* or *Awning*. Changes **only the names** of the three time limits (see Settings), not the calculation. Can be changed later via "Configure"; the entities stay the same |
| Weekend days | default Sat/Sun | These weekdays count as days off. Empty selection = no weekend |
| Calendars for days off | optional | Any number of `calendar` entities (holidays from the HA "Holiday" integration, vacation, shift calendars …). A day with an event counts as a day off |

## Settings (entities of the device)

All values are entities (category "Configuration") and are kept across restarts. With the defaults: drive time = sunrise/sunset, no time limits.

| Setting | Type | Default | Effect |
|---|---|---|---|
| Sunrise / Sunset | `select` | Horizon | Horizon (−0.83°, like `sun.sun`), Civil (−6°), Nautical (−12°), Astronomical (−18°) or **Off**. With *Off* the sun position is disabled and only the time limits apply (offset has no effect) |
| Sunrise / Sunset offset | `number` (−30…30 °) | 0 ° | Added to the sun elevation of the preset. Positive = sun higher → later in the morning, earlier in the evening |
| Earliest time up<br>*(awning: Earliest time automation)* | `time` | 00:00 | Morning time = **later** of (sun position, this time). **00:00 = no override** |
| Earliest time up WE/DO<br>*(awning: Earliest time automation WE/DO)* | `time` | 00:00 | WE = weekend, DO = days off (attribute `comment`). On days off it **replaces** the normal earliest time. **00:00 = the normal limit also applies on days off** |
| Latest time down<br>*(awning: Latest time retract)* | `time` | 23:59 | Evening time = **earlier** of (sun position, this time). **23:59 = no override** |

For the time controls the seconds are always set to `00` (times are minute-exact).

## Logic

**Morning time** = later of *sunrise* (with offset) and *Earliest time up* (on days off *… WE/DO*, if set).
**Evening time** = earlier of *sunset* (with offset) and *Latest time down*.
It is **day** when morning time ≤ now < evening time, otherwise night. The times always show **today** and jump to the new day at midnight; switching happens exactly at the point in time, the sun is not polled cyclically.

**Days off**: A day counts as a "day off" if it is a **weekend day** or has an event in one of the selected **calendars** (all-day or timed, as soon as it touches today). For shift work a calendar containing only the days off is therefore suitable. Calendars are checked at midnight, when the calendar options change and every 30 minutes (not on every change of a setting). If a calendar is not reachable yet (e.g. after startup), it is retried after one minute; until then the last known result applies. The **Day off** sensor names the reason in the attribute `reasons` (`weekend` or the calendar entity).

**Special cases**

* Sun position *Off*: in the morning the day starts at 00:00 or at the earliest time, in the evening it ends at the latest time or at midnight. The time sensor then shows `23:59:00`.
* Polar day (sun does not go below the target elevation): behaves like *Off*, the time limits still apply.
* Polar night (sun never reaches the target elevation): drive times are `unknown`, state is night.
* If the evening time is **before** the morning time (e.g. morning 18:00, evening 05:00), the day spans midnight: day is then from the morning time to 24:00 and from 00:00 to the evening time. The sensors still show the two times of today's calendar day; the attribute `spans_midnight` indicates this case. If both times are equal it is night all the time.

## Outputs (entities)

| Entity | Type | Content |
|---|---|---|
| Day | `binary_sensor` | on (shown "Yes") = day, otherwise off ("No"); attribute `spans_midnight` |
| Day off | `binary_sensor` | on (shown "Yes") = weekend or event in a selected calendar; attributes `reasons`, `calendars_ok` |
| Day/Night | `sensor` (enum) | `day` / `night` (shown: Day / Night); attributes `polar`, `spans_midnight` |
| Morning / evening drive time | `sensor` | only the time of today, e.g. `06:44:48` |
| Morning / evening drive time (timestamp) | `sensor` (timestamp) | same as a full timestamp; **disabled by default**, for `trigger: time` with `at: sensor.…` |

Attributes of the drive-time sensors: `sun_time` (pure sun position without earliest/latest limit), `overridden` (limit applies), `timestamp`, `polar`.

## Working together with "Rollladen Steuerung"

When adding a shutter in the **Rollladen Steuerung** integration, choose the sensor *Day* (or *Day/Night*) of an instance as **day or day/night** and the two drive-time sensors as **drive time morning/evening** (display only in the card). One *Rollladen Zeiten* instance can serve any number of shutters.

## Example: automation with the timestamp sensor

```yaml
triggers:
  - trigger: time
    at: sensor.south_morning_drive_time_timestamp   # entity ID depends on the instance name
actions:
  - action: cover.open_cover
    target:
      entity_id: cover.shutter_south
```

Alternatively without the timestamp sensor, using the time sensor:

```yaml
triggers:
  - trigger: template
    value_template: "{{ now().strftime('%H:%M:%S') == states('sensor.south_morning_drive_time') }}"
```

## Lovelace card "Rollladen Zeiten"

![Rollladen Zeiten card](docs/karte.png)

Table with one row per instance. The card is loaded into the frontend by the integration itself (no entry under resources needed; after an update clear the browser cache, Ctrl+F5). To add it: edit dashboard → add card → **Rollladen Zeiten**; in the editor choose devices (order = row order) and columns. Columns are separated by lines.

**What the screenshot shows:**

| Row / element | Shows |
|---|---|
| Name | Device name, a click opens the device page |
| *Morning / evening time* | Time of today. **Dotted underline** = a time limit applies (Wohnzimmer Süd morning, Schlafzimmer Ost evening); the tooltip names the pure sun position |
| *Day* | Chip **Ja** (green) = day, **Nein** (grey) = night (Schlafzimmer Ost) |
| *Day off* | Chip **Ja** = weekend/calendar event (Wohnzimmer Süd) |
| "–" | Value not available |

With the option **Kind of devices** (card editor: *Shutters / blinds* or *Awnings*; YAML `device_type: shutter | awning`) the labels of the time-limit columns switch. It is best to create one card each for shutters and awnings:

![Card with settings columns for awnings](docs/karte_markisen.png)

Default columns are *Morning time*, *Evening time*, *Day* and *Day off*. Optionally the **settings** can be shown as additional columns (sunrise/sunset, offsets, the three time limits). With `editable: true` they can be changed directly in the card:

![Card with settings columns](docs/karte_einstellungen.png)

(The screenshots are German because the card follows the HA language; in an English HA the headings read *Morning time*, *Sunrise*, *Earliest time up* …)

```yaml
type: custom:rollladen-zeiten-card
title: Shutters
devices:                     # device IDs (easiest to choose via the card editor)
  - 0123456789abcdef0123456789abcdef
columns:                     # order is fixed, only the selection is made here
  - morning
  - evening
  - is_day
  - free_day
  # - morning_preset, morning_offset, earliest_morning, earliest_morning_free
  # - evening_preset, evening_offset, latest_evening
device_type: shutter         # shutter = shutters/blinds, awning = awnings (only the labels of the time limits)
show_seconds: true           # false = HH:MM only
editable: true               # false = show settings columns read-only
show_help: true              # "?" icon linking to this documentation
```

## Installation

### Via HACS (recommended)

1. Open HACS → menu (⋮) → **Custom repositories**.
2. Add `https://github.com/Reinhard-M/ha-rollladen-zeiten` with category **Integration**.
3. Search for "Rollladen Zeiten" in HACS, **Download**, then **restart** Home Assistant.
4. Settings → Devices & services → Add integration → "Rollladen Zeiten".

### Manual

Copy the folder `custom_components/rollladen_zeiten` from this repository to `/config/custom_components/` and **restart** Home Assistant. The integration is declared as a service (`integration_type: service`) and appears under **Settings → Devices & services → Integrations** as one card "Rollladen Zeiten" with all instances; each instance is a device with all its entities.

## Help

The **?** icon (question mark in a circle) in the Lovelace card and the *Documentation (README)* link in the settings dialogs lead to this page. The icon can be hidden in the card editor (`show_help: false`). Please report bugs and wishes as an [issue](https://github.com/Reinhard-M/ha-rollladen-zeiten/issues).

## Disclaimer

* This is a **private hobby project** and an **unofficial community integration**. It is not affiliated with Home Assistant, the Open Home Foundation, Nabu Casa, eQ-3/Homematic IP, Jarolift, Somfy or any other manufacturer mentioned; all names and trademarks belong to their respective owners and are used only to describe compatibility.
* The software is provided **"as is" without warranty of any kind** (see [LICENSE](LICENSE)). Use it at your own risk.
* It is **not a safety device**. It does not replace wind, rain or frost sensors, nor the pinch protection or obstacle detection of the drives. Moving shutters, blinds, awnings and doors can endanger people and property; the automation moves without presence detection.
* Test new settings while you are present and make a backup before updates.

## License

[MIT License](LICENSE) © 2026 Reinhard-M
