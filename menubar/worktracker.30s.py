#!/usr/bin/python3
# <xbar.title>Work Tracker</xbar.title>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
"""SwiftBar plugin: timer in the menu bar, Start/Stop from the menu. Refreshes every 30s (the bar shows minutes)."""
import json
import os
import subprocess
import sys
import urllib.request

URL = "http://localhost:47474"
ME = os.path.abspath(__file__)


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as r:
        return json.load(r)


def dur(sec, sign=False):
    s = "+" if sec > 0 else "−" if sec < 0 else "±"
    sec = abs(int(sec))
    return (s if sign else "") + "%dh %02dm" % (sec // 3600, sec % 3600 // 60)


def ask_note():
    script = ('text returned of (display dialog "What are you working on?" default answer "" '
              'with title "Work Tracker" buttons {"Cancel", "Start"} default button "Start")')
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return None if r.returncode else r.stdout.strip()


# ---- menu actions (SwiftBar calls this script with an argument)
if len(sys.argv) > 1:
    if sys.argv[1] == "start":
        api("POST", "/api/start", {"note": ""})
    elif sys.argv[1] == "start-note":
        note = ask_note()
        if note is not None:
            api("POST", "/api/start", {"note": note})
    elif sys.argv[1] == "stop":
        api("POST", "/api/stop")
    sys.exit()

# ---- menu
try:
    s = api("GET", "/api/status")
except OSError:
    print("– | sfimage=exclamationmark.triangle")
    print("---")
    print("Work Tracker server is not running")
    sys.exit()

run = s["running"]
if run:
    t = run["seconds"]
    print("%d:%02d | sfimage=timer" % (t // 3600, t % 3600 // 60))
else:
    print("| sfimage=timer")
print("---")
if run:
    print("Running since %s%s" % (run["start_time"][11:16], " · " + run["note"] if run["note"] else ""))
    print("Stop | bash=%s param1=stop terminal=false refresh=true sfimage=stop.fill" % ME)
else:
    print("Start | bash=%s param1=start terminal=false refresh=true sfimage=play.fill" % ME)
    print("Start with note… | bash=%s param1=start-note terminal=false refresh=true sfimage=square.and.pencil" % ME)
print("---")
print("Today: %s / %s" % (dur(s["today_seconds"]), dur(s["daily_target"])))
print("Week: %s / %s" % (dur(s["week_seconds"]), dur(s["weekly_target"])))
print("Overtime incl. today: %s" % dur(s["balance_seconds"] + s["today_seconds"] - s["daily_target"], sign=True))
print("---")
print("Open tracker | href=%s sfimage=safari" % URL)
