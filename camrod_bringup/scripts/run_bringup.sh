#!/usr/bin/env bash
# Run bringup.launch.py and exit the terminal when it terminates.
# Usage: ./run_bringup.sh [extra launch args...]
#   e.g. ./run_bringup.sh sim:=true
#        ./run_bringup.sh rviz:=false

set -e
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    printf '%s\n' \
        'Usage: ./run_bringup.sh [--print-paths] [extra launch args...]' \
        'Run this checkout using the output root selected by colcon_build.sh.' \
        'CAMROD_BUILD_ROOT overrides the build/install/log output root.'
    exit 0
fi
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
SRC_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
RESOLVED_PATHS="$("${SRC_ROOT}/colcon_build.sh" --print-paths)"
if [[ "${1:-}" == --print-paths ]]; then
    printf '%s\n' "${RESOLVED_PATHS}"
    exit 0
fi
WS=""
while IFS='=' read -r key value; do
    if [[ "${key}" == WS_ROOT ]]; then WS="${value}"; fi
done <<< "${RESOLVED_PATHS}"
[[ "${WS}" == /* ]] || { echo "Invalid CAMROD output root" >&2; exit 1; }

# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash
if [ -f "${WS}/install/setup.bash" ]; then
    # shellcheck disable=SC1091
    source "${WS}/install/setup.bash"
fi

echo "[run_bringup] Starting bringup.launch.py $*"
ros2 launch camrod_bringup bringup.launch.py "$@"

# Terminal closes automatically when ros2 launch exits (Ctrl+C or crash).
# HH_260805 - ROS launch performs graceful child shutdown; clean_before_launch
# clears any stale process left by an abnormal termination before the next run.
