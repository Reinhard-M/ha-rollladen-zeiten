import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry, async_fire_time_changed, mock_restore_cache)

DOMAIN = "rollladen_zeiten"


@pytest.fixture(autouse=True)
def _auto(enable_custom_integrations):
    yield


async def _loc(hass):
    await hass.config.async_update(latitude=48.137, longitude=11.575, elevation=520, time_zone="Europe/Berlin")


async def _create(hass, name, **extra):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert r["type"] == "form"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"name": name, **extra})
    assert r["type"] == "create_entry"
    await hass.async_block_till_done()
    return r["result"]


def _ids(hass, entry):
    reg = er.async_get(hass)
    return {e.translation_key: e.entity_id for e in er.async_entries_for_config_entry(reg, entry.entry_id)}


async def _call(hass, domain, service, **data):
    await hass.services.async_call(domain, service, data, blocking=True)
    await hass.async_block_till_done()


async def test_full(hass: HomeAssistant, freezer):
    await _loc(hass)
    freezer.move_to("2026-10-25 11:00:00+00:00")  # 12:00 CET
    e1 = await _create(hass, "Süd")
    ids = _ids(hass, e1)
    print(sorted(ids))
    assert set(ids) == {"is_day","free_day","earliest_morning_free","day_night","morning","evening","morning_timestamp","evening_timestamp",
                        "morning_preset","evening_preset","morning_offset","evening_offset","earliest_morning","latest_evening"}
    S = lambda k: hass.states.get(ids[k])
    # Standard: reine Sonnenzeiten, nur Uhrzeit
    assert S("morning").state == "06:44:48" and S("evening").state == "17:09:57"
    assert S("morning").attributes.get("device_class") is None
    assert S("is_day").state == "on" and S("day_night").state == "day"
    assert S("morning_preset").state == "sunrise" and float(S("morning_offset").state) == 0
    assert S("earliest_morning").state == "00:00:00" and S("latest_evening").state == "23:59:00"
    assert S("morning_timestamp") is None  # standardmäßig deaktiviert

    # Einstellungen über Entitäten
    await _call(hass, "time", "set_value", entity_id=ids["earliest_morning"], time="07:30:00")
    await _call(hass, "time", "set_value", entity_id=ids["latest_evening"], time="17:00:59")
    assert S("latest_evening").state == "17:00:00"
    assert S("morning").state == "07:30:00" and S("evening").state == "17:00:00"
    assert S("morning").attributes["overridden"] is True
    assert S("morning").attributes["sun_time"].startswith("2026-10-25T06:44:48")
    assert S("morning").attributes["timestamp"].startswith("2026-10-25T07:30:00")

    await _call(hass, "select", "select_option", entity_id=ids["morning_preset"], option="civil")
    await _call(hass, "number", "set_value", entity_id=ids["morning_offset"], value=-2)
    await _call(hass, "time", "set_value", entity_id=ids["earliest_morning"], time="00:00:00")
    assert S("morning").state == "05:59:01" and S("morning").attributes["overridden"] is False  # = civil -2°

    # Timer: Abend 17:00 -> Nacht
    freezer.move_to("2026-10-25 16:00:01+00:00")
    async_fire_time_changed(hass); await hass.async_block_till_done()
    assert S("is_day").state == "off" and S("day_night").state == "night"

    # Zweite Instanz unabhängig
    e2 = await _create(hass, "Nord")
    ids2 = _ids(hass, e2)
    assert hass.states.get(ids2["morning"]).state == "06:44:48"
    # Neuladen ohne Fehler
    assert await hass.config_entries.async_reload(e1.entry_id)


async def test_restore(hass: HomeAssistant, freezer):
    await _loc(hass)
    freezer.move_to("2026-10-25 11:00:00+00:00")
    entry = MockConfigEntry(domain=DOMAIN, title="West", data={}, entry_id="abc123")
    entry.add_to_hass(hass)
    reg = er.async_get(hass)
    def eid(domain, key):
        return reg.async_get_or_create(domain, DOMAIN, f"abc123_{key}", config_entry=entry, translation_key=key, suggested_object_id=f"west_{key}").entity_id
    mock_restore_cache(hass, [
        State(eid("select","morning_preset"), "nautical"),
        State(eid("number","evening_offset"), "2.5"),
        State(eid("time","earliest_morning"), "08:15:00"),
        State(eid("time","latest_evening"), "21:00:59"),
    ])
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("select.west_morning_preset").state == "nautical"
    assert float(hass.states.get("number.west_evening_offset").state) == 2.5
    assert hass.states.get("time.west_earliest_morning").state == "08:15:00"
    assert hass.states.get("time.west_latest_evening").state == "21:00:00"  # Sekunden werden auf 00 gesetzt
    assert hass.states.get(_ids(hass, entry)["morning"]).state == "08:15:00"  # Grenze greift nach Restore (nautical wäre 05:35)


