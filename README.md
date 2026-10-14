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
- **Away tracking (macOS)** – the same watcher records when you were away (Mac asleep, screen locked,
  display off / lid closed), from your last keyboard/trackpad input until you're back. The day view
  lists them under each session's **Timeline & break** (click to expand; green = in use, grey = away).
  Click any time on the timeline (grey parts snap to when you left / came back) or in the away list
  to use it as **start**, **end**, **break from** or **break until** — e.g. forgot to stop the timer?
  Click where the lid was closed → *Set as end* → *Save & stop*. Edit also works on the running
  timer (empty End keeps it running). Only kept for the last 3 sessions (a few rows).
- **Breaks** – under **Timeline & break**, add a break (e.g. lunch 12:00–12:45): the session is split
  in two, so the break doesn't count as work time; the gap shows as *Break* in the day view.

Targets are set at the top of `app.py` (`DAILY_TARGET`, `WEEKLY_TARGET`, `WORKDAYS`).

## Menu bar (macOS)

`menubar/worktracker.30s.py` is a [SwiftBar](https://swiftbar.app) plugin: running time in the
menu bar, Start / Start with note… / Stop, and today's stats (refreshes every 30s).

Requirements: SwiftBar (`brew install --cask swiftbar`) and macOS's `/usr/bin/python3`, which comes with
the Xcode Command Line Tools (`xcode-select --install`). The tracker server must be running.

Setup: start SwiftBar, choose the `menubar` folder as plugin folder, and turn on *Launch at Login* in
SwiftBar's preferences. The plugin talks to `http://localhost:47474`; edit `URL` at the top of the
script if you run the server on another port.
