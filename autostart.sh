#!/bin/sh
# Start Work Tracker at login (macOS LaunchAgent).
#   ./autostart.sh          install + start now
#   ./autostart.sh remove   uninstall
#   SNAPSHOT_DIR=~/path ./autostart.sh   also write worktracker.html there (e.g. OneDrive, for the phone)
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL=com.worktracker
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$1" = remove ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Autostart removed."
  exit 0
fi

[ -x "$DIR/.venv/bin/python" ] || python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"

ENV=""
[ -n "$SNAPSHOT_DIR" ] && ENV="<key>EnvironmentVariables</key><dict><key>SNAPSHOT_DIR</key><string>$SNAPSHOT_DIR</string></dict>"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$DIR/.venv/bin/python</string><string>$DIR/app.py</string></array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>$DIR/tracker.log</string>
  $ENV
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Work Tracker runs at login: http://localhost:47474"
