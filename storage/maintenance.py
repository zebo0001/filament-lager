"""Wartungsbuch (maintenance log) fuer das Lagersystem.

Intervall-Basis: Druckstunden.
  - Stunden pro Drucker = Summe prints.duration_min/60.
  - Drucke ohne Dauer (z.B. manuelle Drucker) werden ueber Gramm / g_pro_h geschaetzt.
    g_pro_h = Mittelwert aller Drucke mit Dauer und Gramm (Fallback 20 g/h), je Drucker ueberschreibbar.
  - Drucker ohne Historie: Zusatzstunden (extra_hours) im Steckbrief.
Einbindung in app.py:  import maintenance; maintenance.setup(app, db)
"""
import datetime as _dt
import os
import re
import time
from typing import Optional

import httpx
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

ABRASIVE_RE = re.compile(r"((?<![a-z])(cf|gf)(?![a-z])|carbon|glass|wood|holz|glow|metal|copper|bronze|steel|marble)", re.I)
OUTGAS_RE = re.compile(r"\b(abs|asa|pc)\b", re.I)
ABRASIVE_EXTRA = 2.0  # abrasive Stunden zaehlen 3-fach (1 + 2 Extra) auf die Duesen-Laufzeit
FORECAST_MIN_DAYS = 7  # Prognose erst ab 7 Drucktagen in den letzten 30 Tagen
_MAT_CACHE = {"ts": 0, "map": {}}


def _classify(material, name=""):
    s = f"{material or ''} {name or ''}"
    if ABRASIVE_RE.search(s):
        return "abrasive"
    if OUTGAS_RE.search(s):
        return "outgassing"
    return "normal"

SOON_FRAC = 0.15  # "bald faellig" ab 15 % Restlaufzeit
_HARD_RE = re.compile(r"härte|harte|hard|wolfram|tungsten|ruby|rubin|hss|carbid|karbid", re.I)


def _abr_extra(material):
    """Zusatzgewicht abrasiver Stunden/kg: gehaertete Duesen verschleissen kaum mehr, Messing/Edelstahl dreifach."""
    return 0.0 if material and _HARD_RE.search(material) else ABRASIVE_EXTRA

# (key, title_de, title_en, interval_h, source, note)
_COMMON = [
    ("rails", "Schienen/Führungen reinigen und ölen", "Clean and oil rails/guides", 100, "community",
     "Richtwert: etwa monatlich; als Druckstunden angesetzt"),
    ("zscrew", "Z-Spindel reinigen und fetten", "Clean and grease Z lead screw", 250, "community",
     "Richtwert: etwa alle 3 Monate, Fett statt Öl"),
    ("hotend", "Düse und Heizblock reinigen", "Clean nozzle and heater block", 100, "community",
     "Richtwert: etwa monatlich"),
    ("plate", "Druckplatte reinigen", "Clean build plate", 50, "community", "Isopropanol, nicht mit Fingern anfassen"),
    ("fans", "Lüfter entstauben", "Dust off fans", 100, "community", "Regelmäßig prüfen, Staub entfernen (Richtwert)"),
    ("cutter", "Filament-Cutter prüfen", "Check filament cutter", 150, "community", "Etwa alle 3 Rollen prüfen (Richtwert)"),
    ("ptfe", "PTFE-Schlauch auf Verschleiß prüfen", "Check PTFE tube for wear", 270, "community",
     "Etwa alle 6 Rollen, bei CF-Filament öfter (Richtwert)"),
    ("belts", "Riemenspannung prüfen", "Check belt tension", 500, "community", "Nur bei Auffälligkeiten prüfen (Richtwert)"),
]
# Bambu-spezifische Herstellerangaben (nur für Bambu-Drucker)
_BAMBU_NOTES = {
    "fans": ("vendor", "Hersteller (Bambu): wöchentlich prüfen"),
    "cutter": ("vendor", "Hersteller (Bambu): alle 3 Rollen"),
    "ptfe": ("vendor", "Hersteller (Bambu): alle 6 Rollen, bei CF alle 2"),
    "belts": ("community", "Bambu: nur auf Meldung (HMS)"),
}
_EXTRA = {
    "bambu": [("idlers", "Umlenkrollen ölen", "Oil idler pulleys", 250, "vendor", "Bambu: alle 3 Monate (Öl)")],
    "kobra": [("wiper", "Düsen-Abstreifer reinigen", "Clean nozzle wiper", 100, "community",
               "Anycubic: eigene Anleitung, kein Intervall genannt")],
}
# (kind, name_de, life_h, source, note)
_COMP = [
    ("nozzle", "Düse (Messing)", 800, "community", "Messing ca. 6 Monate, QIDI: 800-1500 h (nicht abrasiv)"),
    ("plate", "Druckplatte (PEI)", 1500, "community", "Richtwert, hängt stark von Pflege ab"),
]


def _family(name: str, model: str = "") -> str:
    s = f"{name} {model}".lower()
    if "bambu" in s or " a1" in f" {s}" or "p1" in s or "x1" in s:
        return "bambu"
    if "kobra" in s or "anycubic" in s:
        return "kobra"
    return "generic"


class PrinterIn(BaseModel):
    model: Optional[str] = None
    serial: Optional[str] = None
    purchased: Optional[str] = None
    warranty_until: Optional[str] = None
    notes: Optional[str] = None
    extra_hours: Optional[float] = None
    g_per_h: Optional[float] = None


class TaskIn(BaseModel):
    printer: str
    title: str
    interval_h: float
    source: Optional[str] = "user"
    note: Optional[str] = None
    link: Optional[str] = None


