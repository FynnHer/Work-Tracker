"""Work Tracker — Flask + SQLite backend.

Run:  python app.py   then open http://localhost:47474
"""
import os
import sqlite3
import subprocess
import sys
import threading
import time as clock
from datetime import date, datetime, time, timedelta

from flask import Flask, g, jsonify, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("TRACKER_DB", os.path.join(BASE_DIR, "tracker.db"))

DAILY_TARGET = 8 * 3600       # seconds per workday
WEEKLY_TARGET = 40 * 3600     # seconds per week
WORKDAYS = {0, 1, 2, 3, 4}    # Monday..Friday

app = Flask(__name__, static_folder="static", static_url_path="")


# ---------------------------------------------------------------- database

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time  TEXT NOT NULL,          -- local time, ISO 8601
                end_time    TEXT,                   -- NULL while the timer runs
                note        TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_time);
            -- Times the Mac was asleep / locked / display off (only kept for recent sessions).
            CREATE TABLE IF NOT EXISTS away (
                start_time  TEXT NOT NULL,          -- last keyboard/trackpad input before leaving
                end_time    TEXT NOT NULL,          -- when you were back
                reason      TEXT NOT NULL           -- sleep | lock | display-off
            );
            """
        )


# ---------------------------------------------------------------- helpers

def fmt(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat(timespec="seconds")


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def parse_day(value: str) -> date:
    return date.fromisoformat(value)


def session_dict(row) -> dict:
    start = parse(row["start_time"])
    end = parse(row["end_time"]) if row["end_time"] else None
    return {
        "id": row["id"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "note": row["note"],
        "running": end is None,
        "seconds": int(((end or datetime.now()) - start).total_seconds()),
    }


def daily_totals(first: date, last: date) -> dict:
    """Seconds worked per day (YYYY-MM-DD -> int) in [first, last].

    Sessions spanning midnight are split across the days they cover.
    """
    lo = datetime.combine(first, time.min)
    hi = datetime.combine(last + timedelta(days=1), time.min)
    rows = get_db().execute(
        "SELECT start_time, end_time FROM sessions "
        "WHERE start_time < ? AND (end_time IS NULL OR end_time > ?)",
        (fmt(hi), fmt(lo)),
    ).fetchall()

    now = datetime.now()
    totals: dict = {}
    for r in rows:
        s = max(parse(r["start_time"]), lo)
        e = min(parse(r["end_time"]) if r["end_time"] else now, hi)
        while s < e:
            chunk_end = min(e, datetime.combine(s.date() + timedelta(days=1), time.min))
            key = s.date().isoformat()
            totals[key] = totals.get(key, 0) + int((chunk_end - s).total_seconds())
            s = chunk_end
    return totals


def expected_seconds(first: date, last: date) -> int:
    """Target seconds for all workdays in [first, last]."""
    if last < first:
        return 0
    days = (last - first).days + 1
    workdays = sum(1 for i in range(days) if (first + timedelta(days=i)).weekday() in WORKDAYS)
    return workdays * DAILY_TARGET


def running_session():
    return get_db().execute(
        "SELECT * FROM sessions WHERE end_time IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()


def bad_request(msg: str):
    return jsonify({"error": msg}), 400


# ---------------------------------------------------------------- pages

@app.get("/")
def index():
    return app.send_static_file("index.html")


# ---------------------------------------------------------------- API

@app.get("/api/status")
def status():
    global tab_seen_at
    if request.args.get("notify"):
        tab_seen_at = clock.time()
    db = get_db()
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    week = daily_totals(monday, monday + timedelta(days=6))
    today_s = week.get(today.isoformat(), 0)
    week_s = sum(week.values())
    today_target = DAILY_TARGET if today.weekday() in WORKDAYS else 0

    # Overtime balance: everything worked before today vs. target before today.
    first_row = db.execute("SELECT MIN(start_time) FROM sessions").fetchone()[0]
    balance = 0
    first_year = today.year
    if first_row:
        first_day = parse(first_row).date()
        first_year = first_day.year
        yesterday = today - timedelta(days=1)
        if first_day <= yesterday:
            worked = sum(daily_totals(first_day, yesterday).values())
            balance = worked - expected_seconds(first_day, yesterday)

    run = running_session()
    return jsonify({
        "now": fmt(datetime.now()),
        "today": today.isoformat(),
        "daily_target": today_target,
        "weekly_target": WEEKLY_TARGET,
        "today_seconds": today_s,
        "week_seconds": week_s,
        "today_remaining": max(0, today_target - today_s),
        "week_remaining": max(0, WEEKLY_TARGET - week_s),
        "balance_seconds": balance,
        "first_year": first_year,
        "week_days": [
            {
                "date": (monday + timedelta(days=i)).isoformat(),
                "seconds": week.get((monday + timedelta(days=i)).isoformat(), 0),
                "target": DAILY_TARGET if i in WORKDAYS else 0,
            }
            for i in range(7)
        ],
        "running": session_dict(run) if run else None,
        "last_reminder": last_reminder,
    })


@app.post("/api/start")
def start():
    db = get_db()
    if running_session():
        return bad_request("Timer is already running.")
    note = (request.get_json(silent=True) or {}).get("note", "").strip()
    db.execute("INSERT INTO sessions (start_time, note) VALUES (?, ?)", (fmt(datetime.now()), note))
    db.commit()
    return jsonify(session_dict(running_session()))


@app.post("/api/stop")
def stop():
    db = get_db()
    run = running_session()
    if not run:
        return bad_request("Timer is not running.")
    db.execute("UPDATE sessions SET end_time = ? WHERE id = ?", (fmt(datetime.now()), run["id"]))
    db.commit()
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (run["id"],)).fetchone()
    return jsonify(session_dict(row))


@app.get("/api/days")
def days():
    """Per-day totals for the heatmap: /api/days?from=YYYY-MM-DD&to=YYYY-MM-DD"""
    try:
        first = parse_day(request.args["from"])
        last = parse_day(request.args["to"])
    except (KeyError, ValueError):
        return bad_request("Use ?from=YYYY-MM-DD&to=YYYY-MM-DD")
    if (last - first).days > 800:
        return bad_request("Range too large.")
    return jsonify(daily_totals(first, last))


@app.get("/api/sessions")
def list_sessions():
    """Sessions overlapping a given day: /api/sessions?date=YYYY-MM-DD"""
    try:
        day = parse_day(request.args["date"])
    except (KeyError, ValueError):
        return bad_request("Use ?date=YYYY-MM-DD")
    lo = fmt(datetime.combine(day, time.min))
    hi = fmt(datetime.combine(day + timedelta(days=1), time.min))
    rows = get_db().execute(
        "SELECT * FROM sessions WHERE start_time < ? AND (end_time IS NULL OR end_time > ?) "
        "ORDER BY start_time",
        (hi, lo),
    ).fetchall()
    db = get_db()
    out = []
    for r in rows:
        s = session_dict(r)
        s["away"] = [dict(a) for a in db.execute(
            "SELECT start_time, end_time, reason FROM away WHERE start_time < ? AND end_time > ? "
            "ORDER BY start_time",
            (r["end_time"] or fmt(datetime.now()), r["start_time"]),
        )]
        out.append(s)
    return jsonify(out)


def read_session_body(end_optional=False):
    """(start, end, note) from the JSON body; with end_optional an empty end_time gives end None."""
    data = request.get_json(silent=True) or {}
    try:
        start_dt = parse(data["start_time"])
        end_dt = None if end_optional and not data.get("end_time") else parse(data["end_time"])
    except (KeyError, TypeError, ValueError):
        return None, bad_request("start_time and end_time are required (YYYY-MM-DDTHH:MM).")
    if end_dt is None:
        if start_dt > datetime.now():
            return None, bad_request("Start cannot be in the future.")
        return (fmt(start_dt), None, str(data.get("note", "")).strip()), None
    if end_dt <= start_dt:
        return None, bad_request("End must be after start.")
    if end_dt > datetime.now() + timedelta(minutes=1):
        return None, bad_request("End cannot be in the future.")
    return (fmt(start_dt), fmt(end_dt), str(data.get("note", "")).strip()), None


@app.post("/api/sessions")
def add_session():
    values, err = read_session_body()
    if err:
        return err
    db = get_db()
    cur = db.execute("INSERT INTO sessions (start_time, end_time, note) VALUES (?, ?, ?)", values)
    db.commit()
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(session_dict(row)), 201


@app.put("/api/sessions/<int:sid>")
def edit_session(sid):
    """Edit a session; on the running one, an empty end_time keeps it running (otherwise it stops)."""
    values, err = read_session_body(end_optional=True)
    if err:
        return err
    db = get_db()
    if values[1] is None:
        cur = db.execute(
            "UPDATE sessions SET start_time = ?, note = ? WHERE id = ? AND end_time IS NULL",
            (values[0], values[2], sid),
        )
    else:
        cur = db.execute(
            "UPDATE sessions SET start_time = ?, end_time = ?, note = ? WHERE id = ?", (*values, sid)
        )
    db.commit()
    if cur.rowcount == 0:
        if values[1] is None and db.execute("SELECT 1 FROM sessions WHERE id = ?", (sid,)).fetchone():
            return bad_request("End is required for a finished session.")
        return jsonify({"error": "Not found"}), 404
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    return jsonify(session_dict(row))


@app.delete("/api/sessions/<int:sid>")
def delete_session(sid):
    db = get_db()
    cur = db.execute("DELETE FROM sessions WHERE id = ?", (sid,))
    db.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Not found"}), 404
    return "", 204


@app.post("/api/sessions/<int:sid>/break")
def add_break(sid):
    """Cut a break (e.g. lunch) out of a session: it becomes two sessions, before and after."""
    data = request.get_json(silent=True) or {}
    try:
        b0, b1 = parse(data["start_time"]), parse(data["end_time"])
    except (KeyError, TypeError, ValueError):
        return bad_request("start_time and end_time are required (YYYY-MM-DDTHH:MM).")
    db = get_db()
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    if row is None:
        return jsonify({"error": "Not found"}), 404
    end = parse(row["end_time"]) if row["end_time"] else datetime.now()
    if not parse(row["start_time"]) < b0 < b1 < end:
        return bad_request("The break must lie within the session (and be over already).")
    db.execute("UPDATE sessions SET end_time = ? WHERE id = ?", (fmt(b0), sid))
    db.execute(  # end_time NULL → the running timer continues in the second part
        "INSERT INTO sessions (start_time, end_time, note) VALUES (?, ?, ?)", (fmt(b1), row["end_time"], row["note"])
    )
    db.commit()
    return "", 204


# ---------------------------------------------------------------- wake reminder (macOS)

URL = f"http://localhost:{os.environ.get('PORT', 47474)}"
last_reminder = 0.0  # time of the last reminder; open tracker tabs show a notification when it changes
tab_seen_at = 0.0   # last /api/status poll from a tab that is allowed to notify


def log(msg):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg, file=sys.stderr, flush=True)


def remind():
    global last_reminder
    with sqlite3.connect(DB_PATH) as db:
        running = db.execute("SELECT 1 FROM sessions WHERE end_time IS NULL").fetchone()
    if running:
        log("reminder skipped: timer running")
        return
    last_reminder = clock.time()
    if clock.time() - tab_seen_at > 30:
        clock.sleep(15)  # after a wake the tab may not have polled yet
    if clock.time() - tab_seen_at <= 30:
        log("reminder → browser tab")
    else:  # no tab open → macOS notification (click opens Script Editor)
        log("reminder → no tab with notifications enabled, macOS notification")
        subprocess.run(["osascript", "-e", 'display notification "No timer running — open '
                        f'{URL} to start it." with title "Work Tracker" subtitle "Working?" sound name "Glass"'])


if sys.platform == "darwin":
    # Read the two IOKit properties directly instead of spawning `ioreg` every 10s.
    import ctypes
    import ctypes.util

    _iokit = ctypes.CDLL(ctypes.util.find_library("IOKit"))
    _cg = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))
    _cg.CGMainDisplayID.restype = ctypes.c_uint32
    _cg.CGDisplayIsAsleep.argtypes = [ctypes.c_uint32]
    _cg.CGDisplayIsAsleep.restype = ctypes.c_uint32
    _cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
    _iokit.IORegistryGetRootEntry.argtypes = [ctypes.c_uint32]
    _iokit.IORegistryGetRootEntry.restype = ctypes.c_uint32
    _iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
    _iokit.IOServiceMatching.restype = ctypes.c_void_p
    _iokit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    _iokit.IOServiceGetMatchingService.restype = ctypes.c_uint32
    _iokit.IORegistryEntryCreateCFProperty.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
    _iokit.IORegistryEntryCreateCFProperty.restype = ctypes.c_void_p
    _cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
    _cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    _cf.CFBooleanGetValue.argtypes = [ctypes.c_void_p]
    _cf.CFBooleanGetValue.restype = ctypes.c_bool
    _cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    _cf.CFRelease.argtypes = [ctypes.c_void_p]

    _ROOT = _iokit.IORegistryGetRootEntry(0)
    _HID = _iokit.IOServiceGetMatchingService(0, _iokit.IOServiceMatching(b"IOHIDSystem"))
    _LOCKED = _cf.CFStringCreateWithCString(None, b"IOConsoleLocked", 0x08000100)  # UTF-8
    _IDLE = _cf.CFStringCreateWithCString(None, b"HIDIdleTime", 0x08000100)

    def _prop(entry, key):
        return _iokit.IORegistryEntryCreateCFProperty(entry, key, None, 0)


def display_asleep() -> bool:
    """True when the lid is closed or the display went to sleep (no sleep/lock needed)."""
    return bool(_cg.CGDisplayIsAsleep(_cg.CGMainDisplayID()))


def screen_locked() -> bool:
    v = _prop(_ROOT, _LOCKED)
    if not v:
        return False
    locked = _cf.CFBooleanGetValue(v)
    _cf.CFRelease(v)
    return locked


def idle_seconds() -> float:
    """Seconds since the last keyboard/trackpad input."""
    v = _prop(_HID, _IDLE)
    if not v:
        return float("inf")
    ns = ctypes.c_int64()
    _cf.CFNumberGetValue(v, 4, ctypes.byref(ns))  # kCFNumberSInt64Type
    _cf.CFRelease(v)
    return ns.value / 1e9


def recently_active() -> bool:
    """Keyboard/trackpad used in the last minute (rules out dark wakes)."""
    return idle_seconds() < 60


def record_away(start: float, end: float, reason: str):
    """Store an away period; only periods overlapping the last 3 sessions are kept."""
    if end - start < 60:
        return
    with sqlite3.connect(DB_PATH) as db:
        db.execute("INSERT INTO away VALUES (?, ?, ?)",
                   (fmt(datetime.fromtimestamp(start)), fmt(datetime.fromtimestamp(end)), reason))
        db.execute(
            "DELETE FROM away WHERE NOT EXISTS (SELECT 1 FROM "
            "(SELECT start_time, end_time FROM sessions ORDER BY start_time DESC LIMIT 3) AS s "
            "WHERE away.start_time < COALESCE(s.end_time, '9999') AND away.end_time > s.start_time)"
        )


def wake_watcher():
    """Remind at login and whenever you come back: after sleep, lock or display off (e.g. lid closed).
    A running timer is left alone."""
    remind()
    prev = last_input = clock.time()
    pending = False
    while True:
        clock.sleep(10)
        now = clock.time()
        locked = screen_locked()
        slept = now - prev > 30  # wall clock jumped
        if not slept and not pending:
            last_input = now - idle_seconds()  # after a sleep, keep the value from before it
        # ponytail: 10s polling, so an away shorter than that can slip through
        away = "sleep" if slept else "lock" if locked else "display-off" if display_asleep() else None
        if away and not pending:
            pending, away_since, away_reason = True, last_input, away
            log("away (%s) since %s" % (away, datetime.fromtimestamp(away_since).strftime("%H:%M:%S")))
        if pending and not locked and recently_active():
            log("back")
            record_away(away_since, now, away_reason)
            remind()
            pending = False
        prev = now


init_db()

if __name__ == "__main__":
    if sys.platform == "darwin" and os.environ.get("WAKE_PROMPT", "1") == "1":
        threading.Thread(target=wake_watcher, daemon=True).start()
    app.run(host="localhost", port=int(os.environ.get("PORT", 47474)), debug=False)