async def test_free_days(hass: HomeAssistant, freezer):
    await _loc(hass)
    # Holiday-Integration (Deutschland) -> calendar.*
    hol = MockConfigEntry(domain="holiday", data={"country": "DE"}, title="DE")
    hol.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hol.entry_id)
    await hass.async_block_till_done()
    cals = hass.states.async_entity_ids("calendar")
    print("calendars:", cals)
    assert cals

    freezer.move_to("2026-12-24 09:00:00+00:00")  # Do 24.12., kein Feiertag, 10:00 lokal
    e = await _create(hass, "Süd", weekend_days=["sat", "sun"], free_calendars=cals)
    ids = _ids(hass, e)
    S = lambda k: hass.states.get(ids[k])
    await _call(hass, "time", "set_value", entity_id=ids["earliest_morning"], time="08:30:00")
    await _call(hass, "time", "set_value", entity_id=ids["earliest_morning_free"], time="09:00:00")
    assert S("free_day").state == "off", S("free_day").attributes
    assert S("morning").state == "08:30:00"

    # Mitternacht -> 25.12. (Freitag, Feiertag): Kalender greift
    freezer.move_to("2026-12-24 23:00:05+00:00")
    async_fire_time_changed(hass); await hass.async_block_till_done()
    print(S("free_day").attributes)
    assert S("free_day").state == "on" and cals[0] in S("free_day").attributes["reasons"]
    assert S("morning").state == "09:00:00"

    # 26.12. = Samstag -> Wochenende (und Stephanstag)
    freezer.move_to("2026-12-25 23:00:05+00:00")
    async_fire_time_changed(hass); await hass.async_block_till_done()
    assert S("free_day").state == "on" and "weekend" in S("free_day").attributes["reasons"]
    assert S("morning").state == "09:00:00"

    # 28.12. Montag, kein Feiertag -> normal
    freezer.move_to("2026-12-27 23:00:05+00:00")
    async_fire_time_changed(hass); await hass.async_block_till_done()
    assert S("free_day").state == "off" and S("morning").state == "08:30:00"

    # Options-Flow: keine Wochenendtage/Kalender mehr; 25.12. wäre nun normal
    r = await hass.config_entries.options.async_init(e.entry_id)
    assert r["type"] == "form"
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"weekend_days": []})
    assert r["type"] == "create_entry"
    await hass.async_block_till_done()
    ids = _ids(hass, e)
    assert hass.states.get(ids["free_day"]).state == "off"
    assert e.options.get("free_calendars") in (None, [])

    # Free-Zeit neutral (00:00:00) -> normale Grenze auch an freien Tagen
    await _call(hass, "time", "set_value", entity_id=ids["earliest_morning_free"], time="00:00:00")


async def test_sun_off(hass: HomeAssistant, freezer):
    await _loc(hass)
    freezer.move_to("2026-10-26 11:00:00+00:00")  # Mo 12:00 CET
    e = await _create(hass, "Süd", weekend_days=["sat", "sun"])
    ids = _ids(hass, e)
    S = lambda k: hass.states.get(ids[k])
    assert "off" in S("morning_preset").attributes["options"]
    assert S("earliest_morning_free").attributes["comment"] in (
        "WE = weekend, DO = days off", "WE = Wochenende, FT = Freie Tage")

    # Morgens "Aus" ohne Zeitgrenze -> ab 00:00 Tag; abends weiter nach Sonne
    await _call(hass, "select", "select_option", entity_id=ids["morning_preset"], option="off")
    assert S("morning").state == "00:00:00"
    assert S("morning").attributes["sun_time"] is None and S("morning").attributes["overridden"] is False
    assert S("evening").state == "17:08:00" or S("evening").state.startswith("17:")  # Sonne bleibt aktiv

    # nur Zeit: morgens 07:00 / abends 18:00 (Sonne abends ebenfalls aus)
    await _call(hass, "time", "set_value", entity_id=ids["earliest_morning"], time="07:00:00")
    await _call(hass, "select", "select_option", entity_id=ids["evening_preset"], option="off")
    await _call(hass, "time", "set_value", entity_id=ids["latest_evening"], time="18:00:00")
    assert S("morning").state == "07:00:00" and S("evening").state == "18:00:00"
    assert S("morning").attributes["overridden"] is True and S("morning").attributes["sun_time"] is None
    assert S("is_day").state == "on"  # 12:00 liegt zwischen 07:00 und 18:00

    # Abends "Aus" ohne späteste Zeit -> Tag bis Mitternacht, Anzeige 23:59:59
    await _call(hass, "time", "set_value", entity_id=ids["latest_evening"], time="23:59:00")
    assert S("evening").state == "23:59:00" and S("is_day").state == "on"
    # alter Neutralwert 23:59:59 (z. B. aus wiederhergestelltem Zustand) bleibt "keine Grenze"
    await _call(hass, "time", "set_value", entity_id=ids["latest_evening"], time="23:59:59")
    assert S("evening").state == "23:59:00" and S("evening").attributes["overridden"] is False

    # Wochenende (Sa 31.10.): WE/FT-Zeit 09:00 gilt auch im Modus "Aus"
    await _call(hass, "time", "set_value", entity_id=ids["earliest_morning_free"], time="09:00:00")
    freezer.move_to("2026-10-31 07:30:00+00:00")  # Sa 08:30 CET
    async_fire_time_changed(hass); await hass.async_block_till_done()
    assert S("free_day").state == "on" and S("morning").state == "09:00:00"
    assert S("is_day").state == "off"  # 08:30 < 09:00
    freezer.move_to("2026-10-31 08:00:01+00:00")  # 09:00:01 CET
    async_fire_time_changed(hass); await hass.async_block_till_done()
    assert S("is_day").state == "on"


