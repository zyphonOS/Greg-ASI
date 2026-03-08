#!/bin/bash
# Greg Keep-Alive — restarts auto_tick if it dies
# Run once: bash keepalive.sh &

LOG=/workspaces/Greg-ASI/auto_tick.log
CMD="python -u /workspaces/Greg-ASI/auto_tick.py --save-every 100"

echo "[keepalive] Started — watching auto_tick"

while true; do
    if ! pgrep -f "auto_tick.py" > /dev/null; then
        echo "[keepalive] auto_tick not running — restarting at $(date)"
        cd /workspaces/Greg-ASI
        $CMD >> $LOG 2>&1 &
        echo "[keepalive] Restarted PID: $!"
    fi
    sleep 60
done
