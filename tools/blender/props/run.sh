#!/bin/sh
# Retry a props build script: the box is shared and Blender occasionally loses a
# CUDA context or an allocation when other agents spike memory.
BL="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
SCRIPT="$1"; shift
LOG="${LOG:-/tmp/props_build.log}"
for i in 1 2 3 4 5; do
  "$BL" -b --factory-startup --python "$SCRIPT" -- "$@" > "$LOG" 2>&1
  rc=$?
  if [ $rc -eq 0 ] && grep -aq EXPORTED "$LOG"; then
    tr -d '\0' < "$LOG" | grep -aE "=== building|pre-bake|^  tris|EXPORTED|WARNING: no material"
    exit 0
  fi
  echo "attempt $i failed (rc=$rc), retrying..."
  sleep 12
done
tr -d '\0' < "$LOG" | grep -avE "^Info: Baking|Fra:" | tail -25
exit 1