def test_manifest_type():
    import json, pathlib
    m = json.loads(pathlib.Path("custom_components/rollladen_zeiten/manifest.json").read_text())
    assert m["integration_type"] == "service"


async def test_wrap_midnight(hass: HomeAssistant, freezer):
    await _loc(hass)
    freezer.move_to("2026-10-26 17:30:00+00:00")  # Mo 18:30 CET
    e = await _create(hass, "Nacht", weekend_days=[])
    ids = _ids(hass, e)
    S = lambda k: hass.states.get(ids[k])
    await _call(hass, "select", "select_option", entity_id=ids["morning_preset"], option="off")
    await _call(hass, "select", "select_option", entity_id=ids["evening_preset"], option="off")
    await _call(hass, "time", "set_value", entity_id=ids["earliest_morning"], time="18:00:00")
    await _call(hass, "time", "set_value", entity_id=ids["latest_evening"], time="05:00:00")
    assert S("morning").state == "18:00:00" and S("evening").state == "05:00:00"
    assert S("is_day").state == "on" and S("is_day").attributes["spans_midnight"] is True
    assert S("day_night").state == "day" and S("day_night").attributes["spans_midnight"] is True

    for ts, expected in [
        ("2026-10-27 02:00:00+00:00", "on"),    # 03:00 CET Di: noch Tag
        ("2026-10-27 03:59:59+00:00", "on"),    # 04:59:59
        ("2026-10-27 04:00:01+00:00", "off"),   # 05:00:01
        ("2026-10-27 11:00:00+00:00", "off"),   # 12:00
        ("2026-10-27 16:59:59+00:00", "off"),   # 17:59:59
        ("2026-10-27 17:00:01+00:00", "on"),    # 18:00:01
    ]:
        freezer.move_to(ts)
        async_fire_time_changed(hass); await hass.async_block_till_done()
        assert S("is_day").state == expected, ts

    # Normalfall unverändert: Abend nach Morgen -> spans_midnight False
    await _call(hass, "time", "set_value", entity_id=ids["earliest_morning"], time="07:00:00")
    await _call(hass, "time", "set_value", entity_id=ids["latest_evening"], time="21:00:00")
    assert S("is_day").attributes["spans_midnight"] is False and S("is_day").state == "on"


async def test_free_day_state_translation(hass: HomeAssistant):
    from homeassistant.helpers.translation import async_get_translations
    await _loc(hass)
    await _create(hass, "Süd")
    for lang, on, off in (("de", "Ja", "Nein"), ("en", "Yes", "No")):
        tr = await async_get_translations(hass, lang, "entity", [DOMAIN])
        for key in ("free_day", "is_day"):
            base = f"component.{DOMAIN}.entity.binary_sensor.{key}.state"
            assert tr[f"{base}.on"] == on and tr[f"{base}.off"] == off, (lang, key)


async def test_card_registration(hass: HomeAssistant):
    from unittest.mock import AsyncMock, MagicMock, patch
    from custom_components import rollladen_zeiten as rz

    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.config.components.add("frontend")
    with patch.object(rz, "add_extra_js_url") as add_js:
        await rz._async_register_card(hass)
    cfg = hass.http.async_register_static_paths.call_args[0][0][0]
    assert cfg.url_path == "/rollladen_zeiten/rollladen-zeiten-card.js"
    assert cfg.path.endswith("frontend/rollladen-zeiten-card.js")
    import os
    assert os.path.isfile(cfg.path)
    url = add_js.call_args[0][1]
    assert url.startswith("/rollladen_zeiten/rollladen-zeiten-card.js?v=")

    # ohne Frontend: still überspringen
    hass.config.components.remove("frontend")
    hass.http.async_register_static_paths.reset_mock()
    await rz._async_register_card(hass)
    hass.http.async_register_static_paths.assert_not_called()


