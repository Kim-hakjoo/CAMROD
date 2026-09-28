#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <module_pkg_name> [tag]"
  exit 1
fi

MODULE="$1"
TAG="${2:-${MODULE}:humble}"
BASE_IMAGE="${BASE_IMAGE:-camrod/base:humble}"

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
SRC_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

docker build \
  -f "${SCRIPT_DIR}/Dockerfile.module" \
  --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
  --build-arg MODULE="${MODULE}" \
  -t "${TAG}" \
  "${SRC_ROOT}"

echo "Built image: ${TAG}"
