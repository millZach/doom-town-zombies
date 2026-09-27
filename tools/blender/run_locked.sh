#!/bin/sh
# Run ONE headless Blender job at a time across all agents on this machine (the laptop overheats).
#   sh tools/blender/run_locked.sh <script.py> [script args...]
# Waits until: no other project Blender process is running, the lock is free, CPU < 85 %,
# free RAM > 4 GB and GPU < 83 C. Then runs Blender with a 12-thread cap and releases the lock.
BL="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOCK="$ROOT/tools/blender/.blender.lock"
SCRIPT="$1"; shift

others() {
  powershell -NoProfile -Command "@(Get-Process blender -ErrorAction SilentlyContinue | Where-Object { (Get-CimInstance Win32_Process -Filter \"ProcessId=\$(\$_.Id)\").CommandLine -like '*tools/blender*' }).Count" 2>/dev/null | tr -d '\r'
}
load_ok() {
  set -- $(powershell -NoProfile -Command "\$c=(Get-CimInstance Win32_Processor).LoadPercentage; \$f=[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1); \"\$c \$f\"" 2>/dev/null | tr -d '\r')
  gpu=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d '\r')
  [ "${1:-0}" -lt 85 ] && awk "BEGIN{exit !(${2:-99} > 4)}" && [ "${gpu:-0}" -lt 83 ]
}

waited=0
while :; do
  if mkdir "$LOCK" 2>/dev/null; then
    echo $$ > "$LOCK/pid"
    if [ "$(others)" = "0" ] && load_ok; then break; fi
    rm -rf "$LOCK"
  else
    # break a stale lock: owner died, pid missing, or no Blender has run under it for 3 minutes
    owner=$(cat "$LOCK/pid" 2>/dev/null)
    if [ -z "$owner" ] || ! kill -0 "$owner" 2>/dev/null; then rm -rf "$LOCK"; continue; fi
    age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || date +%s) ))
    if [ "$age" -gt 180 ] && [ "$(others)" = "0" ]; then rm -rf "$LOCK"; continue; fi
  fi
  [ $((waited % 60)) -eq 0 ] && echo "[run_locked] waiting for Blender slot / machine load... (${waited}s)"
  sleep 10; waited=$((waited + 10))
done
trap 'rm -rf "$LOCK"' EXIT INT TERM
echo "[run_locked] running $SCRIPT (waited ${waited}s)"
"$BL" -b --factory-startup -t 12 --python "$SCRIPT" -- "$@"
rc=$?
rm -rf "$LOCK"      # release explicitly too: EXIT traps don't always fire at the head of a pipeline
echo "[run_locked] done rc=$rc"
exit $rc
