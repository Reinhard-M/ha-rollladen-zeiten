# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Reinhard-M. Unofficial community integration, not affiliated with Home Assistant.
"""Pure calculation logic of Rollladen Zeiten (no Home Assistant dependencies)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

from astral import Observer, SunDirection
from astral.sun import SUN_APPARENT_RADIUS, elevation as sun_elevation, noon, time_at_elevation

# Sun elevation (degrees) at which the respective point in time is defined.
# "sunrise" corresponds to sunrise/sunset of sun.sun in Home Assistant.
PRESET_ELEVATION: dict[str, float] = {
    "sunrise": -SUN_APPARENT_RADIUS,  # approx. -0.833 deg (upper edge of the sun at the horizon)
    "civil": -6.0,
    "nautical": -12.0,
    "astronomical": -18.0,
}

PRESET_OFF = "off"  # sun position disabled
POLAR_DAY = "polar_day"
POLAR_NIGHT = "polar_night"


@dataclass(frozen=True)
class DayTimes:
    """Result of the calculation for one calendar day (local time)."""

    date: date
    sun_morning: datetime | None  # pure sun position, without the earliest time
    sun_evening: datetime | None  # pure sun position, without the latest time
    morning: datetime | None  # final (with override)
    evening: datetime | None  # final (with override)
    polar: str | None  # None | "polar_day" | "polar_night"
    morning_off: bool = False  # sun position disabled in the morning (time limit only)
    evening_off: bool = False  # sun position disabled in the evening (time limit only)

    @property
    def spans_midnight(self) -> bool:
        """True if the evening time is before the morning time (the day spans midnight)."""
        return (
            self.morning is not None
            and self.evening is not None
            and self.evening < self.morning
        )

    def is_day(self, now: datetime) -> bool:
        """Day if morning <= now < evening; across midnight if evening < morning.

        Example morning 18:00, evening 05:00: day from 18:00 to 24:00 and from 00:00 to 05:00.
        """
        if self.morning is None or self.evening is None:
            return False
        if self.spans_midnight:
            return now >= self.morning or now < self.evening
        return self.morning <= now < self.evening

    @property
    def morning_overridden(self) -> bool:
        return self.morning is not None and self.morning != self.sun_morning

    @property
    def evening_overridden(self) -> bool:
        return self.evening is not None and self.evening != self.sun_evening


def target_elevation(preset: str, offset_deg: float) -> float:
    """Target sun elevation: preset plus offset (positive = sun higher = later in the morning)."""
    return PRESET_ELEVATION[preset] + offset_deg


def _event_on_date(
    observer: Observer,
    elevation: float,
    day: date,
    direction: SunDirection,
    tz: tzinfo,
) -> datetime:
    """Point in time of the event on the local calendar day `day`.

    astral calculates in UTC days; with a large longitude the result can fall on a
    neighbouring day. In that case the calculation is repeated with a shifted date.
    Raises ValueError if the sun does not cross this elevation on that day.
    """
    result = None
    for shift in (0, -1, 1):
        candidate = time_at_elevation(
            observer, elevation, day + timedelta(days=shift), direction, tz
        )
        result = result or candidate
        if candidate.date() == day:
            return candidate
    return result  # type: ignore[return-value]


def _sun_event(
    observer: Observer,
    elevation: float,
    day: date,
    direction: SunDirection,
    tz: tzinfo,
) -> tuple[datetime | None, str | None]:
    """Returns (point in time, polar). On polar day/night the point in time is None."""
    try:
        event = _event_on_date(observer, elevation, day, direction, tz)
        return event.replace(microsecond=0), None  # second precision is enough
    except ValueError:
        local_noon = noon(observer, day, tz)
        # elevation at noon = highest position of the sun that day
        if sun_elevation(observer, local_noon) > elevation:
            return None, POLAR_DAY  # the sun stays above the target elevation
        return None, POLAR_NIGHT  # the sun never reaches the target elevation


def compute_day(
    observer: Observer,
    tz: tzinfo,
    day: date,
    *,
    morning_preset: str,
    morning_offset: float,
    evening_preset: str,
    evening_offset: float,
    earliest_morning: time | None,
    latest_evening: time | None,
) -> DayTimes:
    """Calculates the drive times for `day`."""
    morning_off = morning_preset == PRESET_OFF
    evening_off = evening_preset == PRESET_OFF

    if morning_off:
        sun_morning, polar_m = None, None
    else:
        sun_morning, polar_m = _sun_event(
            observer,
            target_elevation(morning_preset, morning_offset),
            day,
            SunDirection.RISING,
            tz,
        )
    if evening_off:
        sun_evening, polar_e = None, None
    else:
        sun_evening, polar_e = _sun_event(
            observer,
            target_elevation(evening_preset, evening_offset),
            day,
            SunDirection.SETTING,
            tz,
        )

    day_start = datetime.combine(day, time.min, tzinfo=tz)
    # Exclusive end of the day (= 00:00 of the next day) so that there is no short
    # "night" at midnight during polar day.
    day_end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)

    polar: str | None = None
    if POLAR_NIGHT in (polar_m, polar_e):
        polar = POLAR_NIGHT
    elif POLAR_DAY in (polar_m, polar_e):
        polar = POLAR_DAY

    if polar == POLAR_NIGHT:
        return DayTimes(day, None, None, None, None, polar, morning_off, evening_off)

    # Polar day or sun position "off": the sun position does not restrict the day,
    # only the time limits apply.
    if morning_off or polar_m == POLAR_DAY:
        sun_morning = day_start
    if evening_off or polar_e == POLAR_DAY:
        sun_evening = day_end

    morning = sun_morning
    evening = sun_evening
    if earliest_morning is not None:
        limit = datetime.combine(day, earliest_morning, tzinfo=tz)
        morning = max(morning, limit)  # type: ignore[type-var]
    if latest_evening is not None:
        limit = datetime.combine(day, latest_evening, tzinfo=tz)
        evening = min(evening, limit)  # type: ignore[type-var]

    return DayTimes(
        day, sun_morning, sun_evening, morning, evening, polar, morning_off, evening_off
    )
