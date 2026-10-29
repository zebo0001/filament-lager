"""Spoolman-API-v1-kompatibles Modul (Abloesung von Spoolman).
Filament-Datenbank: SpoolmanDB (MIT) https://github.com/Donkie/SpoolmanDB - Dank an Donkie & Community."""
import os, json, math, sqlite3, asyncio, time, sys, threading
import datetime as dt
from contextlib import contextmanager
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

DB = os.environ.get("SM_DB_PATH", "/data/spoolman_compat.db")
EXT_URL = os.environ.get("SM_EXTERNAL_URL", "https://donkie.github.io/SpoolmanDB/filaments.json")
EXT_CACHE = os.environ.get("SM_EXTERNAL_CACHE", "/data/spoolmandb_filaments.json")
EXT_EVERY = int(os.environ.get("SM_EXTERNAL_HOURS", "24")) * 3600
router = APIRouter()
_lock = threading.RLock()
VKEYS = ["name", "comment", "empty_spool_weight", "external_id"]
FKEYS = ["name", "material", "price", "density", "diameter", "weight", "spool_weight", "article_number", "comment", "settings_extruder_temp", "settings_bed_temp", "color_hex", "multi_color_hexes", "multi_color_direction", "external_id", "tags"]
SKEYS = ["price", "initial_weight", "spool_weight", "used_weight", "location", "lot_nr", "comment", "archived", "first_used", "last_used", "tags"]


class SmErr(Exception):
    def __init__(self, status, msg):
        self.status, self.msg = status, msg


def err(status, msg):
    raise SmErr(status, msg)


@contextmanager
def db():
    c = sqlite3.connect(DB, timeout=30)
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with db() as c:
        c.executescript("""
CREATE TABLE IF NOT EXISTS sm_doc(kind TEXT NOT NULL, id INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY(kind,id));
CREATE TABLE IF NOT EXISTS sm_field(entity TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(entity,key));
CREATE TABLE IF NOT EXISTS sm_setting(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS sm_ext_custom(id TEXT PRIMARY KEY, data TEXT NOT NULL);
""")


def now():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def load(c, kind, id):
    r = c.execute("SELECT data FROM sm_doc WHERE kind=? AND id=?", (kind, id)).fetchone()
    return json.loads(r[0]) if r else None


def all_(c, kind):
    return [json.loads(r[0]) for r in c.execute("SELECT data FROM sm_doc WHERE kind=? ORDER BY id", (kind,))]


def save(c, kind, d):
    c.execute("INSERT OR REPLACE INTO sm_doc VALUES(?,?,?)", (kind, d["id"], json.dumps(d, ensure_ascii=False)))


def next_id(c, kind):
    r = c.execute("SELECT MAX(id) FROM sm_doc WHERE kind=?", (kind,)).fetchone()[0] or 0
    s = c.execute("SELECT value FROM sm_setting WHERE key=?", ("_seq_" + kind,)).fetchone()
    n = max(r, int(s[0]) if s else 0) + 1
    c.execute("INSERT OR REPLACE INTO sm_setting VALUES(?,?)", ("_seq_" + kind, str(n)))
    return n


def need(c, kind, id, label):
    d = load(c, kind, id) if id is not None else None
    if d is None:
        err(404, "No %s with ID %s found." % (label, id))
    return d


def length(w, f):
    d, dn = f.get("diameter"), f.get("density")
    if w is None or not d or not dn:
        return None
    return (w / dn * 1000) / (math.pi * (d / 2) ** 2)


def _comp_vendor(v):
    return {"id": v["id"], "registered": v.get("registered"), "name": v.get("name"), "comment": v.get("comment"), "empty_spool_weight": v.get("empty_spool_weight"), "external_id": v.get("external_id"), "extra": v.get("extra") or {}}


