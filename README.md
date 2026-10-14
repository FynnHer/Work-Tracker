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

Targets are set at the top of `app.py` (`DAILY_TARGET`, `WEEKLY_TARGET`, `WORKDAYS`).

## Menu bar (macOS)

`menubar/worktracker.30s.py` is a [SwiftBar](https://swiftbar.app) plugin: running time in the
menu bar, Start / Start with note… / Stop, and today's stats (refreshes every 30s).

Requirements: SwiftBar (`brew install --cask swiftbar`) and macOS's `/usr/bin/python3`, which comes with
the Xcode Command Line Tools (`xcode-select --install`). The tracker server must be running.

Setup: start SwiftBar, choose the `menubar` folder as plugin folder, and turn on *Launch at Login* in
SwiftBar's preferences. The plugin talks to `http://localhost:47474`; edit `URL` at the top of the
script if you run the server on another port.
