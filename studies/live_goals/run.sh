#!/usr/bin/env bash
# Detached restart loop for the live_goals recorder (and the real-time paper trader).
#   start:  bash studies/live_goals/run.sh start
#   status: bash studies/live_goals/run.sh status
#   stop:   bash studies/live_goals/run.sh stop
# Logs: data/live_goals/recorder.log, data/live_goals/paper.log. PIDs: data/live_goals/*.pid
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
DATA="${LIVE_GOALS_DATA:-$ROOT/data/live_goals}"
mkdir -p "$DATA"

loop() {  # $1 = name, rest = command
  local name="$1"; shift
  while [ ! -f "$DATA/$name.stop" ]; do
    echo "$(date -u '+%F %T') [$name] starting: $*" >> "$DATA/$name.log"
    "$@" >> "$DATA/$name.log" 2>&1
    echo "$(date -u '+%F %T') [$name] exited with $?; restart in 10 s" >> "$DATA/$name.log"
    sleep 10
  done
  rm -f "$DATA/$name.stop" "$DATA/$name.pid"
}

start_one() {  # $1 = name, rest = command
  local name="$1"; shift
  if [ -f "$DATA/$name.pid" ] && kill -0 "$(cat "$DATA/$name.pid")" 2>/dev/null; then
    echo "$name already running (loop pid $(cat "$DATA/$name.pid"))"; return
  fi
  rm -f "$DATA/$name.stop"
  nohup setsid bash -c "$(declare -f loop); DATA='$DATA'; loop $name $*" > /dev/null 2>&1 &
  echo $! > "$DATA/$name.pid"
  echo "$name started (loop pid $!)"
}

stop_one() {
  local name="$1"
  touch "$DATA/$name.stop"
  if [ -f "$DATA/$name.pid" ]; then
    local pid; pid="$(cat "$DATA/$name.pid")"
    pkill -TERM -s "$pid" 2>/dev/null || kill "$pid" 2>/dev/null
    sleep 2
    pkill -KILL -s "$pid" 2>/dev/null
    rm -f "$DATA/$name.pid"
  fi
  echo "$name stopped"
}

case "${1:-status}" in
  start)
    start_one recorder python3 -u "$HERE/recorder.py"
    [ "${2:-}" = "--with-paper" ] && start_one paper python3 -u "$HERE/paper.py" --follow
    ;;
  start-paper) start_one paper python3 -u "$HERE/paper.py" --follow ;;
  stop) stop_one recorder; stop_one paper ;;
  stop-paper) stop_one paper ;;
  status)
    for n in recorder paper; do
      if [ -f "$DATA/$n.pid" ] && kill -0 "$(cat "$DATA/$n.pid")" 2>/dev/null; then
        echo "$n: running (loop pid $(cat "$DATA/$n.pid"))"
      else
        echo "$n: not running"
      fi
    done
    [ -f "$DATA/status.json" ] && python3 -c "import json;d=json.load(open('$DATA/status.json'));print('last status', d['utc'], 'UTC'); print('lines written', d['counts']); print('shards', {k:(v['n'],v['msgs'],v['alive']) for k,v in d['shards'].items()})"
    tail -n 3 "$DATA/recorder.log" 2>/dev/null
    ;;
esac
