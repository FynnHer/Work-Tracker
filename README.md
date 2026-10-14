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

## Features

- **Timer** – Start/Stop with an optional note. Only one session runs at a time; it keeps
  running even if you close the browser.
- **Today / This week** – worked vs. target, time remaining, and the time you'll be done today.
- **Overtime balance** – total worked vs. 8h per workday (Mon–Fri) for all days before today.
- **Activity heatmap** – last 12 months or any year; darker = more hours. Click a day to see it.
- **Day view** – list, add, edit or delete sessions (e.g. if you forgot to start/stop the timer).
- **Come-back reminder (macOS)** – when you log in or come back (after sleep, lock or the display
  turning off, e.g. lid closed) and no timer is running, you get a notification. Click
  **Enable reminders** in the tracker once: the open tab then sends the notification and clicking
  it jumps to that tab. With no tab open you get a plain macOS notification instead. A running timer
  just keeps going. No extra installs, but macOS must allow notifications for your browser
  (System Settings → Notifications). Decisions are logged to stderr (`tracker.log` with autostart);
  disable with `WAKE_PROMPT=0`.
- **Away tracking (macOS)** – the same watcher records when you were away (Mac asleep, screen locked,
  display off / lid closed), from your last keyboard/trackpad input until you're back. The day view
  shows a timeline per session (green = in use, grey = away) and lists the away periods; forgot to
  stop the timer? Click **Stop timer at …** / **End session here** on the away period to end the
  session when you left. Only kept for the last 3 sessions (a few rows).

Targets are set at the top of `app.py` (`DAILY_TARGET`, `WEEKLY_TARGET`, `WORKDAYS`).
