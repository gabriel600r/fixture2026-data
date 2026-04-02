#!/bin/bash
# World Cup 2026 live match watcher.
# Called by cron. Starts fetch_live.py --watch if not already running.
# Logs to /opt/fixture2026/watcher.log

SCRIPT_DIR="/opt/fixture2026"
PIDFILE="$SCRIPT_DIR/watcher.pid"
LOGFILE="$SCRIPT_DIR/watcher.log"

# Check if already running
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        # Already running, nothing to do
        exit 0
    else
        # Stale PID file
        rm -f "$PIDFILE"
    fi
fi

# Start watcher in background
cd "$SCRIPT_DIR"
nohup python3 fetch_live.py --watch >> "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"

echo "[$(date)] Started watcher PID $!" >> "$LOGFILE"
