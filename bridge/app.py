"""
anycubic-bridge
----------------
Optionale Brücke zwischen der Anycubic Cloud (via anycubic-cloud-api, GPL-3.0,
https://github.com/Nino6689/anycubic-cloud-api) und dem Lagersystem-Storage-Backend
(Spoolman-Erweiterung). Läuft als eigener, separater Swarm-Service, damit die
GPL-3.0-Lizenz der Anycubic-Lib nicht auf den Rest des Lagersystems durchschlägt.

Opt-in: Ohne "enabled" in den Settings passiert nichts (kein Polling, keine
Anycubic-Kommunikation). Kein Login-Automatismus möglich (Anycubic-Login ist
Captcha-/2FA-geschützt) -- der Nutzer meldet sich alle ~90 Tage einmal manuell
an und schickt den resultierenden Token per Bookmarklet an POST /api/auth/token.

Keine Authentifizierung auf den eigenen Endpoints (Projekt-Policy, siehe
Lagersystem/Mesh-Hub: "beide Systeme arbeiten ohne Authentifizierung").
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import time
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
import aiosqlite
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from anycubic_cloud_api import AnycubicAuthMode, AnycubicMQTTAPI

from anycubic_cloud_api.data_models.printer import AnycubicPrinter as _ACP478

_orig_process_mqtt_update_478q = _ACP478.process_mqtt_update

from anycubic_cloud_api.api.functions import AnycubicAPIFunctions as _ACAPI478r
_orig_send_order_478r = _ACAPI478r._send_anycubic_order

async def _patched_send_order_478r(self, order_request, raw_data=False):
    try:
        logging.getLogger("uvicorn.error").warning(
            "DEBUG478r SEND_ORDER order_id=%r printer_id=%r",
            getattr(order_request, 'order_id', None), getattr(order_request, 'printer_id', None),
        )
    except Exception as _er:
        logging.getLogger("uvicorn.error").warning("DEBUG478r SEND_ORDER_LOGFAIL %r: %s", type(_er), _er)
    try:
        logging.getLogger("uvicorn.error").warning(
            "DEBUG478s ORDER_OBJ type=%r dir=%r slots=%r dict_attempt=%r repr=%.500r",
            type(order_request),
            [a for a in dir(order_request) if not a.startswith("__")],
            getattr(order_request, "__slots__", None),
            (order_request.model_dump() if hasattr(order_request, "model_dump") else (order_request.__dict__ if hasattr(order_request, "__dict__") else None)),
            order_request,
        )
    except Exception as _es:
        logging.getLogger("uvicorn.error").warning("DEBUG478s ORDER_OBJ_LOGFAIL %r: %s", type(_es), _es)
    try:
        _result478r = await _orig_send_order_478r(self, order_request, raw_data)
        logging.getLogger("uvicorn.error").warning("DEBUG478r SEND_ORDER_RESULT result=%r", _result478r)
        return _result478r
    except Exception as _er2:
        logging.getLogger("uvicorn.error").warning("DEBUG478r SEND_ORDER_EXC %r: %s", type(_er2), _er2)
        raise

_ACAPI478r._send_anycubic_order = _patched_send_order_478r


def _patched_process_mqtt_update_478q(self, topic, payload):
    try:
        logging.getLogger("uvicorn.error").warning(
            "DEBUG478q MQTT_IN topic=%r type=%r action=%r state=%r data_keys=%r",
            topic, payload.get('type'), payload.get('action'), payload.get('state'),
            list(payload.get('data', {}).keys()) if isinstance(payload.get('data'), dict) else payload.get('data'),
        )
    except Exception as _eq:
        logging.getLogger("uvicorn.error").warning("DEBUG478q MQTT_IN_LOGFAIL %r: %s", type(_eq), _eq)
    return _orig_process_mqtt_update_478q(self, topic, payload)

_ACP478.process_mqtt_update = _patched_process_mqtt_update_478q


_orig_pmu478 = _ACP478.process_mqtt_update
def _patched_pmu478(self, topic, payload):
    try:
        logging.getLogger("uvicorn.error").warning(
            "DEBUG478h RAW_MQTT topic=%r type=%r action=%r state=%r full=%r",
            topic, payload.get('type'), payload.get('action'), payload.get('state'), payload,
        )
    except Exception:
        pass
    try:
        if payload.get('type') == 'extfilbox':
            _d501 = payload.get('data') or {}
            if True:
                _loaded501 = 1 if _d501.get('loaded') else 0
                _color501 = _d501.get('color') or [0, 0, 0]
                _slot501 = {
                    "brand_name": "anycubic",
                    "color": _color501,
                    "color_group": [list(_color501) + [255]],
                    "consumables_percent": 100,
                    "edit_status": 0,
                    "icon_type": 0,
                    "index": 0,
                    "material_name": "",
                    "sku": "",
                    "status": 5 if _loaded501 else 1,
                    "type": _d501.get('type') or '',
                    "weight": 1000,
                }
                _box501 = {
                    "id": 99001,
                    "model_id": 99001,
                    "loaded_slot": 0 if _loaded501 else -1,
                    "auto_feed": 0,
                    "humidity": 0,
                    "status": 0,
                    "target_temp": 0,
                    "drying_status": {"duration": 0, "remain_time": 0, "status": 0},
                    "slots": [_slot501],
                }
                logging.getLogger("uvicorn.error").warning("DEBUG501 EXTFILBOX_MAP box=%r", _box501)
                self._set_multi_color_box([_box501])
    except Exception as _e501:
        logging.getLogger("uvicorn.error").warning("DEBUG501 EXTFILBOX_MAP_FAIL %r: %s", type(_e501), _e501)
    return _orig_pmu478(self, topic, payload)
_ACP478.process_mqtt_update = _patched_pmu478

_orig_mcb_update478 = _ACP478._process_mqtt_update_multicolorbox
def _patched_mcb_update478(self, action, state, payload):
    try:
        logging.getLogger("uvicorn.error").warning(
            "DEBUG478g MCB_UPDATE action=%r state=%r payload=%r",
            action, state, payload,
        )
    except Exception:
        pass
    return _orig_mcb_update478(self, action, state, payload)
_ACP478._process_mqtt_update_multicolorbox = _patched_mcb_update478

_orig_set_mcb478 = _ACP478._set_multi_color_box
def _patched_set_mcb478(self, data):
    try:
        logging.getLogger("uvicorn.error").warning("DEBUG478g SET_MCB data=%r", data)
    except Exception:
        pass
    return _orig_set_mcb478(self, data)
_ACP478._set_multi_color_box = _patched_set_mcb478


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("anycubic-bridge")

DB_PATH = "/data/anycubic_bridge.db"
STORAGE_BASE_URL = "http://storage:8080"
POLL_INTERVAL_SECONDS = 90  # 507fix: 20s->90s, verhindert MQTT-Reconnect-Spam/rc=5-Sperre bei Anycubic
FILAMENT_DIAMETER_MM = 1.75
FILAMENT_CROSS_SECTION_MM2 = math.pi * (FILAMENT_DIAMETER_MM / 2) ** 2

# g/cm^3, approximiert nach Materialtyp -- Spoolman liefert keine Dichte über
# den bestehenden /spools-Lesepfad des Storage-Backends. Genau wie bei der
# OrcaSlicer-Schaetzung (Stufe 3 der Mesh-Hub-Integration) ist das eine
# Annäherung, kein Messwert. Siehe Obsidian-Doku, Abschnitt Anycubic-Bridge.
DEFAULT_DENSITY_BY_MATERIAL = {
    "PLA": 1.24,
    "PLA+": 1.24,
    "PETG": 1.27,
    "ABS": 1.04,
    "ASA": 1.05,
    "TPU": 1.21,
    "PA": 1.14,
    "NYLON": 1.14,
    "PC": 1.20,
    "PVA": 1.23,
    "HIPS": 1.04,
}
FALLBACK_DENSITY = 1.24


def density_for_material(material: str | None) -> float:
    if not material:
        return FALLBACK_DENSITY
    key = material.strip().upper()
    for known, density in DEFAULT_DENSITY_BY_MATERIAL.items():
        if key.startswith(known):
            return density
    return FALLBACK_DENSITY


def grams_from_mm(delta_mm: float, material: str | None) -> float:
    if delta_mm <= 0:
        return 0.0
    volume_mm3 = delta_mm * FILAMENT_CROSS_SECTION_MM2
    volume_cm3 = volume_mm3 / 1000.0
    return round(volume_cm3 * density_for_material(material), 2)


def decode_jwt_exp(token: str) -> int | None:
    """Liest nur das exp-Claim aus einem JWT, ohne Signatur zu prüfen.

    Wir vertrauen dem Token inhaltlich (er kommt direkt vom Nutzer-Login bei
    Anycubic), wollen hier nur wissen, wann er abläuft.
    """
    try:
        payload_part = token.split(".")[1]
        padding = "=" * (-len(payload_part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_part + padding))
        exp = payload.get("exp")
        return int(exp) if exp is not None else None
    except Exception:
        return None


# ---------------------------------------------------------------- database --

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS mappings (
    printer_id TEXT NOT NULL,
    box_id INTEGER NOT NULL,
    slot_index INTEGER NOT NULL,
    spool_id INTEGER NOT NULL,
    PRIMARY KEY (printer_id, box_id, slot_index)
);
CREATE TABLE IF NOT EXISTS job_state (
    printer_id TEXT PRIMARY KEY,
    task_id TEXT,
    baseline_usage_mm REAL NOT NULL DEFAULT 0,
    last_booked_at REAL
);
"""


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()