class TaskUpd(BaseModel):
    title: Optional[str] = None
    interval_h: Optional[float] = None
    note: Optional[str] = None
    active: Optional[int] = None


class DoneIn(BaseModel):
    cost: Optional[float] = 0
    note: Optional[str] = None
    part_id: Optional[int] = None
    part_qty: Optional[float] = 1


class PostponeIn(BaseModel):
    hours: float = 20


class CompIn(BaseModel):
    printer: str
    kind: str  # nozzle | plate
    name: Optional[str] = None
    life_h: Optional[float] = 0  # Lebensdauer in 'unit' (0 = keine)
    mounted: int = 1
    note: Optional[str] = None
    unit: Optional[str] = "h"  # h | kg
    diameter: Optional[float] = None
    material: Optional[str] = None
    surface: Optional[str] = None
    clean_every: Optional[float] = 0
    price: Optional[float] = 0
    used_h: Optional[float] = 0
    used_kg: Optional[float] = 0
    used_abr_kg: Optional[float] = 0
    replace_task: Optional[int] = 0


class CompUpd(BaseModel):
    name: Optional[str] = None
    life_h: Optional[float] = None
    mounted: Optional[int] = None
    note: Optional[str] = None
    diameter: Optional[float] = None
    material: Optional[str] = None
    surface: Optional[str] = None
    clean_every: Optional[float] = None
    price: Optional[float] = None
    retired: Optional[int] = None


class ReplaceIn(BaseModel):
    cost: Optional[float] = 0
    note: Optional[str] = None
    name: Optional[str] = None
    life_h: Optional[float] = None
    part_id: Optional[int] = None
    part_qty: Optional[float] = 1


class PartIn(BaseModel):
    name: str
    qty: float = 0
    min_qty: float = 1
    price: Optional[float] = 0  # Preis je Packung
    printer: Optional[str] = None
    note: Optional[str] = None
    unit: Optional[str] = "Stück"  # Stück | ml | g
    pack_type: Optional[str] = "Stück"  # Stück | Flasche | Tube | Pack
    pack_size: Optional[float] = 1  # Menge je Packung in 'unit'
    symbol: Optional[str] = None
    category: Optional[str] = "Ersatzteil"  # Ersatzteil | Zubehör


class ServiceIn(BaseModel):
    cost: Optional[float] = 0
    note: Optional[str] = None


class PartUpd(BaseModel):
    name: Optional[str] = None
    qty: Optional[float] = None
    min_qty: Optional[float] = None
    price: Optional[float] = None
    printer: Optional[str] = None
    note: Optional[str] = None
    unit: Optional[str] = None
    pack_type: Optional[str] = None
    pack_size: Optional[float] = None
    symbol: Optional[str] = None
    category: Optional[str] = None


