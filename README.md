# Tracker

A personal work-time tracker: start/stop a timer, see how much you've worked today and this
week against an 8h/day, 40h/week target, and browse your history in a GitHub-style heatmap.

Backend: Python + Flask, data stored in SQLite (`tracker.db`, created automatically).

## Run

Requires Python 3.9+.

```powershell
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:47474> (override with `PORT=...`).

**Start at login (macOS):** run `./autostart.sh` (needs `python3` on your PATH). It creates `.venv`,
installs `requirements.txt` and adds a LaunchAgent (`~/Library/LaunchAgents/com.worktracker.plist`)
that starts the server at login and restarts it if it stops; output goes to `tracker.log`. It always
uses port 47474. Undo with `./autostart.sh remove`.

## Features

- **Timer** – Start/Stop with a note of what you're working on; the note stays editable while the
  timer runs (Enter or click away to save). Only one session runs at a time; it keeps
  running even if you close the browser.
- **Today / This week** – worked vs. target, time remaining, and the time you'll be done today.
- **Overtime balance** – total worked vs. 8h per workday (Mon–Fri) for all days before today.
- **Overtime incl. today** – the same balance with today counted so far ("if you stopped now").
- **Activity heatmap** – last 12 months or any year; darker = more hours. Click a day to see it.
- **Day view** – list, add, edit or delete sessions (e.g. if you forgot to start/stop the timer).
- **Come-back reminder (macOS)** – when you log in or come back (after sleep, lock or the display
  turning off, e.g. lid closed) and no timer is running, you get a notification. Click
  **Enable reminders** in the tracker once: the open tab then sends the notification and clicking
  it jumps to that tab. With no tab open you get a plain macOS notification instead. A running timer
  just keeps going. No extra installs, but macOS must allow notifications for your browser
  (System Settings → Notifications). Decisions are logged to stderr (`tracker.log` with autostart);
  disable with `WAKE_PROMPT=0`.

Targets are set at the top of `app.py` (`DAILY_TARGET`, `WEEKLY_TARGET`, `WORKDAYS`).