async def get_setting(db: aiosqlite.Connection, key: str, default: str | None = None) -> str | None:
    cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cur.fetchone()
    return row["value"] if row else default


async def set_setting(db: aiosqlite.Connection, key: str, value: str) -> None:
    await db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    await db.commit()


# ------------------------------------------------------------------ models --

class TokenPayload(BaseModel):
    token: str
    auth_mode: str = "web"  # "web" oder "slicer"


class SettingsPayload(BaseModel):
    enabled: bool


class MappingPayload(BaseModel):
    printer_id: str
    box_id: int
    slot_index: int
    spool_id: int


# -------------------------------------------------------------------- poll --

_CUR_PRINT = {"name": None}


async def book_usage(session: aiohttp.ClientSession, spool_id: int, grams: float) -> bool:
    try:
        async with session.post(
            f"{STORAGE_BASE_URL}/spools/{spool_id}/use",
            json={"grams": grams, "source": "bridge", "print_name": _CUR_PRINT.get("name")},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status >= 400:
                text = await resp.text()
                log.warning("Buchung fehlgeschlagen (spool %s, %sg): %s %s", spool_id, grams, resp.status, text)
                return False
            return True
    except Exception as exc:
        log.warning("Buchung fehlgeschlagen (spool %s, %sg): %s", spool_id, grams, exc)
        return False


async def _resolve_spool_via_storage_link(session: aiohttp.ClientSession, printer_id: str, box_id, slot_index: int) -> int | None:
    """Fallback-Zuordnung (#522): wenn in der bridge-eigenen 'mappings'-Tabelle
    kein Eintrag existiert, versuchen wir die Spule ueber den bereits in der
    Lagerplaetze-Oberflaeche (Drucker-Seite, #516-521) gepflegten Link
    storage_units.bridge_printer_id/bridge_box_id + deren Slot-Belegung
    (slots.spool_id) aufzuloesen. So muss der Nutzer die Zuordnung nicht an
    zwei Stellen (Settings-UI-Mapping UND Lagerplatz-Verknuepfung) pflegen.
    """
    try:
        async with session.get(f"{STORAGE_BASE_URL}/units", timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status >= 400:
                return None
            data = await resp.json()
    except Exception as exc:
        log.debug("Storage-Link-Fallback: Abruf der Units fehlgeschlagen: %s", exc)
        return None

    units = data.get("units", data) if isinstance(data, dict) else data
    if not isinstance(units, list):
        return None

    for unit in units:
        if not isinstance(unit, dict):
            continue
        if str(unit.get("bridge_printer_id") or "") != str(printer_id):
            continue
        unit_box_id = unit.get("bridge_box_id")
        if unit_box_id is None or str(unit_box_id) != str(box_id):
            continue
        slots = unit.get("slots") or []
        slots_sorted = sorted(slots, key=lambda sl: (sl.get("level", 0), sl.get("position", 0)))
        if slot_index < 0 or slot_index >= len(slots_sorted):
            continue
        spool_id = slots_sorted[slot_index].get("spool_id")
        if spool_id is not None:
            return int(spool_id)
    return None


async def _resolve_external_spool(session: aiohttp.ClientSession, printer_id: str) -> int | None:
    """Aussenspule (z.B. Kobra X Druckerplatz): Drucker-Lagerplatz mit genau einer Spule."""
    try:
        async with session.get(f"{STORAGE_BASE_URL}/units", timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status >= 400:
                return None
            data = await resp.json()
    except Exception as exc:
        log.debug("Externe Spule: Abruf der Units fehlgeschlagen: %s", exc)
        return None
    units = data.get("units", data) if isinstance(data, dict) else data
    if not isinstance(units, list):
        return None
    for unit in units:
        if not isinstance(unit, dict) or unit.get("type") != "printer":
            continue
        if str(unit.get("bridge_printer_id") or "") != str(printer_id):
            continue
        filled = [sl.get("spool_id") for sl in (unit.get("slots") or []) if sl.get("spool_id") is not None]
        if len(filled) == 1:
            return int(filled[0])
    return None


async def _ordered_slots(session, printer_id):
    """Slicer-Reihenfolge (nach Sync): belegte Druckerplaetze, danach ACE-Slots.
    Liefert [(box_id, position, spool_id)] oder None."""
    try:
        async with session.get(f"{STORAGE_BASE_URL}/units", timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status >= 400:
                return None
            data = await resp.json()
    except Exception as exc:
        log.debug("ordered_slots: Units-Abruf fehlgeschlagen: %s", exc)
        return None
    units = data.get("units", data) if isinstance(data, dict) else data
    if not isinstance(units, list):
        return None
    mine = [u for u in units if isinstance(u, dict) and str(u.get("bridge_printer_id") or "") == str(printer_id)]
    mine.sort(key=lambda u: 0 if u.get("type") == "printer" else 1)
    out = []
    for u in mine:
        bid = u.get("bridge_box_id")
        if bid is None:
            return None
        for sl in sorted(u.get("slots") or [], key=lambda x: x.get("position", 0)):
            if sl.get("spool_id") is not None:
                out.append((int(bid), int(sl.get("position", 0)), int(sl["spool_id"])))
    return out or None


async def _resolve_auth_mode(session, cookie_jar, token, preferred_mode, db=None):
    """Probiert zuerst den bevorzugten Modus, dann den jeweils anderen.

    Hintergrund (#476/#477): ein Anycubic-Token "weiss" nicht, aus welcher App
    er stammt - nur der Login-Versuch beim Server je Modus entscheidet, ob
    MQTT (SLICER) oder nur REST (WEB) moeglich ist. Vorbild: hass-anycubic
    detect_auth_mode()/_async_authenticate_detecting_mode(). Bei Erfolg wird
    der tatsaechlich funktionierende Modus in der DB aktualisiert (falls db
    uebergeben wurde).
    """
    candidates = [preferred_mode] + [
        m for m in (AnycubicAuthMode.SLICER, AnycubicAuthMode.WEB) if m is not preferred_mode
    ]

    for mode in candidates:
        api = AnycubicMQTTAPI(session=session, cookie_jar=cookie_jar, debug_logger=log)
        api.set_authentication(auth_token=token, auth_mode=mode, auto_pick_token=False)
        try:
            ok = await api.check_api_tokens()
        except Exception as exc:
            log.warning("Anycubic-Token-Check (%s) fehlgeschlagen: %s", mode.name, exc)
            ok = False

        if ok:
            try:
                await api.get_user_info()
            except Exception as exc:
                log.warning("get_user_info fehlgeschlagen: %s", exc)
            if mode != preferred_mode:
                mode_str = "slicer" if mode == AnycubicAuthMode.SLICER else "web"
                log.info("Anycubic auth_mode automatisch auf '%s' korrigiert.", mode_str)
                if db is not None:
                    await set_setting(db, "auth_mode", mode_str)
            return api

    return None


async def _rest_refresh(printers) -> None:
    """ACE-Slots/Status per REST laden (funktioniert auch mit Web-Token ohne MQTT)."""
    for _p in printers:
        try:
            await asyncio.wait_for(_p.update_info_from_api(True), timeout=15)
        except Exception as exc:
            log.warning("REST-Refresh fehlgeschlagen fuer %s: %s", getattr(_p, "id", "?"), exc)


async def poll_once(db: aiosqlite.Connection, session: aiohttp.ClientSession) -> None:
    token = await get_setting(db, "token")
    auth_mode_raw = await get_setting(db, "auth_mode", "web")
    if not token:
        return

    # #557: nur noch den dauerhaften Live-Zustand verarbeiten (keine zweite MQTT-Sitzung)
    _lp = _live.get("printers")
    if _lp is None:
        log.info("poll_once: live_loop noch nicht verbunden - ueberspringe Zyklus.")
        return
    for printer in _lp:
        try:
            await process_printer(db, session, printer)
        except Exception:
            log.exception("Fehler beim Verarbeiten von Drucker %s", getattr(printer, "id", "?"))
    try:
        _printers_cache["data"] = await _serialize_printers(_lp)
        _printers_cache["ts"] = _time507.time()
    except Exception:
        log.exception("Cache-Befuellung fehlgeschlagen")
    return

    preferred_mode = (
        AnycubicAuthMode.SLICER if auth_mode_raw == "slicer" else AnycubicAuthMode.WEB
    )

    anycubic_cookie_jar = aiohttp.CookieJar()
    async with aiohttp.ClientSession(cookie_jar=anycubic_cookie_jar) as anycubic_session:
        api = await _resolve_auth_mode(anycubic_session, anycubic_cookie_jar, token, preferred_mode, db)
        if api is None:
            log.warning("Anycubic-Token ungueltig oder abgelaufen (weder slicer noch web).")
            return

        try:
            printers = await api.list_my_printers()
        except Exception as exc:
            log.warning("Druckerliste konnte nicht geladen werden: %s", exc)
            return


        await _rest_refresh(printers)

        for _p in printers:
            try:
                api.mqtt_add_subscribed_printer(_p)
            except Exception:
                pass
        mqtt_task = None
        try:
            mqtt_task = asyncio.create_task(asyncio.to_thread(api.connect_mqtt))
            await asyncio.wait_for(api.mqtt_wait_for_connect(), timeout=12)
            # 513fix: _latest_project ist nach jedem Poll-Zyklus None, weil die
            # Printer-Objekte frisch von list_my_printers() kommen. Die MQTT-
            # print_status-Handler in der Lib aktualisieren aber nur ein BEREITS
            # vorhandenes _latest_project (siehe _check_latest_project_id_valid),
            # legen nie eins neu an. Deshalb hier per REST vorladen ("primen"),
            # damit (a) sofort echte Projektdaten verfuegbar sind und (b) die
            # folgenden MQTT-Updates im Fenster tatsaechlich greifen.
            for _p in printers:
                try:
                    if str(getattr(_p, 'current_status', '')).lower() in ('busy', 'printing'):
                        _proj = await asyncio.wait_for(
                            api.get_latest_project(printer_id=getattr(_p, 'id', None)),
                            timeout=10,
                        )
                        if _proj is not None:
                            _p._latest_project = _proj
                except Exception:
                    log.exception("513fix: Konnte latest_project nicht vorladen fuer %s", getattr(_p, 'id', '?'))

            for _p in printers:
                try:
                    if getattr(_p, "has_peripheral_multi_color_box", False) and getattr(_p, "connected_ace_units", 0) == 0:
                        pass  # 478fix: no premature empty-box reset, lib keeps state via MQTT
                except Exception:
                    pass
                try:
                    _r478j = await asyncio.wait_for(api.multi_color_box_get_info(_p), timeout=5)
                    logging.getLogger("uvicorn.error").warning("DEBUG478j GET_INFO_OK result=%r", _r478j)
                except Exception as _e478j:
                    logging.getLogger("uvicorn.error").warning("DEBUG478j GET_INFO_FAIL %r: %s", type(_e478j), _e478j)
                    pass
            await _rest_refresh(printers)
            await asyncio.sleep(180)
            for _p in printers:
                try:
                    if getattr(_p, "has_peripheral_multi_color_box", False) and getattr(_p, "connected_ace_units", 0) == 0:
                        pass  # 478fix: no premature empty-box reset, lib keeps state via MQTT
                        try:
                            await asyncio.wait_for(api.multi_color_box_get_info(_p), timeout=5)
                        except Exception:
                            pass
                except Exception:
                    pass
            await asyncio.sleep(5)
        except Exception as exc:
            log.warning("Anycubic-MQTT-Verbindung fehlgeschlagen: %s", exc)
        finally:
            try:
                api.disconnect_mqtt()
            except Exception:
                pass
            if mqtt_task is not None:
                try:
                    await asyncio.wait_for(mqtt_task, timeout=5)
                except Exception:
                    pass

        for printer in printers:
            try:
                await process_printer(db, session, printer)
            except Exception:
                log.exception("Fehler beim Verarbeiten von Drucker %s", getattr(printer, "id", "?"))

        try:  # 511fix: Cache ERST NACH MQTT-Fenster befuellen, damit latest_project_* Live-Daten enthalten sind
            _printers_cache["data"] = await _serialize_printers(printers)
            _printers_cache["ts"] = _time507.time()
        except Exception:
            log.exception("511fix: Konnte Printers-Cache nicht aktualisieren")


async def process_printer(db: aiosqlite.Connection, session: aiohttp.ClientSession, printer: Any) -> None:
    printer_id = str(getattr(printer, "id", ""))
    if not printer_id:
        return

    usage_mm = getattr(printer, "latest_project_supplies_usage", None)
    latest_project = getattr(printer, "latest_project", None)
    task_id = str(getattr(latest_project, "id", "")) if latest_project else None

    if usage_mm is None:
        return

    cur = await db.execute(
        "SELECT task_id, baseline_usage_mm FROM job_state WHERE printer_id = ?",
        (printer_id,),
    )
    row = await cur.fetchone()

    if row is None or row["task_id"] != task_id:
        # Neuer Job (oder erster Poll ueberhaupt) -- Baseline setzen, noch
        # nichts buchen. Verhindert, dass beim Start ein bereits vergangener
        # Verbrauch faelschlich auf die aktuell geladene Spule gebucht wird.
        await db.execute(
            "INSERT INTO job_state (printer_id, task_id, baseline_usage_mm, last_booked_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(printer_id) DO UPDATE SET task_id = excluded.task_id, "
            "baseline_usage_mm = excluded.baseline_usage_mm",
            (printer_id, task_id, usage_mm, time.time()),
        )
        await db.commit()
        return

    baseline = row["baseline_usage_mm"] or 0
    delta_mm = usage_mm - baseline
    if delta_mm <= 0:
        return

    _CUR_PRINT["name"] = getattr(printer, "latest_project_name", None)
    # Aktiven Slot ermitteln (ueber alle ACE-Boxen des Druckers).
    boxes = [
        b for b in (
            getattr(printer, "primary_multi_color_box", None),
            getattr(printer, "secondary_multi_color_box", None),
        ) if b is not None
    ]

    log.info("BOOKDBG printer=%s task=%s delta_mm=%.1f boxes=%s", printer_id, task_id, delta_mm, [(getattr(b, "box_id", None), getattr(b, "loaded_slot", None), len(getattr(b, "slots", None) or [])) for b in (boxes or [])])
    def _resolve_slot_from_loaded():
        for box in boxes:
            loaded_slot = getattr(box, "loaded_slot", -1)
            if loaded_slot is not None and loaded_slot >= 0:
                box_id = getattr(box, "box_id", None)
                material = None
                try:
                    slots = getattr(box, "slots", None) or []
                    material = slots[loaded_slot].material_type
                except Exception:
                    material = None
                return box_id, loaded_slot, material
        return None, None, None

    def _slot_color(_bid, _si):
        for _b in boxes:
            if getattr(_b, "box_id", None) == _bid:
                try:
                    return list(_b.slots[_si].color)
                except Exception:
                    return None
        return None

    def _color_ok(_pc, _sc, _tol=60):
        try:
            if not _pc or not _sc or list(_sc)[:3] == [0, 0, 0]:
                return True
            _d = sum((int(x) - int(y)) ** 2 for x, y in zip(_pc[:3], _sc[:3])) ** 0.5
            return _d <= _tol
        except Exception:
            return True

    def _resolve_slot_for_global_index(global_index):
        # paint_infos liefert ggf. einen Index relativ zur Slicer-Materialliste
        # bzw. zum spool_index/ams_index-Feld -- hier best effort ueber die
        # Boxen hinweg durchgezaehlt (primary zuerst, dann secondary, je nach
        # eigener slots-Laenge). Noch nicht live gegen Mehr-ACE-Setups
        # verifiziert -- siehe Obsidian-Vault Docker/Anycubic-Bridge.md.
        if global_index is None:
            return None, None, None
        try:
            global_index = int(global_index)
        except (TypeError, ValueError):
            return None, None, None
        offset = 0
        _real = [b for b in boxes if (getattr(b, "box_id", None) is not None and getattr(b, "box_id") >= 0)]
        for box in (_real or boxes):
            slots = getattr(box, "slots", None) or []
            if offset <= global_index < offset + len(slots):
                local_index = global_index - offset
                material = None
                try:
                    material = slots[local_index].material_type
                except Exception:
                    material = None
                return getattr(box, "box_id", None), local_index, material
            offset += len(slots)
        return None, None, None

    async def _book_slot(box_id, slot_index, material, grams, label):
        if box_id is None or slot_index is None or grams <= 0:
            return True
        cur = await db.execute(
            "SELECT spool_id FROM mappings WHERE printer_id = ? AND box_id = ? AND slot_index = ?",
            (printer_id, box_id, slot_index),
        )
        mapping = await cur.fetchone()
        spool_id = mapping["spool_id"] if mapping is not None else None
        if spool_id is None:
            spool_id = await _resolve_spool_via_storage_link(session, printer_id, box_id, slot_index)
        log.info("BOOKDBG label=%s mapping=%s spool=%s grams=%.2f", label, mapping is not None, spool_id, grams)
        if spool_id is None:
            log.debug("Kein Mapping fuer Slot %s (Drucker %s) -- ueberspringe Buchung.", label, printer_id)
            return True
        booked = await book_usage(session, spool_id, grams)
        if not booked:
            log.warning("Buchung fehlgeschlagen fuer Slot %s (Drucker %s, %.2fg).", label, printer_id, grams)
        return booked

    # Mehrfarb-Aufteilung: wenn der Slicer mehrere Materialien mit Verbrauch > 0
    # meldet, den gemessenen Gesamt-Delta proportional aufteilen (wie Spooly/
    # hass-anycubic) statt alles einem einzigen Slot zuzuschreiben.
    materials = []
    if latest_project is not None:
        raw_materials = getattr(latest_project, "slice_material_info_list", None) or []
        for m in raw_materials:
            if not isinstance(m, dict):
                continue
            used = m.get("filament_used")
            if isinstance(used, (int, float)) and used > 0:
                materials.append(m)

    all_ok = True

    if len(materials) > 1:
        total_used = sum(float(m["filament_used"]) for m in materials)
        if total_used > 0:
            for m in materials:
                log.info("BOOKDBG mat=%s", {k: v for k, v in m.items() if "url" not in str(k).lower() and "thumb" not in str(k).lower()})
                share = float(m["filament_used"]) / total_used
                delta_mm_for_slot = delta_mm * share
                global_index = m.get("spool_index")
                if global_index is None:
                    global_index = m.get("ams_index")
                _paint = False
                if global_index is None:
                    global_index = m.get("paint_index")
                    _paint = True
                if _paint and global_index is not None:
                    _ord = await _ordered_slots(session, printer_id)
                    if _ord is not None:
                        try:
                            _gi = int(global_index)
                        except (TypeError, ValueError):
                            _gi = -1
                        if 0 <= _gi < len(_ord):
                            _bid, _pos, _sp = _ord[_gi]
                            if not _color_ok(m.get("paint_color"), _slot_color(_bid, _pos)):
                                log.warning("COLORMISMATCH idx=%s box=%s pos=%s: Cloud %s vs Slot %s -- NICHT gebucht (Sync vergessen?)", _gi, _bid, _pos, m.get("paint_color"), _slot_color(_bid, _pos))
                                continue
                            _g = grams_from_mm(delta_mm_for_slot, m.get("material_type") or "PLA")
                            if _g > 0:
                                _ok = await book_usage(session, _sp, _g)
                                log.info("BOOKDBG ordered idx=%s box=%s pos=%s spool=%s grams=%.2f ok=%s", _gi, _bid, _pos, _sp, _g, _ok)
                                all_ok = bool(_ok) and all_ok
                        else:
                            log.warning("Index %s ausserhalb der Slotliste (%s Eintraege) -- NICHT gebucht", _gi, len(_ord))
                        continue
                if _paint and global_index == 0:
                    if not _color_ok(m.get("paint_color"), _slot_color(-1, 0)):
                        log.warning("COLORMISMATCH extern: Cloud %s vs Slot %s -- NICHT gebucht (Sync vergessen?)", m.get("paint_color"), _slot_color(-1, 0))
                        continue
                    _ext = await _resolve_external_spool(session, printer_id)
                    _mt = m.get("material_type") or "PLA"
                    _g = grams_from_mm(delta_mm_for_slot, _mt)
                    if _ext is not None and _g > 0:
                        _ok = await book_usage(session, _ext, _g)
                        log.info("BOOKDBG external(multi) spool=%s grams=%.2f ok=%s", _ext, _g, _ok)
                        all_ok = bool(_ok) and all_ok
                    continue
                if _paint and global_index is not None:
                    global_index = global_index - 1
                box_id, slot_index, material = _resolve_slot_for_global_index(global_index)
                if box_id is None or slot_index is None:
                    log.debug(
                        "Mehrfarb-Material (Index %r) konnte keinem ACE-Slot zugeordnet werden -- ueberspringe.",
                        global_index,
                    )
                    continue
                if not _color_ok(m.get("paint_color"), _slot_color(box_id, slot_index)):
                    log.warning("COLORMISMATCH box=%s slot=%s: Cloud %s vs Slot %s -- NICHT gebucht (Sync vergessen?)", box_id, slot_index, m.get("paint_color"), _slot_color(box_id, slot_index))
                    continue
                grams = grams_from_mm(delta_mm_for_slot, material or m.get("material_type"))
                if grams > 0:
                    all_ok = await _book_slot(box_id, slot_index, material, grams, f"box={box_id} slot={slot_index}") and all_ok
    elif len(materials) == 1:
        # Nur ein Material mit Verbrauch > 0: paint_index ist hier immer 0 und
        # sagt nichts ueber den physischen Slot aus -- den tatsaechlich
        # eingezogenen Slot verwenden (wie bisher).
        box_id, slot_index, material = _resolve_slot_from_loaded()
        if box_id is not None and slot_index is not None:
            grams = grams_from_mm(delta_mm, material)
            if grams > 0:
                all_ok = await _book_slot(box_id, slot_index, material, grams, f"box={box_id} slot={slot_index}") and all_ok
        else:
            _ext = await _resolve_external_spool(session, printer_id)
            if _ext is not None:
                _mat = (materials[0].get("material_type") if materials else None) or "PLA"
                _g = grams_from_mm(delta_mm, _mat)
                if _g > 0:
                    _ok = await book_usage(session, _ext, _g)
                    log.info("BOOKDBG external spool=%s grams=%.2f ok=%s", _ext, _g, _ok)
                    all_ok = bool(_ok) and all_ok
            else:
                log.warning("Kein aktiver Slot (loaded_slot) fuer Drucker %s, Druck %r, +%.1f mm -- Verbrauch NICHT gebucht.", printer_id, _CUR_PRINT.get("name"), delta_mm)
    else:
        # Keine Slicer-Materialinfo verfuegbar (z.B. lokal gesliced) -- Fallback
        # auf den aktuell eingezogenen Slot, wie zuvor.
        box_id, slot_index, material = _resolve_slot_from_loaded()
        if box_id is not None and slot_index is not None:
            grams = grams_from_mm(delta_mm, material)
            if grams > 0:
                all_ok = await _book_slot(box_id, slot_index, material, grams, f"box={box_id} slot={slot_index}") and all_ok
        else:
            _ext = await _resolve_external_spool(session, printer_id)
            if _ext is not None:
                _mat = (materials[0].get("material_type") if materials else None) or "PLA"
                _g = grams_from_mm(delta_mm, _mat)
                if _g > 0:
                    _ok = await book_usage(session, _ext, _g)
                    log.info("BOOKDBG external spool=%s grams=%.2f ok=%s", _ext, _g, _ok)
                    all_ok = bool(_ok) and all_ok
            else:
                log.warning("Kein aktiver Slot (loaded_slot) fuer Drucker %s, Druck %r, +%.1f mm -- Verbrauch NICHT gebucht.", printer_id, _CUR_PRINT.get("name"), delta_mm)

    if all_ok:
        await db.execute(
            "UPDATE job_state SET baseline_usage_mm = ?, last_booked_at = ? WHERE printer_id = ?",
            (usage_mm, time.time(), printer_id),
        )
        await db.commit()
    # sonst: Baseline bleibt stehen, naechster Poll versucht es mit dem dann
    # groesseren Delta erneut (gleiche Semantik wie zuvor bei Buchungsfehlern).


_live: dict = {"printers": None, "ts": 0.0}


async def _live_prime(printers) -> None:
    for _p in printers:
        try:
            await _p.update_info_from_api(True)
        except Exception as exc:
            log.warning("live REST refresh fehlgeschlagen: %s", exc)
        try:
            if str(getattr(_p, "current_status", "")).lower() in ("busy", "printing"):
                _api = getattr(_p, "_api_parent", None)
                _proj = await asyncio.wait_for(_api.get_latest_project(printer_id=getattr(_p, "id", None)), timeout=10)
                if _proj is not None:
                    _p._latest_project = _proj
        except Exception:
            pass


async def live_loop() -> None:
    """Dauerhafte Cloud-Verbindung (#557): MQTT bleibt offen und die Drucker-Objekte
    bleiben bestehen, damit ACE-Box-0-Ereignisse (feedFilament/Print-Reports)
    im Zustand akkumulieren - wie bei der HA-Integration."""
    while True:
        api = None
        mqtt_task = None
        try:
            db = await get_db()
            try:
                enabled = (await get_setting(db, "enabled", "0")) == "1"
                token = await get_setting(db, "token")
                raw = await get_setting(db, "auth_mode", "web")
            finally:
                await db.close()
            if not enabled or not token:
                await asyncio.sleep(30)
                continue
            pref = AnycubicAuthMode.SLICER if raw == "slicer" else AnycubicAuthMode.WEB
            jar = aiohttp.CookieJar()
            async with aiohttp.ClientSession(cookie_jar=jar) as sess:
                db = await get_db()
                try:
                    api = await _resolve_auth_mode(sess, jar, token, pref, db)
                finally:
                    await db.close()
                if api is None:
                    log.warning("live_loop: Token ungueltig oder abgelaufen.")
                    await asyncio.sleep(60)
                    continue
                printers = await api.list_my_printers()
                for _p in printers:
                    try:
                        api.mqtt_add_subscribed_printer(_p)
                    except Exception:
                        pass
                mqtt_task = asyncio.create_task(asyncio.to_thread(api.connect_mqtt))
                await asyncio.wait_for(api.mqtt_wait_for_connect(), timeout=20)
                await _live_prime(printers)
                _live["printers"] = printers
                _live["ts"] = _time507.time()
                log.info("live_loop: MQTT dauerhaft verbunden (%d Drucker).", len(printers))
                while True:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    db = await get_db()
                    try:
                        cur = await get_setting(db, "token")
                    finally:
                        await db.close()
                    if cur != token or mqtt_task.done():
                        break
                    await _live_prime(printers)
                    _live["ts"] = _time507.time()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("live_loop fehlgeschlagen")
        finally:
            _live["printers"] = None
            if api is not None:
                try:
                    api.disconnect_mqtt()
                except Exception:
                    pass
            if mqtt_task is not None:
                try:
                    await asyncio.wait_for(mqtt_task, timeout=5)
                except Exception:
                    pass
        await asyncio.sleep(30)


async def poll_loop() -> None:
    while True:
        try:
            db = await get_db()
            try:
                enabled = (await get_setting(db, "enabled", "0")) == "1"
                if enabled:
                    async with aiohttp.ClientSession() as session:
                        await poll_once(db, session)
            finally:
                await db.close()
        except Exception:
            log.exception("Polling-Durchlauf fehlgeschlagen")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


# -------------------------------------------------------------------- app --

async def print_sync_loop() -> None:
    """Importiert die Cloud-Druckhistorie periodisch (Standard alle 30 min)."""
    import os
    minutes = max(5, int(os.environ.get('PRINT_SYNC_MIN', '30')))
    await asyncio.sleep(120)
    while True:
        try:
            r = await prints_sync()
            log.info('auto print sync: %s', r)
        except Exception as e:
            log.warning('auto print sync failed: %s', e)
        await asyncio.sleep(minutes * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(poll_loop())
    live_task = asyncio.create_task(live_loop())
    sync_task = asyncio.create_task(print_sync_loop())
    yield
    task.cancel()
    sync_task.cancel()


app = FastAPI(title="anycubic-bridge", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.get("/api/connection")
async def connection_status() -> dict[str, Any]:
    ts = _live.get("ts") or 0.0
    return {
        "live": _live.get("printers") is not None,
        "last_update_age_seconds": (round(_time507.time() - ts) if ts else None),
    }


@app.get("/api/settings")
async def read_settings() -> dict[str, Any]:
    db = await get_db()
    try:
        enabled = (await get_setting(db, "enabled", "0")) == "1"
        token = await get_setting(db, "token")
        exp = await get_setting(db, "token_exp")
        exp_int = int(exp) if exp else None
        days_remaining = None
        if exp_int is not None:
            days_remaining = round((exp_int - time.time()) / 86400, 1)
        return {
            "enabled": enabled,
            "token_present": bool(token),
            "token_expires_at": exp_int,
            "days_remaining": days_remaining,
            "auth_mode": await get_setting(db, "auth_mode", "web"),
        }
    finally:
        await db.close()


@app.post("/api/settings")
async def write_settings(payload: SettingsPayload) -> dict[str, Any]:
    db = await get_db()
    try:
        await set_setting(db, "enabled", "1" if payload.enabled else "0")
        return {"ok": True}
    finally:
        await db.close()


@app.post("/api/auth/token")
async def receive_token(payload: TokenPayload) -> dict[str, Any]:
    exp = decode_jwt_exp(payload.token)
    db = await get_db()
    try:
        await set_setting(db, "token", payload.token)
        await set_setting(db, "auth_mode", payload.auth_mode)
        await set_setting(db, "token_received_at", str(int(time.time())))
        if exp is not None:
            await set_setting(db, "token_exp", str(exp))
        return {"ok": True, "expires_at": exp}
    finally:
        await db.close()


import time as _time507
_printers_cache_lock = asyncio.Lock()
_printers_cache: dict[str, Any] = {"data": None, "ts": 0.0}
PRINTERS_CACHE_TTL_SECONDS = 60  # 507fix


async def _serialize_printers(printers) -> dict[str, Any]:  # 507fix
        result = []
        for p in printers:
            boxes = []
            for box in (
                getattr(p, "primary_multi_color_box", None),
                getattr(p, "secondary_multi_color_box", None),
            ):
                if box is None:
                    continue
                boxes.append({
                    "box_id": getattr(box, "box_id", None),
                "loaded_slot": getattr(box, "loaded_slot", None),
                    "slots": [
                        {
                            "slot_index": slot.slot_index,
                            "material_type": getattr(slot, "material_type", None),
                            "color": getattr(slot, "color", None),
                            "color_group": getattr(slot, "color_group", None),
                        "type": getattr(slot, "type", None),
                        "material_name": getattr(slot, "material_name", None),
                            "sku": getattr(slot, "sku", None),
                            "status": getattr(slot, "status", None),
                            "consumables_percent": getattr(slot, "consumables_percent", None),
                        }
                        for slot in (getattr(box, "slots", None) or [])
                    ],
                })
            result.append({
                "printer_id": str(getattr(p, "id", "")),
                "name": getattr(p, "name", "?"),
                "current_status": str(getattr(p, "current_status", "")),
            "progress": {
                "project_name": getattr(p, "latest_project_name", None),
                "image_url": getattr(p, "latest_project_image_url", None),
                "progress_percentage": getattr(p, "latest_project_progress_percentage", None),
                "current_layer": getattr(p, "latest_project_print_current_layer", None),
                "total_layers": getattr(p, "latest_project_print_total_layers", None),
                "elapsed_minutes": getattr(p, "latest_project_print_time_elapsed_minutes", None),
                "remaining_minutes": getattr(p, "latest_project_print_time_remaining_minutes", None),
                "total_minutes": getattr(p, "latest_project_print_total_time_minutes", None),
                "approximate_completion_time": getattr(p, "latest_project_print_approximate_completion_time", None),
                "in_progress": getattr(p, "latest_project_print_in_progress", None),
                "curr_nozzle_temp": getattr(p, "curr_nozzle_temp", None),
                "curr_hotbed_temp": getattr(p, "curr_hotbed_temp", None),
                "target_nozzle_temp": getattr(p, "latest_project_target_nozzle_temp", None),
                "target_hotbed_temp": getattr(p, "latest_project_target_hotbed_temp", None),
            },
                "boxes": boxes,
            })
        try:
            _db = await get_db()
            try:
                _snap = json.loads(await get_setting(_db, "box_snapshot", "{}") or "{}")
                _changed = False
                for _r in result:
                    _k = str(_r.get("name"))
                    _sb = _snap.get(_k, {})
                    _have = set()
                    for _b in _r.get("boxes", []):
                        if _b.get("box_id") is None:
                            continue
                        _have.add(_b["box_id"])
                        if _b.get("slots") and _sb.get(str(_b["box_id"])) != _b:
                            _sb[str(_b["box_id"])] = _b
                            _changed = True
                    for _bid, _b in _sb.items():
                        if int(_bid) not in _have:
                            _r.setdefault("boxes", []).append({**_b, "stale": True})
                    _r["boxes"] = sorted(_r.get("boxes", []), key=lambda x: x.get("box_id") if x.get("box_id") is not None else -9)
                    _snap[_k] = _sb
                if _changed:
                    await set_setting(_db, "box_snapshot", json.dumps(_snap))
            finally:
                await _db.close()
        except Exception:
            log.exception("box_snapshot fehlgeschlagen")
        return {"printers": result}


@app.get("/api/printers")
async def list_printers() -> dict[str, Any]:
    # 507fix: gecachte Antwort statt bei jedem Request eine neue MQTT-Verbindung zu oeffnen
    now = _time507.time()
    # 507fix: Live-Verbindung nur noch im Hintergrund-Poll (poll_once), nie pro HTTP-Request
    async with _printers_cache_lock:
        if _printers_cache["data"] is not None:
            return _printers_cache["data"]
    return {"printers": [], "bridge_error": "Noch keine Daten vom Hintergrund-Polling (erster Zyklus laeuft noch)."}


async def _fetch_printers_live() -> dict[str, Any]:
    db = await get_db()
    try:
        token = await get_setting(db, "token")
        auth_mode_raw = await get_setting(db, "auth_mode", "web")
    finally:
        await db.close()

    if not token:
        raise HTTPException(status_code=400, detail="Kein Anycubic-Token hinterlegt.")

    preferred_mode = AnycubicAuthMode.SLICER if auth_mode_raw == "slicer" else AnycubicAuthMode.WEB

    printers_cookie_jar = aiohttp.CookieJar()
    async with aiohttp.ClientSession(cookie_jar=printers_cookie_jar) as session:
        resolve_db = await get_db()
        try:
            api = await _resolve_auth_mode(session, printers_cookie_jar, token, preferred_mode, resolve_db)
        finally:
            await resolve_db.close()
        if api is None:
            raise HTTPException(status_code=401, detail="Anycubic-Token ungueltig oder abgelaufen.")

        printers = await api.list_my_printers()
        for _pd in printers:
            try:
                logging.getLogger("uvicorn.error").warning("DEBUG478o RAW_PRINTER type=%r dir=%r slots=%r dict_attempt=%r", type(_pd), [a for a in dir(_pd) if not a.startswith('_')], getattr(_pd, '__slots__', None), (_pd.model_dump() if hasattr(_pd, 'model_dump') else (_pd.dict() if hasattr(_pd, 'dict') else None)))
                logging.getLogger("uvicorn.error").warning("DEBUG478p FIELDS connected_ace_units=%r primary_box=%r primary_info_obj=%r primary_spool_info_obj=%r primary_loaded_slot=%r secondary_box=%r secondary_info_obj=%r secondary_spool_info_obj=%r", getattr(_pd, 'connected_ace_units', 'MISSING'), getattr(_pd, 'primary_multi_color_box', 'MISSING'), getattr(_pd, 'primary_multi_color_box_info_object', 'MISSING'), getattr(_pd, 'primary_multi_color_box_spool_info_object', 'MISSING'), getattr(_pd, 'primary_multi_color_box_loaded_slot', 'MISSING'), getattr(_pd, 'secondary_multi_color_box', 'MISSING'), getattr(_pd, 'secondary_multi_color_box_info_object', 'MISSING'), getattr(_pd, 'secondary_multi_color_box_spool_info_object', 'MISSING'))
            except Exception as _ed:
                logging.getLogger("uvicorn.error").warning("DEBUG478n RAW_PRINTER_FAIL %r: %s", type(_ed), _ed)

        await _rest_refresh(printers)

        for _p in printers:
            try:
                api.mqtt_add_subscribed_printer(_p)
            except Exception:
                pass
        mqtt_task = None
        try:
            if preferred_mode != AnycubicAuthMode.SLICER:
                raise RuntimeError("skip_mqtt_non_slicer_mode")
            mqtt_task = asyncio.create_task(asyncio.to_thread(api.connect_mqtt))
            await asyncio.wait_for(api.mqtt_wait_for_connect(), timeout=12)
            # 513fix: _latest_project ist nach jedem Poll-Zyklus None, weil die
            # Printer-Objekte frisch von list_my_printers() kommen. Die MQTT-
            # print_status-Handler in der Lib aktualisieren aber nur ein BEREITS
            # vorhandenes _latest_project (siehe _check_latest_project_id_valid),
            # legen nie eins neu an. Deshalb hier per REST vorladen ("primen"),
            # damit (a) sofort echte Projektdaten verfuegbar sind und (b) die
            # folgenden MQTT-Updates im Fenster tatsaechlich greifen.
            for _p in printers:
                try:
                    if str(getattr(_p, 'current_status', '')).lower() in ('busy', 'printing'):
                        _proj = await asyncio.wait_for(
                            api.get_latest_project(printer_id=getattr(_p, 'id', None)),
                            timeout=10,
                        )
                        if _proj is not None:
                            _p._latest_project = _proj
                except Exception:
                    log.exception("513fix: Konnte latest_project nicht vorladen fuer %s", getattr(_p, 'id', '?'))

            for _p in printers:
                try:
                    if getattr(_p, "has_peripheral_multi_color_box", False) and getattr(_p, "connected_ace_units", 0) == 0:
                        pass  # 478fix: no premature empty-box reset, lib keeps state via MQTT
                except Exception:
                    pass
                try:
                    _r478m_1 = await asyncio.wait_for(api.multi_color_box_get_info(_p), timeout=5)
                    logging.getLogger("uvicorn.error").warning("DEBUG478m_1 GET_INFO_OK result=%r", _r478m_1)
                except Exception as _e478m_1:
                    logging.getLogger("uvicorn.error").warning("DEBUG478m_1 GET_INFO_FAIL %r: %s", type(_e478m_1), _e478m_1)
            await _rest_refresh(printers)
            await asyncio.sleep(180)
            for _p in printers:
                try:
                    if getattr(_p, "has_peripheral_multi_color_box", False) and getattr(_p, "connected_ace_units", 0) == 0:
                        pass  # 478fix: no premature empty-box reset, lib keeps state via MQTT
                        try:
                            _r478m_2 = await asyncio.wait_for(api.multi_color_box_get_info(_p), timeout=5)
                            logging.getLogger("uvicorn.error").warning("DEBUG478m_2 GET_INFO_OK result=%r", _r478m_2)
                        except Exception as _e478m_2:
                            logging.getLogger("uvicorn.error").warning("DEBUG478m_2 GET_INFO_FAIL %r: %s", type(_e478m_2), _e478m_2)
                except Exception:
                    pass
            await asyncio.sleep(5)
        except Exception:
            pass
        finally:
            try:
                api.disconnect_mqtt()
            except Exception:
                pass
            if mqtt_task is not None:
                try:
                    await asyncio.wait_for(mqtt_task, timeout=5)
                except Exception:
                    pass

    return await _serialize_printers(printers)


@app.get("/api/mappings")
async def list_mappings() -> dict[str, Any]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT printer_id, box_id, slot_index, spool_id FROM mappings")
        rows = await cur.fetchall()
        return {"mappings": [dict(r) for r in rows]}
    finally:
        await db.close()


@app.post("/api/mappings")
async def upsert_mapping(payload: MappingPayload) -> dict[str, Any]:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO mappings (printer_id, box_id, slot_index, spool_id) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(printer_id, box_id, slot_index) DO UPDATE SET spool_id = excluded.spool_id",
            (payload.printer_id, payload.box_id, payload.slot_index, payload.spool_id),
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@app.delete("/api/mappings")
async def delete_mapping(printer_id: str, box_id: int, slot_index: int) -> dict[str, Any]:
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM mappings WHERE printer_id = ? AND box_id = ? AND slot_index = ?",
            (printer_id, box_id, slot_index),
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@app.post("/api/prints/sync")
async def prints_sync(pages: int = 5) -> dict[str, Any]:
    """Importiert die Cloud-Druckhistorie ins Storage-Backend (idempotent)."""
    db = await get_db()
    try:
        token = await get_setting(db, "token")
        auth_mode_raw = await get_setting(db, "auth_mode", "web")
    finally:
        await db.close()
    if not token:
        raise HTTPException(status_code=400, detail="Kein Anycubic-Token hinterlegt.")
    preferred_mode = AnycubicAuthMode.SLICER if auth_mode_raw == "slicer" else AnycubicAuthMode.WEB
    jar = aiohttp.CookieJar()
    rows: list[dict[str, Any]] = []
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        rdb = await get_db()
        try:
            api = await _resolve_auth_mode(session, jar, token, preferred_mode, rdb)
        finally:
            await rdb.close()
        if api is None:
            raise HTTPException(status_code=401, detail="Token ungueltig")
        for page in range(1, max(1, pages) + 1):
            raw = await api.list_all_projects(page=page, raw_data=True)
            data = (raw or {}).get("data") or []
            for x in data:
                try:
                    mm = float(x.get("material") or 0)
                except (TypeError, ValueError):
                    mm = 0.0
                sp = x.get("slice_param")
                if isinstance(sp, str):
                    try:
                        sp = json.loads(sp)
                    except Exception:
                        sp = {}
                plates = (sp or {}).get("plate_infos") or []
                mat = (plates[0].get("material_type") if plates else None) or "PLA"
                grams = round(grams_from_mm(mm, mat), 1) if mm > 0 else 0.0
                ps = x.get("print_status")
                try:
                    dur = float(x.get("print_time") or 0)
                except (TypeError, ValueError):
                    dur = 0.0
                rows.append({
                    "cloud_id": str(x.get("id")),
                    "name": x.get("gcode_name") or x.get("task_name"),
                    "printer": x.get("machine_name"),
                    "start_ts": int(x.get("start_time") or x.get("create_time") or 0) or None,
                    "end_ts": int(x.get("end_time") or 0) or None,
                    "duration_min": dur,
                    "status": ("running" if not x.get("end_time") else ("done" if ps == 2 else "failed")),
                    "grams": grams,
                    "length_mm": mm,
                    "thumb": x.get("img") or None,
                    "reason": str(x.get("reason") or "").strip() if x.get("reason") not in (0, "0", None) else None,
                    "source": "cloud",
                })
            if len(data) < 100:
                break
    res = {"new": 0, "updated": 0, "matched_booked": 0}
    async with aiohttp.ClientSession() as s2:
        for k in range(0, len(rows), 100):
            async with s2.post(f"{STORAGE_BASE_URL}/prints/import", json={"items": rows[k:k + 100]}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status >= 400:
                    raise HTTPException(status_code=502, detail="Storage: " + (await resp.text())[:200])
                j = await resp.json()
                for key in res:
                    res[key] += j.get(key, 0)
    return {"fetched": len(rows), **res}