async def test_card_registration(hass: HomeAssistant):
    """Die Lovelace-Karte wird als statische Datei ausgeliefert und im Frontend geladen."""
    import pathlib
    from unittest.mock import AsyncMock, MagicMock, patch

    from custom_components.rollladen_zeiten import CARD_FILE, CARD_URL, async_setup

    assert pathlib.Path(CARD_FILE).is_file()
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.config.components.add("frontend")
    with patch("custom_components.rollladen_zeiten.add_extra_js_url") as add_js:
        assert await async_setup(hass, {})
    hass.http.async_register_static_paths.assert_awaited_once()
    cfg = hass.http.async_register_static_paths.await_args.args[0][0]
    assert cfg.url_path == CARD_URL == "/rollladen_zeiten/rollladen-zeiten-card.js"
    assert pathlib.Path(cfg.path) == pathlib.Path(CARD_FILE)
    add_js.assert_called_once()
    assert add_js.call_args.args[1].startswith(CARD_URL + "?v=")

    # ohne HTTP/Frontend: kein Fehler, nichts registriert
    hass.http = None
    with patch("custom_components.rollladen_zeiten.add_extra_js_url") as add_js:
        assert await async_setup(hass, {})
    add_js.assert_not_called()


async def test_settings_do_not_requery_calendars(hass: HomeAssistant, freezer):
    from unittest.mock import patch
    from custom_components.rollladen_zeiten.coordinator import RollladenZeitenCoordinator as C
    await _loc(hass)
    hol = MockConfigEntry(domain="holiday", data={"country": "DE"}, title="DE")
    hol.add_to_hass(hass)
    assert await hass.config_entries.async_setup(hol.entry_id)
    await hass.async_block_till_done()
    cals = hass.states.async_entity_ids("calendar")
    freezer.move_to("2026-12-24 09:00:00+00:00")
    calls = []
    orig = C._async_calendar_has_event

    async def counting(self, *a, **k):
        calls.append(a[0])
        return await orig(self, *a, **k)

    with patch.object(C, "_async_calendar_has_event", counting):
        e = await _create(hass, "Süd", free_calendars=cals)
        ids = _ids(hass, e)
        n = len(calls)
        assert n >= 1
        await _call(hass, "time", "set_value", entity_id=ids["earliest_morning"], time="08:30:00")
        await _call(hass, "number", "set_value", entity_id=ids["morning_offset"], value=2)
        assert len(calls) == n  # Einstellungen: Zeiten neu rechnen, Kalender nicht
        assert hass.states.get(ids["morning"]).state >= "08:30:00"
        freezer.tick(1801)
        async_fire_time_changed(hass); await hass.async_block_till_done()
        assert len(calls) > n  # regelmäßige Prüfung fragt weiterhin ab


async def test_awning_names_and_switching(hass: HomeAssistant, freezer):
    await _loc(hass)
    e = await _create(hass, "Markise Süd", device_type="awning")
    reg = er.async_get(hass)
    ents = {x.unique_id.split("_", 1)[1]: x for x in er.async_entries_for_config_entry(reg, e.entry_id)}
    assert ents["earliest_morning"].translation_key == "earliest_morning_awning"
    assert ents["latest_evening"].translation_key == "latest_evening_awning"
    assert ents["morning_offset"].translation_key == "morning_offset"
    st = hass.states.get(ents["earliest_morning"].entity_id)
    assert st.attributes["friendly_name"].endswith("Earliest time automation"), st.attributes
    assert hass.states.get(ents["latest_evening"].entity_id).attributes["friendly_name"].endswith("Latest time retract")
    # Typ im Options-Flow zurueck auf Rollo: Bezeichnungen wechseln, Entitaeten bleiben (gleiche unique_id)
    r = await hass.config_entries.options.async_init(e.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"device_type": "shutter", "weekend_days": ["sat", "sun"]})
    assert r["type"] == "create_entry"
    await hass.async_block_till_done()
    ents2 = {x.unique_id.split("_", 1)[1]: x for x in er.async_entries_for_config_entry(reg, e.entry_id)}
    assert ents2["earliest_morning"].entity_id == ents["earliest_morning"].entity_id
    assert ents2["earliest_morning"].translation_key == "earliest_morning"
    assert hass.states.get(ents2["earliest_morning"].entity_id).attributes["friendly_name"].endswith("Earliest time up")
