#!/usr/bin/env bash
# Start (or restart) the action server and the Rasa server for local testing.
#   scripts/serve.sh start | stop | status
# PIDs are tracked in .run/ so stopping never relies on pattern-matching
# process names — a pkill for "rasa run" also matches the shell that issued it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/.run"
RASA_BIN="${RASA_BIN:-rasa}"
mkdir -p "$RUN_DIR"

stop_one() {
  local name="$1" pidfile="$RUN_DIR/$1.pid"
  [[ -f "$pidfile" ]] || return 0
  local pid; pid="$(cat "$pidfile")"
  if kill -0 "$pid" 2>/dev/null; then kill "$pid" 2>/dev/null || true; sleep 1; kill -9 "$pid" 2>/dev/null || true; fi
  rm -f "$pidfile"
  echo "stopped $name"
}

case "${1:-start}" in
  stop)
    stop_one rasa; stop_one actions ;;
  status)
    curl -sf --max-time 5 http://localhost:5055/health && echo " actions OK" || echo "actions DOWN"
    curl -sf --max-time 5 http://localhost:5005/status >/dev/null && echo "rasa OK" || echo "rasa DOWN" ;;
  start)
    stop_one rasa; stop_one actions
    cd "$ROOT"
    nohup "$RASA_BIN" run actions --actions actions.actions --port 5055 > "$RUN_DIR/actions.log" 2>&1 &
    echo $! > "$RUN_DIR/actions.pid"
    sleep 8
    nohup "$RASA_BIN" run --enable-api --cors "*" --port 5005 \
      --model models/eco_travel_advisor.tar.gz > "$RUN_DIR/rasa.log" 2>&1 &
    echo $! > "$RUN_DIR/rasa.pid"
    echo "starting; the Rasa server takes ~60 s to load spaCy and the model"
    for _ in $(seq 1 40); do
      if curl -sf --max-time 3 http://localhost:5005/status >/dev/null 2>&1; then echo "both servers up"; exit 0; fi
      sleep 5
    done
    echo "rasa did not come up; see $RUN_DIR/rasa.log" >&2; exit 1 ;;
  *)
    echo "usage: $0 {start|stop|status}" >&2; exit 2 ;;
esac