def _booklet_html(d):
    from html import escape as e

    def f(v, n=1):
        return "–" if v is None or v == "" else (f"{v:.{n}f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v))

    def dt(ts):
        return _dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y") if ts else ""

    def cost_txt(x):
        return "%.2f €" % x["cost"] if x["cost"] else ""

    st_txt = {"due": "Fällig", "soon": "Bald", "ok": "OK"}
    st_col = {"due": "#c0392b", "soon": "#d68910", "ok": "#1e8449"}
    s, sb = d["stats"], d["steckbrief"]
    kind_txt = {"done": "Erledigt", "postponed": "Verschoben", "setup": "Angelegt", "service": "Großer Service"}
    m = s.get("materials_kg", {})

    rows_t = "".join(
        f"<tr><td>{e(t['title'])}</td><td>{f(t['interval_h'],0)} h</td><td>{f(t['remaining_h'])} h</td>"
        f"<td>{'~' + str(t['eta_days']) + ' Tage' if t.get('eta_days') is not None else '–'}</td>"
        f"<td style='color:{st_col[t['status']]};font-weight:600'>{st_txt[t['status']]}</td></tr>"
        for t in d["tasks"]
    ) or "<tr><td colspan=5>Keine Aufgaben</td></tr>"
    rows_c = "".join(
        f"<tr><td>{e(c['title'])}</td><td>{f(c['life_h'],0) if c['life_h'] else '–'} {c.get('unit','h')}</td>"
        f"<td>{f(c['runtime_h'])} {c.get('unit','h')}</td>"
        f"<td>{f(c['remaining_h'])} {c.get('unit','h')}</td><td>{'montiert' if c['mounted'] else 'Lager'}</td>"
        f"<td style='color:{st_col[c['status']]};font-weight:600'>{st_txt[c['status']]}</td></tr>"
        for c in d["components"]
    ) or "<tr><td colspan=6>Keine Komponenten</td></tr>"
    rows_h = "".join(
        f"<tr><td>{dt(x['ts'])}</td><td>{kind_txt.get(x['kind'], e(x['kind']))}</td><td>{e(x['title'] or '')}</td>"
        f"<td>{f(x['at_h'])} h</td><td>{cost_txt(x)}</td><td>{e(x['note'] or '')}</td></tr>"
        for x in d["history"]
    ) or "<tr><td colspan=6>Noch keine Einträge</td></tr>"

    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><style>
body{{font-family:Helvetica,Arial,sans-serif;color:#1b2430;font-size:10.5pt}}
h1{{margin:0 0 2mm;font-size:22pt}} h2{{font-size:12pt;margin:7mm 0 2mm;border-bottom:1.5px solid #2b6cb0;padding-bottom:1mm;color:#2b6cb0}}
.sub{{color:#5b6773;font-size:9.5pt}} .score{{float:right;text-align:center;border:3px solid #2b6cb0;border-radius:50%;width:22mm;height:22mm;line-height:22mm;font-size:17pt;font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:9.5pt}} th{{text-align:left;color:#5b6773;font-weight:600;border-bottom:1px solid #bbb;padding:1.2mm 1.5mm}}
td{{padding:1.2mm 1.5mm;border-bottom:1px solid #e3e7eb;vertical-align:top}} tr{{page-break-inside:avoid}}
.kv{{display:grid;grid-template-columns:38mm 1fr 38mm 1fr;gap:1mm 4mm;font-size:10pt}} .kv b{{color:#5b6773;font-weight:600}}
.foot{{margin-top:8mm;color:#8a949e;font-size:8.5pt}}
</style></head><body>
<div class="score">{d['score']}</div>
<h1>Service-Heft</h1><div class="sub">{e(d['printer'])} · erstellt am {_dt.datetime.now().strftime('%d.%m.%Y')}</div>
<h2>Steckbrief</h2><div class="kv">
<b>Modell</b><span>{e(sb.get('model') or '–')}</span><b>Seriennummer</b><span>{e(sb.get('serial') or '–')}</span>
<b>Gekauft am</b><span>{e(sb.get('purchased') or '–')}</span><b>Garantie bis</b><span>{e(sb.get('warranty_until') or '–')}</span>
<b>Druckstunden</b><span>{f(s['hours'])} h</span><b>Drucke</b><span>{s['prints']}</span>
<b>Filament gesamt</b><span>{s['kg']} kg</span><b>Ø Tempo</b><span>{s['tempo_h_per_day']} h/Tag</span>
<b>Material</b><span>Normal {m.get('normal',0)} kg · Ausgasend {m.get('outgassing',0)} kg · Abrasiv {m.get('abrasive',0)} kg</span>
<b>Kosten gesamt</b><span>{d['cost_total']:.2f} €</span></div>
{('<p class="sub">Notizen: ' + e(sb['notes']) + '</p>') if sb.get('notes') else ''}
<h2>Wartungsaufgaben</h2><table><tr><th>Aufgabe</th><th>Intervall</th><th>Verbleibend</th><th>Prognose</th><th>Status</th></tr>{rows_t}</table>
<h2>Komponenten</h2><table><tr><th>Komponente</th><th>Lebensdauer</th><th>Laufzeit</th><th>Verbleibend</th><th>Zustand</th><th>Status</th></tr>{rows_c}</table>
<h2>Historie</h2><table><tr><th>Datum</th><th>Art</th><th>Eintrag</th><th>Bei</th><th>Kosten</th><th>Notiz</th></tr>{rows_h}</table>
<div class="foot">The Filament Storage System · Wartungsbuch. Druckstunden aus gebuchten Drucken; bei fehlender Dauer aus Filamentverbrauch geschätzt.</div>
</body></html>"""


def setup(app, db, spoolman_url=None):
    def init():
        with db() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS maint_printers (
                    printer TEXT PRIMARY KEY, model TEXT, serial TEXT, purchased TEXT,
                    warranty_until TEXT, notes TEXT, extra_hours REAL DEFAULT 0, g_per_h REAL,
                    set_up INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS maint_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, printer TEXT NOT NULL, key TEXT,
                    title TEXT NOT NULL, interval_h REAL NOT NULL, next_due_h REAL NOT NULL,
                    source TEXT, note TEXT, link TEXT, active INTEGER DEFAULT 1);
                CREATE TABLE IF NOT EXISTS maint_components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, printer TEXT NOT NULL, kind TEXT NOT NULL,
                    name TEXT NOT NULL, life_h REAL NOT NULL, mounted INTEGER DEFAULT 1,
                    banked_h REAL DEFAULT 0, mounted_since_h REAL, retired INTEGER DEFAULT 0, note TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS maint_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, printer TEXT NOT NULL, ts INTEGER NOT NULL,
                    at_h REAL, kind TEXT NOT NULL, title TEXT, cost REAL DEFAULT 0, note TEXT);
                CREATE TABLE IF NOT EXISTS maint_parts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, qty REAL DEFAULT 0,
                    min_qty REAL DEFAULT 1, price REAL DEFAULT 0, printer TEXT, note TEXT);
                """
            )
            have_p = {r[1] for r in c.execute("PRAGMA table_info(maint_parts)")}
            for col, ddl in (("unit", "TEXT DEFAULT 'Stück'"), ("pack_type", "TEXT DEFAULT 'Stück'"),
                             ("pack_size", "REAL DEFAULT 1"), ("symbol", "TEXT"), ("category", "TEXT DEFAULT 'Ersatzteil'")):
                if col not in have_p:
                    c.execute(f"ALTER TABLE maint_parts ADD COLUMN {col} {ddl}")
            have = {r[1] for r in c.execute("PRAGMA table_info(maint_components)")}
            for col, ddl in (
                ("unit", "TEXT DEFAULT 'h'"), ("diameter", "REAL"), ("material", "TEXT"), ("surface", "TEXT"),
                ("clean_every", "REAL DEFAULT 0"), ("last_clean", "REAL DEFAULT 0"), ("banked_kg", "REAL DEFAULT 0"),
                ("mounted_since_kg", "REAL"), ("mounted_since_abr_kg", "REAL"), ("price", "REAL DEFAULT 0"),
            ):
                if col not in have:
                    c.execute(f"ALTER TABLE maint_components ADD COLUMN {col} {ddl}")

    init()

    # ---------- Kernberechnung ----------
    def printers_known(c):
        names = [r[0] for r in c.execute("SELECT DISTINCT printer FROM prints WHERE printer IS NOT NULL AND printer<>''")]
        names += [r[0] for r in c.execute("SELECT name FROM manual_printers")]
        names += [r[0] for r in c.execute("SELECT printer FROM maint_printers")]
        out, seen = [], set()
        for n in names:
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out

    def global_gph(c):
        r = c.execute(
            "SELECT SUM(grams) g, SUM(duration_min)/60.0 h FROM prints "
            "WHERE duration_min>0 AND grams>0"
        ).fetchone()
        if r and r["g"] and r["h"]:
            return round(r["g"] / r["h"], 1)
        return 20.0

    def spool_materials():
        """spool_id -> (material, filament-name); 5 min Cache, Fehler -> leer."""
        if time.time() - _MAT_CACHE["ts"] < 300 and _MAT_CACHE["map"]:
            return _MAT_CACHE["map"]
        url = spoolman_url or os.environ.get("SPOOLMAN_URL", "http://lagersystem_spoolman:8000/api/v1")
        try:
            r = httpx.get(f"{url}/spool", params={"allow_archived": "true"}, timeout=8)
            r.raise_for_status()
            m = {}
            for s in r.json():
                f = s.get("filament") or {}
                m[s["id"]] = (f.get("material") or "", f.get("name") or "")
            _MAT_CACHE.update(ts=time.time(), map=m)
        except Exception:
            pass
        return _MAT_CACHE["map"]

    def stats(c, printer):
        mp = c.execute("SELECT * FROM maint_printers WHERE printer=?", (printer,)).fetchone()
        gph = (mp["g_per_h"] if mp and mp["g_per_h"] else None) or global_gph(c)
        rows = c.execute(
            "SELECT start_ts, duration_min, grams, status, spool_id FROM prints WHERE printer=? "
            "ORDER BY COALESCE(start_ts,0), id", (printer,)
        ).fetchall()
        extra = (mp["extra_hours"] or 0) if mp else 0
        mats = spool_materials()
        hours, grams, est_h = 0.0, 0.0, 0.0
        now = time.time()
        recent = 0.0
        days = set()
        cls_g = {"normal": 0.0, "outgassing": 0.0, "abrasive": 0.0}
        timeline = []  # (start_h, dauer_h, klasse)
        for r in rows:
            g = r["grams"] or 0
            d = r["duration_min"]
            if d and d > 0:
                h = d / 60.0
            elif g > 0:
                h = g / gph
                est_h += h
            else:
                h = 0.0
            mat = mats.get(r["spool_id"]) if r["spool_id"] else None
            cls = _classify(*mat) if mat else "normal"
            timeline.append((extra + hours, h, cls))
            hours += h
            grams += g
            cls_g[cls] += g
            ts = r["start_ts"] or 0
            if ts and now - ts <= 30 * 86400:
                recent += h
                days.add(_dt.datetime.fromtimestamp(ts).date())
        return {
            "hours": round(hours + extra, 1),
            "tracked_hours": round(hours, 1),
            "estimated_hours": round(est_h, 1),
            "extra_hours": extra,
            "prints": len(rows),
            "kg": round(grams / 1000.0, 2),
            "kg_total": grams / 1000.0,
            "abr_kg_total": cls_g["abrasive"] / 1000.0,
            "g_per_h": gph,
            "tempo_h_per_day": round(recent / 30.0, 2),
            "active_days_30": len(days),
            "materials_kg": {k: round(v / 1000.0, 2) for k, v in cls_g.items()},
            "_timeline": timeline,
        }

    def eta_days(rem, s):
        """Prognose in Kalendertagen; None wenn zu wenig Datenbasis."""
        if rem <= 0 or s["active_days_30"] < FORECAST_MIN_DAYS or s["tempo_h_per_day"] <= 0:
            return None
        return int(round(rem / s["tempo_h_per_day"]))

    def task_view(t, s):
        hours = s["hours"]
        rem = t["next_due_h"] - hours
        iv = t["interval_h"] or 1
        if rem <= 0:
            st = "due"
        elif rem <= max(iv * SOON_FRAC, 5):
            st = "soon"
        else:
            st = "ok"
        return {
            "id": t["id"], "kind": "task", "key": t["key"], "title": t["title"],
            "interval_h": t["interval_h"], "remaining_h": round(rem, 1), "status": st,
            "source": t["source"], "note": t["note"], "link": t["link"], "printer": t["printer"],
            "eta_days": eta_days(rem, s),
        }

    def abrasive_extra_h(s, since_h, hours_now, extra_factor=ABRASIVE_EXTRA):
        extra = 0.0
        for start, dur, cls in s["_timeline"]:
            if cls != "abrasive" or dur <= 0:
                continue
            a, b = max(start, since_h), min(start + dur, hours_now)
            if b > a:
                extra += (b - a) * extra_factor
        return extra

    def comp_usage(cm, s):
        """Verbrauchte Laufzeit der Komponente in ihrer Einheit (h oder kg, abrasiv gewichtet)."""
        ex = _abr_extra(cm["material"])
        hours = s["hours"]
        if (cm["unit"] or "h") == "kg":
            run = cm["banked_kg"] or 0
            if cm["mounted"]:
                ks, ka = cm["mounted_since_kg"], cm["mounted_since_abr_kg"]
                if ks is None:
                    ks = s["kg_total"]
                if ka is None:
                    ka = s["abr_kg_total"]
                run += (s["kg_total"] - ks) + ex * (s["abr_kg_total"] - ka)
            return max(run, 0.0)
        since = cm["mounted_since_h"] if cm["mounted_since_h"] is not None else hours
        run = cm["banked_h"] or 0
        if cm["mounted"]:
            run += hours - since
            if cm["kind"] == "nozzle":
                run += abrasive_extra_h(s, since, hours, ex)
        return max(run, 0.0)

    def comp_view(cm, s):
        unit = cm["unit"] or "h"
        run = comp_usage(cm, s)
        life = cm["life_h"] or 0
        ce = cm["clean_every"] or 0
        soon_abs = 5 if unit == "h" else 0.3
        rank = {"due": 0, "soon": 1, "ok": 2}
        checks = []
        for reason, total, rem in (
            ("life", life, life - run),
            ("clean", ce, ce - (run - (cm["last_clean"] or 0))),
        ):
            if total and total > 0:
                st = "due" if rem <= 0 else ("soon" if rem <= max(total * SOON_FRAC, soon_abs) else "ok")
                checks.append((rank[st], rem / total, reason, rem, total, st))
        if checks:
            checks.sort()
            _, _, reason, rem, total, st = checks[0]
            life_rem = next((c[3] for c in checks if c[2] == "life"), None)
            clean_rem = next((c[3] for c in checks if c[2] == "clean"), None)
        else:
            reason, rem, total, st, life_rem, clean_rem = None, None, 0, "ok", None, None
        rd = lambda v: None if v is None else round(v, 2 if unit == "kg" else 1)
        return {
            "id": cm["id"], "kind": "component", "comp_kind": cm["kind"], "title": cm["name"], "unit": unit,
            "life_h": life, "runtime_h": rd(run), "remaining_h": rd(rem), "interval_h": total, "reason": reason,
            "life_rem": rd(life_rem), "clean_rem": rd(clean_rem), "clean_every": ce,
            "diameter": cm["diameter"], "material": cm["material"], "surface": cm["surface"], "price": cm["price"],
            "mounted": cm["mounted"], "status": st, "note": cm["note"], "printer": cm["printer"],
        }

    def score_of(items):
        n = len(items)
        if n == 0:
            return 100
        bad = sum(1.0 if i["status"] == "due" else 0.5 if i["status"] == "soon" else 0 for i in items)
        return round(100 * (1 - bad / n))

    def printer_items(c, printer, s):
        tasks = [task_view(t, s) for t in c.execute(
            "SELECT * FROM maint_tasks WHERE printer=? AND active=1", (printer,))]
        comps = [comp_view(cm, s) for cm in c.execute(
            "SELECT * FROM maint_components WHERE printer=? AND retired=0 AND mounted=1", (printer,))]
        return tasks, comps

    def model_of(c, printer):
        mp = c.execute("SELECT model FROM maint_printers WHERE printer=?", (printer,)).fetchone()
        if mp and mp["model"]:
            return mp["model"]
        m = c.execute("SELECT model FROM manual_printers WHERE name=?", (printer,)).fetchone()
        return (m["model"] if m and m["model"] else "") or ""

    def log(c, printer, kind, title, at_h, cost=0, note=None):
        c.execute(
            "INSERT INTO maint_log (printer,ts,at_h,kind,title,cost,note) VALUES (?,?,?,?,?,?,?)",
            (printer, int(time.time()), at_h, kind, title, cost or 0, note),
        )

    def apply_template(c, printer):
        hours = stats(c, printer)["hours"]
        fam = _family(printer, model_of(c, printer))
        items = list(_COMMON) + list(_EXTRA.get(fam, []))
        for key, de, en, iv, src, note in items:
            if fam == "bambu" and key in _BAMBU_NOTES:
                src, note = _BAMBU_NOTES[key]
            if c.execute("SELECT 1 FROM maint_tasks WHERE printer=? AND key=?", (printer, key)).fetchone():
                continue
            c.execute(
                "INSERT INTO maint_tasks (printer,key,title,interval_h,next_due_h,source,note) VALUES (?,?,?,?,?,?,?)",
                (printer, key, de, iv, hours + iv, src, note),
            )
            log(c, printer, "setup", de, hours)
        for kind, name, life, src, note in _COMP:
            if c.execute("SELECT 1 FROM maint_components WHERE printer=? AND kind=?", (printer, kind)).fetchone():
                continue
            c.execute(
                "INSERT INTO maint_components (printer,kind,name,life_h,mounted,mounted_since_h,note) VALUES (?,?,?,?,1,?,?)",
                (printer, kind, name, life, hours, note),
            )
        c.execute(
            "INSERT INTO maint_printers (printer,set_up) VALUES (?,1) "
            "ON CONFLICT(printer) DO UPDATE SET set_up=1",
            (printer,),
        )

    # Migration: Bambu-Hinweise bei Nicht-Bambu-Druckern durch neutrale Texte ersetzen
    with db() as c:
        neutral = {k: (s_, n_) for k, _, _, _, s_, n_ in _COMMON}
        for p in [r[0] for r in c.execute("SELECT DISTINCT printer FROM maint_tasks")]:
            if _family(p, model_of(c, p)) == "bambu":
                continue
            for k, (s_, n_) in neutral.items():
                c.execute("UPDATE maint_tasks SET source=?, note=? WHERE printer=? AND key=? AND note LIKE '%Bambu%'",
                          (s_, n_, p, k))

    # Migration: Allgemeine "Hersteller"-Hinweise -> Community-Richtwerte
    with db() as c:
        for k, _, _, _, s_, n_ in _COMMON:
            if s_ == "community":
                c.execute("UPDATE maint_tasks SET source=?, note=? WHERE key=? AND note LIKE 'Hersteller: %' AND note NOT LIKE '%Bambu%'",
                          (s_, n_, k))

    # ---------- Endpoints ----------
    @app.get("/maintenance/overview")
    def overview():
        with db() as c:
            out, all_items, nxt = [], [], []
            for p in printers_known(c):
                s = stats(c, p)
                tasks, comps = printer_items(c, p, s)
                items = tasks + comps
                all_items += items
                for i in items:
                    if i["status"] != "ok":
                        nxt.append({**i, "printer": p})
                row = c.execute("SELECT set_up FROM maint_printers WHERE printer=?", (p,)).fetchone()
                out.append({
                    "printer": p, "hours": s["hours"], "prints": s["prints"], "kg": s["kg"],
                    "score": score_of(items), "components": len(items),
                    "due": sum(1 for i in items if i["status"] == "due"),
                    "soon": sum(1 for i in items if i["status"] == "soon"),
                    "ok": sum(1 for i in items if i["status"] == "ok"),
                    "set_up": bool(row and row["set_up"]),
                })
            order = {"due": 0, "soon": 1}
            nxt.sort(key=lambda i: (order.get(i["status"], 2), i["remaining_h"]))
            year = _dt.datetime.now().year
            t0 = int(_dt.datetime(year, 1, 1).timestamp())
            cost_year = c.execute("SELECT COALESCE(SUM(cost),0) v FROM maint_log WHERE ts>=?", (t0,)).fetchone()["v"]
            parts = c.execute("SELECT COUNT(*) n, SUM(qty<=0) e FROM maint_parts").fetchone()
            return {
                "score": score_of(all_items),
                "due": sum(1 for i in all_items if i["status"] == "due"),
                "soon": sum(1 for i in all_items if i["status"] == "soon"),
                "ok": sum(1 for i in all_items if i["status"] == "ok"),
                "components": len(all_items), "printers": out, "next": nxt[:12],
                "cost_year": round(cost_year, 2), "parts": parts["n"] or 0, "parts_empty": parts["e"] or 0,
            }

    def detail_data(c, printer):
        s = stats(c, printer)
        tasks, comps = printer_items(c, printer, s)
        all_comps = [comp_view(cm, s) for cm in c.execute(
            "SELECT * FROM maint_components WHERE printer=? AND retired=0", (printer,))]
        mp = c.execute("SELECT * FROM maint_printers WHERE printer=?", (printer,)).fetchone()
        hist = [dict(r) for r in c.execute(
            "SELECT * FROM maint_log WHERE printer=? ORDER BY ts DESC, id DESC LIMIT 200", (printer,))]
        cost = c.execute("SELECT COALESCE(SUM(cost),0) v FROM maint_log WHERE printer=?", (printer,)).fetchone()["v"]
        items = tasks + comps
        order = {"due": 0, "soon": 1, "ok": 2}
        tasks.sort(key=lambda i: (order[i["status"]], i["remaining_h"]))
        pub = {k: v for k, v in s.items() if not k.startswith("_")}
        return {
            "printer": printer, "family": _family(printer, model_of(c, printer)),
            "steckbrief": {k: (mp[k] if mp else None) for k in
                           ("model", "serial", "purchased", "warranty_until", "notes", "extra_hours", "g_per_h")},
            "stats": pub, "score": score_of(items), "tasks": tasks, "components": all_comps,
            "history": hist, "cost_total": round(cost, 2),
            "set_up": bool(mp and mp["set_up"]),
        }

    @app.get("/maintenance/printer/{printer}")
    def printer_detail(printer: str):
        with db() as c:
            if printer not in printers_known(c):
                raise HTTPException(404, "Drucker unbekannt")
            return detail_data(c, printer)

    @app.post("/maintenance/printer/{printer}/service")
    def printer_service(printer: str, body: ServiceIn):
        """Grosser Service: alle aktiven Aufgaben auf 'jetzt erledigt' setzen."""
        with db() as c:
            if printer not in printers_known(c):
                raise HTTPException(404, "Drucker unbekannt")
            h = stats(c, printer)["hours"]
            n = 0
            for t in c.execute("SELECT * FROM maint_tasks WHERE printer=? AND active=1", (printer,)).fetchall():
                c.execute("UPDATE maint_tasks SET next_due_h=? WHERE id=?", (h + t["interval_h"], t["id"]))
                n += 1
            log(c, printer, "service", f"Großer Service ({n} Aufgaben)", h, body.cost or 0, body.note)
        return {"ok": True, "tasks": n}

    @app.get("/maintenance/booklet/{printer}")
    async def printer_booklet(printer: str):
        from playwright.async_api import async_playwright
        with db() as c:
            if printer not in printers_known(c):
                raise HTTPException(404, "Drucker unbekannt")
            d = detail_data(c, printer)
        html = _booklet_html(d)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--no-sandbox"])
            try:
                page = await browser.new_page()
                await page.set_content(html, wait_until="load")
                pdf = await page.pdf(format="A4", print_background=True,
                                     margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"})
            finally:
                await browser.close()
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", printer)
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="Service-Heft_{safe}.pdf"'})

    @app.post("/maintenance/printer/{printer}/setup")
    def printer_setup(printer: str):
        with db() as c:
            if printer not in printers_known(c):
                raise HTTPException(404, "Drucker unbekannt")
            apply_template(c, printer)
        return {"ok": True}

    @app.put("/maintenance/printer/{printer}")
    def printer_update(printer: str, body: PrinterIn):
        with db() as c:
            c.execute("INSERT OR IGNORE INTO maint_printers (printer) VALUES (?)", (printer,))
            d = body.dict(exclude_unset=True)
            if "extra_hours" in d:
                old = c.execute("SELECT extra_hours FROM maint_printers WHERE printer=?", (printer,)).fetchone()
                delta = (d["extra_hours"] or 0) - ((old["extra_hours"] if old else 0) or 0)
                if delta:  # Vorlauf-Stunden: Faelligkeiten und Montagestand mitverschieben
                    c.execute("UPDATE maint_tasks SET next_due_h=next_due_h+? WHERE printer=?", (delta, printer))
                    c.execute("UPDATE maint_components SET mounted_since_h=mounted_since_h+? "
                              "WHERE printer=? AND mounted=1", (delta, printer))
            for k, v in d.items():
                c.execute(f"UPDATE maint_printers SET {k}=? WHERE printer=?", (v, printer))
        return {"ok": True}

    @app.post("/maintenance/tasks")
    def task_add(body: TaskIn):
        with db() as c:
            h = stats(c, body.printer)["hours"]
            cur = c.execute(
                "INSERT INTO maint_tasks (printer,title,interval_h,next_due_h,source,note,link) VALUES (?,?,?,?,?,?,?)",
                (body.printer, body.title, body.interval_h, h + body.interval_h, body.source, body.note, body.link),
            )
            log(c, body.printer, "setup", body.title, h)
            return {"id": cur.lastrowid}

    @app.put("/maintenance/tasks/{tid}")
    def task_update(tid: int, body: TaskUpd):
        with db() as c:
            t = c.execute("SELECT * FROM maint_tasks WHERE id=?", (tid,)).fetchone()
            if not t:
                raise HTTPException(404)
            d = body.dict(exclude_unset=True)
            if "interval_h" in d and d["interval_h"]:
                h = stats(c, t["printer"])["hours"]
                done_at = t["next_due_h"] - t["interval_h"]
                c.execute("UPDATE maint_tasks SET next_due_h=? WHERE id=?", (max(done_at, 0) + d["interval_h"], tid))
            for k, v in d.items():
                c.execute(f"UPDATE maint_tasks SET {k}=? WHERE id=?", (v, tid))
        return {"ok": True}

    @app.delete("/maintenance/tasks/{tid}")
    def task_delete(tid: int):
        with db() as c:
            c.execute("DELETE FROM maint_tasks WHERE id=?", (tid,))
        return {"ok": True}

    def use_part(c, part_id, qty=1):
        """Verbraucht qty (in der Einheit des Artikels). Rueckgabe: (Artikel, Kosten) oder (None, 0)."""
        if not part_id:
            return None, 0
        p = c.execute("SELECT * FROM maint_parts WHERE id=?", (part_id,)).fetchone()
        if not p:
            return None, 0
        qty = qty if qty is not None else 1
        c.execute("UPDATE maint_parts SET qty=? WHERE id=?", (max((p["qty"] or 0) - qty, 0), part_id))
        size = p["pack_size"] or 1
        return p, round((p["price"] or 0) / size * qty, 2)

    @app.post("/maintenance/tasks/{tid}/done")
    def task_done(tid: int, body: DoneIn):
        with db() as c:
            t = c.execute("SELECT * FROM maint_tasks WHERE id=?", (tid,)).fetchone()
            if not t:
                raise HTTPException(404)
            h = stats(c, t["printer"])["hours"]
            c.execute("UPDATE maint_tasks SET next_due_h=? WHERE id=?", (h + t["interval_h"], tid))
            cost = body.cost or 0
            part, pcost = use_part(c, body.part_id, body.part_qty)
            if part and not cost:
                cost = pcost
            log(c, t["printer"], "done", t["title"], h, cost, body.note)
        return {"ok": True}

    @app.post("/maintenance/tasks/{tid}/postpone")
    def task_postpone(tid: int, body: PostponeIn):
        with db() as c:
            t = c.execute("SELECT * FROM maint_tasks WHERE id=?", (tid,)).fetchone()
            if not t:
                raise HTTPException(404)
            h = stats(c, t["printer"])["hours"]
            c.execute("UPDATE maint_tasks SET next_due_h=? WHERE id=?",
                      (max(t["next_due_h"], h) + body.hours, tid))
            log(c, t["printer"], "postponed", t["title"], h, 0, f"+{body.hours:g} h")
        return {"ok": True}

    def mount_marks(s):
        return s["hours"], s["kg_total"], s["abr_kg_total"]

    @app.post("/maintenance/components")
    def comp_add(body: CompIn):
        with db() as c:
            s = stats(c, body.printer)
            h, kg, akg = mount_marks(s)
            unit = "kg" if body.unit == "kg" else "h"
            ex = _abr_extra(body.material)
            name = (body.name or "").strip()
            if not name:
                if body.kind == "nozzle":
                    name = "Düse" + (f" {body.diameter:g} mm" if body.diameter else "") + (f" {body.material}" if body.material else "")
                else:
                    name = "Druckplatte" + (f" {body.surface}" if body.surface else "")
            banked_h = body.used_h or 0
            banked_kg = (body.used_kg or 0) + ex * (body.used_abr_kg or 0)
            start_use = banked_kg if unit == "kg" else banked_h
            cur = c.execute(
                "INSERT INTO maint_components (printer,kind,name,life_h,mounted,banked_h,banked_kg,mounted_since_h,"
                "mounted_since_kg,mounted_since_abr_kg,note,unit,diameter,material,surface,clean_every,last_clean,price) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (body.printer, body.kind, name, body.life_h or 0, body.mounted, banked_h, banked_kg,
                 h if body.mounted else None, kg if body.mounted else None, akg if body.mounted else None,
                 body.note, unit, body.diameter, body.material, body.surface, body.clean_every or 0,
                 start_use, body.price or 0),
            )
            if body.kind == "plate" and body.replace_task:
                c.execute("UPDATE maint_tasks SET active=0 WHERE printer=? AND key='plate'", (body.printer,))
            log(c, body.printer, "setup", name, h, body.price or 0)
            return {"id": cur.lastrowid}

    @app.put("/maintenance/components/{cid}")
    def comp_update(cid: int, body: CompUpd):
        with db() as c:
            cm = c.execute("SELECT * FROM maint_components WHERE id=?", (cid,)).fetchone()
            if not cm:
                raise HTTPException(404)
            s = stats(c, cm["printer"])
            h, kg, akg = mount_marks(s)
            d = body.dict(exclude_unset=True)
            if "mounted" in d and d["mounted"] != cm["mounted"]:
                if d["mounted"]:
                    c.execute("UPDATE maint_components SET mounted_since_h=?, mounted_since_kg=?, mounted_since_abr_kg=? "
                              "WHERE id=?", (h, kg, akg, cid))
                else:
                    ex = _abr_extra(cm["material"])
                    run_h = h - (cm["mounted_since_h"] if cm["mounted_since_h"] is not None else h)
                    if cm["kind"] == "nozzle":
                        run_h += abrasive_extra_h(s, cm["mounted_since_h"] if cm["mounted_since_h"] is not None else h, h, ex)
                    ks = cm["mounted_since_kg"] if cm["mounted_since_kg"] is not None else kg
                    ka = cm["mounted_since_abr_kg"] if cm["mounted_since_abr_kg"] is not None else akg
                    run_kg = (kg - ks) + ex * (akg - ka)
                    c.execute("UPDATE maint_components SET banked_h=banked_h+?, banked_kg=banked_kg+?, "
                              "mounted_since_h=NULL, mounted_since_kg=NULL, mounted_since_abr_kg=NULL WHERE id=?",
                              (run_h, run_kg, cid))
            for k, v in d.items():
                c.execute(f"UPDATE maint_components SET {k}=? WHERE id=?", (v, cid))
        return {"ok": True}

    @app.post("/maintenance/components/{cid}/clean")
    def comp_clean(cid: int):
        with db() as c:
            cm = c.execute("SELECT * FROM maint_components WHERE id=?", (cid,)).fetchone()
            if not cm:
                raise HTTPException(404)
            s = stats(c, cm["printer"])
            c.execute("UPDATE maint_components SET last_clean=? WHERE id=?", (comp_usage(cm, s), cid))
            log(c, cm["printer"], "done", f"{cm['name']} gereinigt", s["hours"], 0, None)
        return {"ok": True}

    @app.post("/maintenance/components/{cid}/replace")
    def comp_replace(cid: int, body: ReplaceIn):
        with db() as c:
            cm = c.execute("SELECT * FROM maint_components WHERE id=?", (cid,)).fetchone()
            if not cm:
                raise HTTPException(404)
            h, kg, akg = mount_marks(stats(c, cm["printer"]))
            c.execute("UPDATE maint_components SET retired=1, mounted=0 WHERE id=?", (cid,))
            c.execute(
                "INSERT INTO maint_components (printer,kind,name,life_h,mounted,mounted_since_h,mounted_since_kg,"
                "mounted_since_abr_kg,note,unit,diameter,material,surface,clean_every,price) "
                "VALUES (?,?,?,?,1,?,?,?,?,?,?,?,?,?,?)",
                (cm["printer"], cm["kind"], body.name or cm["name"], body.life_h or cm["life_h"], h, kg, akg,
                 cm["note"], cm["unit"] or "h", cm["diameter"], cm["material"], cm["surface"],
                 cm["clean_every"] or 0, cm["price"] or 0),
            )
            cost = body.cost or 0
            part, pcost = use_part(c, body.part_id, body.part_qty)
            if part and not cost:
                cost = pcost
            log(c, cm["printer"], "done", f"{cm['name']} getauscht", h, cost, body.note)
        return {"ok": True}

    @app.get("/maintenance/parts")
    def parts_list():
        with db() as c:
            return [dict(r) for r in c.execute("SELECT * FROM maint_parts ORDER BY name")]

    @app.post("/maintenance/parts")
    def parts_add(body: PartIn):
        with db() as c:
            cur = c.execute(
                "INSERT INTO maint_parts (name,qty,min_qty,price,printer,note,unit,pack_type,pack_size,symbol,category) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (body.name, body.qty, body.min_qty, body.price, body.printer, body.note,
                 body.unit, body.pack_type, body.pack_size or 1, body.symbol, body.category),
            )
            return {"id": cur.lastrowid}

    @app.put("/maintenance/parts/{pid}")
    def parts_update(pid: int, body: PartUpd):
        with db() as c:
            for k, v in body.dict(exclude_unset=True).items():
                c.execute(f"UPDATE maint_parts SET {k}=? WHERE id=?", (v, pid))
        return {"ok": True}

    @app.delete("/maintenance/parts/{pid}")
    def parts_delete(pid: int):
        with db() as c:
            c.execute("DELETE FROM maint_parts WHERE id=?", (pid,))
        return {"ok": True}

    @app.get("/maintenance/costs")
    def costs():
        with db() as c:
            rows = [dict(r) for r in c.execute(
                "SELECT * FROM maint_log WHERE cost>0 ORDER BY ts DESC LIMIT 500")]
            per = [dict(r) for r in c.execute(
                "SELECT printer, ROUND(SUM(cost),2) total FROM maint_log GROUP BY printer HAVING total>0")]
            year = _dt.datetime.now().year
            t0 = int(_dt.datetime(year, 1, 1).timestamp())
            y = c.execute("SELECT COALESCE(SUM(cost),0) v FROM maint_log WHERE ts>=?", (t0,)).fetchone()["v"]
            tot = c.execute("SELECT COALESCE(SUM(cost),0) v FROM maint_log").fetchone()["v"]
            return {"year": round(y, 2), "total": round(tot, 2), "per_printer": per, "entries": rows}