def comp_filament(c, f):
    out = {"id": f["id"], "registered": f.get("registered")}
    for k in FKEYS:
        out[k] = f.get(k)
    out["tags"] = f.get("tags") or []
    out = nn(out)
    v = load(c, "vendor", f.get("vendor_id")) if f.get("vendor_id") is not None else None
    if v:
        out["vendor"] = comp_vendor(v)
    out["extra"] = f.get("extra") or {}
    return out


def _comp_spool(c, s):
    f = comp_filament(c, need(c, "filament", s.get("filament_id"), "filament"))
    iw, uw = s.get("initial_weight"), s.get("used_weight") or 0
    base = iw if iw is not None else f.get("weight")
    rem = max(base - uw, 0) if base is not None else None
    return {"id": s["id"], "registered": s.get("registered"), "first_used": s.get("first_used"), "last_used": s.get("last_used"), "filament": f, "price": s.get("price"), "remaining_weight": rem, "initial_weight": iw, "spool_weight": s.get("spool_weight"), "used_weight": uw, "remaining_length": length(rem, f), "used_length": length(uw, f), "location": s.get("location"), "lot_nr": s.get("lot_nr"), "comment": s.get("comment"), "archived": bool(s.get("archived")), "extra": s.get("extra") or {}}


def nn(d):
    return {k: v for k, v in d.items() if v is not None}


def comp_vendor(v):
    return nn(_comp_vendor(v))


def comp_spool(c, s):
    r = nn(_comp_spool(c, s))
    r["tags"] = s.get("tags") or []
    return r


def apply(d, b, keys):
    for k in keys:
        if k in b:
            d[k] = b[k]
    if isinstance(b.get("extra"), dict):
        d["extra"] = {**(d.get("extra") or {}), **b["extra"]}


def getk(o, key):
    for p in key.split("."):
        o = o.get(p) if isinstance(o, dict) else None
    return o


def csv(v):
    return [x.strip().lower() for x in v.split(",")]


def match(val, lst, exact=False):
    v = "" if val is None else str(val).lower()
    return any((v == "") if t == "" else ((v == t) if exact else (t in v)) for t in lst)


def page(items, q):
    total = len(items)
    for part in reversed((q.get("sort") or "id:asc").split(",")):
        k, _, d = part.partition(":")
        def sk(x, k=k):
            v = getk(x, k)
            return (v is None, v.lower() if isinstance(v, str) else (v or 0))
        items.sort(key=sk, reverse=(d.lower() == "desc"))
    off = int(q.get("offset") or 0)
    lim = q.get("limit")
    items = items[off:off + int(lim)] if lim not in (None, "") else items[off:]
    return JSONResponse(items, headers={"X-Total-Count": str(total), "Access-Control-Expose-Headers": "X-Total-Count"})


def filt(items, q, pairs):
    for p, path in pairs:
        if p in q:
            lst = csv(q[p])
            items = [x for x in items if match(getk(x, path), lst, path.endswith("id"))]
    return items


OK = {"message": "Success!"}


# ---------- Vendor ----------
@router.get("/vendor")
def vendor_list(request: Request):
    q = dict(request.query_params)
    with db() as c:
        items = [comp_vendor(v) for v in all_(c, "vendor")]
    return page(filt(items, q, [("name", "name"), ("external_id", "external_id")]), q)


@router.get("/vendor/{vid}")
def vendor_get(vid: int):
    with db() as c:
        return comp_vendor(need(c, "vendor", vid, "vendor"))


@router.post("/vendor")
async def vendor_create(req: Request):
    b = await req.json()
    if not b.get("name"):
        err(422, "name is required")
    with _lock, db() as c:
        d = {"id": next_id(c, "vendor"), "registered": now(), "extra": {}}
        apply(d, b, VKEYS)
        save(c, "vendor", d)
        return comp_vendor(d)


@router.patch("/vendor/{vid}")
async def vendor_patch(vid: int, req: Request):
    b = await req.json()
    with _lock, db() as c:
        d = need(c, "vendor", vid, "vendor")
        apply(d, b, VKEYS)
        save(c, "vendor", d)
        return comp_vendor(d)


