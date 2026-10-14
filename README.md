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

- **Timer** – Start/Stop with a note of what you're working on; the note stays editable while the
  timer runs (Enter or click away to save). Only one session runs at a time; it keeps
  running even if you close the browser.
- **Today / This week** – worked vs. target, time remaining, and the time you'll be done today.
- **Overtime balance** – total worked vs. 8h per workday (Mon–Fri) for all days before today.
- **Overtime incl. today** – the same balance with today counted so far ("if you stopped now").
- **Activity heatmap** – last 12 months or any year; darker = more hours. Click a day to see it.
- **Day view** – list, add, edit or delete sessions (e.g. if you forgot to start/stop the timer).

Targets are set at the top of `app.py` (`DAILY_TARGET`, `WEEKLY_TARGET`, `WORKDAYS`).
