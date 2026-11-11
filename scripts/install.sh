#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

if [ "${1:-}" = "--uninstall" ]; then
  systemctl disable --now p16-performance.service 2>/dev/null || true
  rm -f /usr/local/bin/p16ctl /usr/local/bin/p16ctl.py
  rm -f /etc/systemd/system/p16-performance.service
  systemctl daemon-reload
  echo "removed p16ctl and p16-performance.service"
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "run with sudo: sudo $0" >&2
  exit 1
fi

install -Dm755 "$ROOT/p16ctl" /usr/local/bin/p16ctl
install -Dm644 "$ROOT/p16ctl.py" /usr/local/bin/p16ctl.py
install -Dm644 "$ROOT/systemd/p16-performance.service" \
  /etc/systemd/system/p16-performance.service
systemctl daemon-reload

if [ -e /proc/acpi/call ]; then
  systemctl enable --now p16-performance.service
  echo "installed; p16-performance.service is enabled"
else
  echo "installed; acpi_call is missing"
  echo "install acpi_call, then run: sudo systemctl enable --now p16-performance.service"
fi