@router.delete("/vendor/{vid}")
def vendor_delete(vid: int):
    with _lock, db() as c:
        need(c, "vendor", vid, "vendor")
        for f in all_(c, "filament"):
            if f.get("vendor_id") == vid:
                f["vendor_id"] = None
                save(c, "filament", f)
        c.execute("DELETE FROM sm_doc WHERE kind='vendor' AND id=?", (vid,))
    return OK


# ---------- Filament ----------
@router.get("/filament")
def filament_list(request: Request):
    q = dict(request.query_params)
    with db() as c:
        items = [comp_filament(c, f) for f in all_(c, "filament")]
    items = filt(items, q, [("name", "name"), ("material", "material"), ("vendor_name", "vendor.name"), ("vendor.name", "vendor.name"), ("vendor_id", "vendor.id"), ("vendor.id", "vendor.id"), ("article_number", "article_number"), ("external_id", "external_id")])
    return page(items, q)


@router.get("/filament/{fid}")
def filament_get(fid: int):
    with db() as c:
        return comp_filament(c, need(c, "filament", fid, "filament"))


@router.post("/filament")
async def filament_create(req: Request):
    b = await req.json()
    with _lock, db() as c:
        if b.get("vendor_id") is not None:
            need(c, "vendor", b["vendor_id"], "vendor")
        d = {"id": next_id(c, "filament"), "registered": now(), "vendor_id": b.get("vendor_id"), "extra": {}}
        apply(d, b, FKEYS)
        save(c, "filament", d)
        return comp_filament(c, d)


@router.patch("/filament/{fid}")
async def filament_patch(fid: int, req: Request):
    b = await req.json()
    with _lock, db() as c:
        d = need(c, "filament", fid, "filament")
        if "vendor_id" in b:
            if b["vendor_id"] is not None:
                need(c, "vendor", b["vendor_id"], "vendor")
            d["vendor_id"] = b["vendor_id"]
        apply(d, b, FKEYS)
        save(c, "filament", d)
        return comp_filament(c, d)


@router.delete("/filament/{fid}")
def filament_delete(fid: int):
    with _lock, db() as c:
        need(c, "filament", fid, "filament")
        if any(s.get("filament_id") == fid for s in all_(c, "spool")):
            err(403, "Failed to delete filament, see server logs for more information.")
        c.execute("DELETE FROM sm_doc WHERE kind='filament' AND id=?", (fid,))
    return OK


# ---------- Spool ----------
@router.get("/spool")
def spool_list(request: Request):
    q = dict(request.query_params)
    with db() as c:
        items = [comp_spool(c, s) for s in all_(c, "spool")]
    if str(q.get("allow_archived", "")).lower() not in ("1", "true", "yes"):
        items = [s for s in items if not s.get("archived")]
    items = filt(items, q, [("filament_name", "filament.name"), ("filament.name", "filament.name"), ("filament_material", "filament.material"), ("filament.material", "filament.material"), ("vendor_name", "filament.vendor.name"), ("filament.vendor.name", "filament.vendor.name"), ("filament_id", "filament.id"), ("filament.id", "filament.id"), ("vendor_id", "filament.vendor.id"), ("filament.vendor.id", "filament.vendor.id"), ("location", "location"), ("lot_nr", "lot_nr")])
    return page(items, q)


@router.get("/spool/{sid}")
def spool_get(sid: int):
    with db() as c:
        return comp_spool(c, need(c, "spool", sid, "spool"))


def spool_apply(c, d, b):
    apply(d, b, SKEYS)
    if b.get("remaining_weight") is not None:
        f = need(c, "filament", d.get("filament_id"), "filament")
        iw = d.get("initial_weight") if d.get("initial_weight") is not None else f.get("weight")
        if iw is None:
            err(400, "Cannot set remaining_weight without initial_weight or filament weight.")
        d["used_weight"] = max(iw - float(b["remaining_weight"]), 0)
    if d.get("used_weight") is None:
        d["used_weight"] = 0


