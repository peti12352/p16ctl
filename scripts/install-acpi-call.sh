#!/usr/bin/env bash
set -euo pipefail

if [ -e /proc/acpi/call ]; then
  echo "/proc/acpi/call is present"
  exit 0
fi

if command -v modprobe >/dev/null 2>&1; then
  modprobe acpi_call 2>/dev/null || true
fi

if [ -e /proc/acpi/call ]; then
  echo "acpi_call loaded"
  exit 0
fi

cat <<'EOF'
acpi_call is not available.

Install the module for your running kernel, then load it:
  Arch/Omarchy: install acpi_call-dkms from the AUR
  Debian/Ubuntu: sudo apt install acpi-call-dkms
  Fedora: install akmod-acpi_call from RPM Fusion if available
  Then: sudo modprobe acpi_call
EOF
exit 1
