#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

if [ "$(id -u)" -ne 0 ]; then
  echo "run with sudo: sudo $0" >&2
  exit 1
fi

exec "$ROOT/p16ctl" verify "$@"