@router.post("/spool")
async def spool_create(req: Request):
    b = await req.json()
    with _lock, db() as c:
        fl = need(c, "filament", b.get("filament_id"), "filament")
        d = {"id": next_id(c, "spool"), "registered": now(), "filament_id": b["filament_id"], "archived": False, "extra": {}}
        if fl.get("weight") is not None:
            d["initial_weight"] = fl["weight"]
        if fl.get("spool_weight") is not None:
            d["spool_weight"] = fl["spool_weight"]
        spool_apply(c, d, b)
        save(c, "spool", d)
        return comp_spool(c, d)


@router.patch("/spool/{sid}")
async def spool_patch(sid: int, req: Request):
    b = await req.json()
    with _lock, db() as c:
        d = need(c, "spool", sid, "spool")
        if b.get("filament_id") is not None:
            need(c, "filament", b["filament_id"], "filament")
            d["filament_id"] = b["filament_id"]
        spool_apply(c, d, b)
        save(c, "spool", d)
        return comp_spool(c, d)


@router.delete("/spool/{sid}")
def spool_delete(sid: int):
    with _lock, db() as c:
        need(c, "spool", sid, "spool")
        c.execute("DELETE FROM sm_doc WHERE kind='spool' AND id=?", (sid,))
    return OK


@router.put("/spool/{sid}/use")
async def spool_use(sid: int, req: Request):
    b = await req.json()
    with _lock, db() as c:
        d = need(c, "spool", sid, "spool")
        f = need(c, "filament", d.get("filament_id"), "filament")
        if b.get("use_weight") is not None:
            w = float(b["use_weight"])
        elif b.get("use_length") is not None:
            dm, dn = f.get("diameter"), f.get("density")
            if not dm or not dn:
                err(400, "Filament diameter/density missing, cannot use length.")
            w = float(b["use_length"]) * math.pi * (dm / 2) ** 2 / 1000 * dn
        else:
            err(400, "Either use_weight or use_length is required.")
        d["used_weight"] = (d.get("used_weight") or 0) + w
        d["last_used"] = now()
        if not d.get("first_used"):
            d["first_used"] = d["last_used"]
        save(c, "spool", d)
        return comp_spool(c, d)


@router.put("/spool/{sid}/measure")
async def spool_measure(sid: int, req: Request):
    b = await req.json()
    with _lock, db() as c:
        d = need(c, "spool", sid, "spool")
        f = need(c, "filament", d.get("filament_id"), "filament")
        sw = d.get("spool_weight") if d.get("spool_weight") is not None else f.get("spool_weight")
        iw = d.get("initial_weight") if d.get("initial_weight") is not None else f.get("weight")
        if sw is None or iw is None:
            err(400, "Spool weight and initial weight needed.")
        d["used_weight"] = max(iw - max(float(b["weight"]) - sw, 0), 0)
        d["last_used"] = now()
        if not d.get("first_used"):
            d["first_used"] = d["last_used"]
        save(c, "spool", d)
        return comp_spool(c, d)


# ---------- Extra-Felder ----------
def fields_of(c, entity):
    fs = [json.loads(r[0]) for r in c.execute("SELECT data FROM sm_field WHERE entity=?", (entity,))]
    return sorted(fs, key=lambda x: (x.get("order") or 0, x.get("key") or ""))


@router.get("/field/{entity}")
def field_list(entity: str):
    with db() as c:
        return fields_of(c, entity)


@router.post("/field/{entity}/{key}")
async def field_set(entity: str, key: str, req: Request):
    b = await req.json()
    with _lock, db() as c:
        d = {**b, "key": key, "entity_type": entity}
        c.execute("INSERT OR REPLACE INTO sm_field VALUES(?,?,?)", (entity, key, json.dumps(d, ensure_ascii=False)))
        return fields_of(c, entity)


@router.delete("/field/{entity}/{key}")
def field_delete(entity: str, key: str):
    with _lock, db() as c:
        c.execute("DELETE FROM sm_field WHERE entity=? AND key=?", (entity, key))
        return fields_of(c, entity)


