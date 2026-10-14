"""Work Tracker — Flask + SQLite backend.

Run:  python app.py   then open http://localhost:47474
"""
import logging
import os
import sqlite3
from datetime import date, datetime, time, timedelta

from flask import Flask, g, jsonify, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("TRACKER_DB", os.path.join(BASE_DIR, "tracker.db"))

DAILY_TARGET = 8 * 3600       # seconds per workday
WEEKLY_TARGET = 40 * 3600     # seconds per week
WORKDAYS = {0, 1, 2, 3, 4}    # Monday..Friday

app = Flask(__name__, static_folder="static", static_url_path="")
logging.getLogger("werkzeug").setLevel(logging.WARNING)  # no per-request access log


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
    return jsonify([session_dict(r) for r in rows])


def read_session_body():
    data = request.get_json(silent=True) or {}
    try:
        start_dt = parse(data["start_time"])
        end_dt = parse(data["end_time"])
    except (KeyError, TypeError, ValueError):
        return None, bad_request("start_time and end_time are required (YYYY-MM-DDTHH:MM).")
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
    values, err = read_session_body()
    if err:
        return err
    db = get_db()
    cur = db.execute(
        "UPDATE sessions SET start_time = ?, end_time = ?, note = ? WHERE id = ?", (*values, sid)
    )
    db.commit()
    if cur.rowcount == 0:
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


init_db()

if __name__ == "__main__":
    app.run(host="localhost", port=int(os.environ.get("PORT", 47474)), debug=False)
