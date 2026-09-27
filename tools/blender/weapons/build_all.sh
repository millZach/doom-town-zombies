#!/bin/sh
# Rebuild every weapon viewmodel.  Each runs in its own Blender process: re-initialising the
# scene after a Cycles GPU render in the same session is unstable.
#
# Everything goes through run_locked.sh - only ONE Blender may run at a time on this machine
# (several agents share it and the laptop overheats).  Run from the project root.
D="$(cd "$(dirname "$0")" && pwd)"
R="$D/../run_locked.sh"
for w in m1911 mp5 m14 olympia remington870 ak74u galil rpd python raygun; do
  echo "=== $w ==="
  sh "$R" "$D/build_$w.py" 2>&1 | grep -E "WEAPON|cam=|movable|TOTAL|EXPORTED|Traceback|Error:|run_locked"
done
for w in knife frag drink; do
  echo "=== $w ==="
  sh "$R" "$D/build_melee.py" --which=$w 2>&1 | grep -E "WEAPON|cam=|movable|TOTAL|EXPORTED|Traceback|Error:|run_locked"
done