# ---------- Settings / Info ----------
@router.get("/setting/")
def setting_all():
    with db() as c:
        return {k: json.loads(v) for k, v in c.execute("SELECT key,value FROM sm_setting WHERE key NOT LIKE '!_%' ESCAPE '!'")}


@router.get("/setting/{key}")
def setting_get(key: str):
    with db() as c:
        r = c.execute("SELECT value FROM sm_setting WHERE key=?", (key,)).fetchone()
    if not r:
        err(404, "Setting %s not found." % key)
    return json.loads(r[0])


@router.post("/setting/{key}")
async def setting_set(key: str, req: Request):
    v = await req.json()
    with _lock, db() as c:
        o = {"value": v if isinstance(v, str) else json.dumps(v), "is_set": True, "type": "string"}
        c.execute("INSERT OR REPLACE INTO sm_setting VALUES(?,?)", (key, json.dumps(o)))
        return o


@router.get("/info")
def info():
    return {"version": "filastorage-1.0", "debug_mode": False, "automatic_backups": False, "data_dir": os.path.dirname(DB), "backups_dir": "", "db_type": "sqlite", "git_commit": None, "build_date": None}


@router.get("/health")
def health():
    return {"status": "healthy"}


# ---------- Externe Filament-DB (SpoolmanDB, MIT) ----------
_ext = {"items": []}


def ext_load():
    try:
        with open(EXT_CACHE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            _ext["items"] = data
    except Exception:
        pass


def ext_valid(data, old_n):
    if not isinstance(data, list) or len(data) < 100:
        return "zu wenige Eintraege"
    if old_n and len(data) < old_n * 0.8:
        return "Liste deutlich kleiner als bisher"
    bad = sum(1 for e in data if not (isinstance(e, dict) and e.get("manufacturer") and e.get("name") and e.get("material") and (e.get("color_hex") or e.get("color_hexes"))))
    if bad > len(data) * 0.02:
        return "%d defekte Eintraege" % bad
    return None


async def ext_sync():
    import httpx
    st = {"checked_at": now(), "url": EXT_URL}
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as h:
            r = await h.get(EXT_URL)
            r.raise_for_status()
            data = r.json()
        bad = ext_valid(data, len(_ext["items"]))
        if bad:
            st.update(ok=False, error=bad)
        else:
            tmp = EXT_CACHE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, EXT_CACHE)
            _ext["items"] = data
            st.update(ok=True, count=len(data), fetched_at=now())
    except Exception as e:
        st.update(ok=False, error=str(e)[:200])
    with db() as c:
        old = c.execute("SELECT value FROM sm_setting WHERE key='_ext_status'").fetchone()
        if not st.get("ok") and old:
            st["last_ok"] = json.loads(old[0]).get("fetched_at") or json.loads(old[0]).get("last_ok")
        c.execute("INSERT OR REPLACE INTO sm_setting VALUES('_ext_status',?)", (json.dumps(st),))
    return st


async def ext_loop():
    ext_load()
    while True:
        try:
            age = time.time() - os.path.getmtime(EXT_CACHE) if os.path.exists(EXT_CACHE) else 1e9
            if age >= EXT_EVERY:
                await ext_sync()
        except Exception:
            pass
        await asyncio.sleep(3600)


def ext_items():
    with db() as c:
        custom = [json.loads(r[0]) for r in c.execute("SELECT data FROM sm_ext_custom")]
    return _ext["items"] + custom


@router.get("/external/filament")
def ext_list():
    return ext_items()


@router.get("/external/filament/search")
def ext_search(query: str = "", limit: int = 20):
    toks = query.lower().split()
    out = []
    for e in ext_items():
        hay = " ".join(str(e.get(k) or "") for k in ("manufacturer", "name", "material", "finish")).lower()
        if all(t in hay for t in toks):
            out.append(e)
            if len(out) >= limit:
                break
    return out


@router.get("/external/status")
def ext_status():
    with db() as c:
        r = c.execute("SELECT value FROM sm_setting WHERE key='_ext_status'").fetchone()
    return {"count": len(_ext["items"]), "sync": json.loads(r[0]) if r else None, "source": "SpoolmanDB (MIT) https://github.com/Donkie/SpoolmanDB"}


@router.post("/external/sync")
async def ext_sync_now():
    return await ext_sync()


@router.post("/external/custom")
async def ext_custom_add(req: Request):
    b = await req.json()
    with _lock, db() as c:
        n = c.execute("SELECT COUNT(*) FROM sm_ext_custom").fetchone()[0] + 1
        while c.execute("SELECT 1 FROM sm_ext_custom WHERE id=?", ("custom-%d" % n,)).fetchone():
            n += 1
        b["id"] = "custom-%d" % n
        c.execute("INSERT INTO sm_ext_custom VALUES(?,?)", (b["id"], json.dumps(b, ensure_ascii=False)))
    return b


@router.delete("/external/custom/{cid}")
def ext_custom_del(cid: str):
    with _lock, db() as c:
        c.execute("DELETE FROM sm_ext_custom WHERE id=?", (cid,))
    return OK


# ---------- Import / Setup ----------
def import_dir(d):
    init()
    L = lambda n: json.load(open(os.path.join(d, n), encoding="utf-8"))
    vendors, filaments, spools = L("vendor.json"), L("filament.json"), L("spool_allow_archived_true.json")
    with _lock, db() as c:
        c.execute("DELETE FROM sm_doc")
        c.execute("DELETE FROM sm_field")
        c.execute("DELETE FROM sm_setting WHERE key NOT LIKE '!_%' ESCAPE '!'")
        for v in vendors:
            save(c, "vendor", {"id": v["id"], "registered": v.get("registered"), "extra": v.get("extra") or {}, **{k: v.get(k) for k in VKEYS}})
        for f in filaments:
            save(c, "filament", {"id": f["id"], "registered": f.get("registered"), "vendor_id": (f.get("vendor") or {}).get("id"), "extra": f.get("extra") or {}, **{k: f.get(k) for k in FKEYS}})
        for s in spools:
            save(c, "spool", {"id": s["id"], "registered": s.get("registered"), "filament_id": s["filament"]["id"], "extra": s.get("extra") or {}, **{k: s.get(k) for k in SKEYS}})
        for ent in ("spool", "filament", "vendor"):
            fn = os.path.join(d, "field_%s.json" % ent)
            if os.path.exists(fn):
                for fd in json.load(open(fn, encoding="utf-8")):
                    c.execute("INSERT OR REPLACE INTO sm_field VALUES(?,?,?)", (ent, fd["key"], json.dumps(fd, ensure_ascii=False)))
        fn = os.path.join(d, "setting_.json")
        if os.path.exists(fn):
            for k, v in json.load(open(fn, encoding="utf-8")).items():
                c.execute("INSERT OR REPLACE INTO sm_setting VALUES(?,?)", (k, json.dumps(v)))
        for kind in ("vendor", "filament", "spool"):
            m = c.execute("SELECT MAX(id) FROM sm_doc WHERE kind=?", (kind,)).fetchone()[0] or 0
            c.execute("INSERT OR REPLACE INTO sm_setting VALUES(?,?)", ("_seq_" + kind, str(m)))
    return {"vendor": len(vendors), "filament": len(filaments), "spool": len(spools)}


def setup(app, start_sync=True):
    init()
    ext_load()

    async def _h(request, exc):
        return JSONResponse({"message": exc.msg}, status_code=exc.status)
    app.add_exception_handler(SmErr, _h)
    app.include_router(router, prefix="/spoolman-v1")
    if start_sync:
        async def _start():
            asyncio.ensure_future(ext_loop())
        app.add_event_handler("startup", _start)


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "import":
    print(import_dir(sys.argv[2]))
