#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
KERNEL=${KERNEL:-/boot/vmlinuz-$(uname -r)}
KDIR=${KDIR:-/lib/modules/$(uname -r)/build}
BUSYBOX=${BUSYBOX:-/usr/bin/busybox}
IASL=${IASL:-$(command -v iasl || true)}
ACPI_CALL_SRC=${ACPI_CALL_SRC:-}

if [ "$(uname -m)" != "x86_64" ]; then
  echo "this VM test needs an x86_64 host and an x86_64 kernel image" >&2
  exit 1
fi
for item in qemu-system-x86_64 cpio gzip make gcc; do
  command -v "$item" >/dev/null 2>&1 || { echo "missing: $item" >&2; exit 1; }
done
[ -r "$KERNEL" ] || { echo "missing kernel image: $KERNEL" >&2; exit 1; }
[ -d "$KDIR" ] || { echo "missing kernel headers: $KDIR" >&2; exit 1; }
[ -x "$BUSYBOX" ] || { echo "missing static busybox: $BUSYBOX" >&2; exit 1; }
[ -n "$IASL" ] || { echo "missing iasl" >&2; exit 1; }

WORK=$(mktemp -d /tmp/p16-vm-test.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

if [ -z "$ACPI_CALL_SRC" ]; then
  ACPI_CALL_SRC="$WORK/acpi_call"
  git clone -q --depth 1 https://github.com/mkottman/acpi_call.git "$ACPI_CALL_SRC"
fi
cp "$ACPI_CALL_SRC/acpi_call.c" "$WORK/acpi_call.c"
python3 - "$WORK/acpi_call.c" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
text = text.replace("#include <asm/uaccess.h>\n#include <acpi/acpi.h>",
                    "#include <linux/uaccess.h>\n#include <linux/acpi.h>")
text = text.replace(
    "static struct file_operations proc_acpi_operations = {\n"
    "        .owner    = THIS_MODULE,\n"
    "        .read     = acpi_proc_read,\n"
    "        .write    = acpi_proc_write,\n"
    "};",
    "static struct proc_ops proc_acpi_operations = {\n"
    "        .proc_read  = acpi_proc_read,\n"
    "        .proc_write = acpi_proc_write,\n"
    "};",
)
path.write_text(text)
PY
cp "$ACPI_CALL_SRC/Makefile" "$WORK/Makefile"
make -C "$WORK" -j"$(nproc)" KDIR="$KDIR" >/dev/null
[ -f "$WORK/acpi_call.ko" ] || { echo "failed to build acpi_call.ko" >&2; exit 1; }

"$IASL" -p "$WORK/atkd" "$ROOT/tests/fixtures/asus_wmnb.asl" >/dev/null
[ -f "$WORK/atkd.aml" ] || { echo "failed to build atkd.aml" >&2; exit 1; }

BAL_CALL=$("$ROOT/p16ctl" balanced --dry-run)
PERF_CALL=$("$ROOT/p16ctl" performance --dry-run)
SILENT_CALL=$("$ROOT/p16ctl" silent --dry-run)
DSTS_CALL=$(python3 -c 'import p16ctl; print(p16ctl.dsts_call())')

mkdir -p "$WORK/initramfs/bin" "$WORK/initramfs/proc" "$WORK/initramfs/sys" \
  "$WORK/initramfs/dev" "$WORK/initramfs/tmp"
cp "$BUSYBOX" "$WORK/initramfs/bin/busybox"
cp "$WORK/acpi_call.ko" "$WORK/initramfs/acpi_call.ko"
{
  echo '#!/bin/busybox sh'
  echo '/bin/busybox --install -s /bin'
  echo 'mount -t proc none /proc'
  echo 'mount -t sysfs none /sys'
  echo 'mount -t devtmpfs none /dev 2>/dev/null || true'
  echo 'echo "=== p16 VM ACPI test ==="'
  echo 'insmod /acpi_call.ko'
  echo 'sleep 2'
  printf "printf '%%s\\\\n' '%s' > /proc/acpi/call\n" "$BAL_CALL"
  echo 'cat /proc/acpi/call >/dev/null'
  printf "printf '%%s\\\\n' '%s' > /proc/acpi/call\n" "$PERF_CALL"
  echo 'echo "DEVS performance result: $(cat /proc/acpi/call)"'
  echo "printf '%s\\n' '\\_SB.ATKD.LAST' > /proc/acpi/call"
  echo 'echo "LAST after performance: $(cat /proc/acpi/call)"'
  printf "printf '%%s\\\\n' '%s' > /proc/acpi/call\n" "$SILENT_CALL"
  echo 'echo "DEVS silent result: $(cat /proc/acpi/call)"'
  echo "printf '%s\\n' '\\_SB.ATKD.LAST' > /proc/acpi/call"
  echo 'echo "LAST after silent: $(cat /proc/acpi/call)"'
  printf "printf '%%s\\\\n' '%s' > /proc/acpi/call\n" "$DSTS_CALL"
  echo 'echo "DSTS result: $(cat /proc/acpi/call)"'
  echo 'echo "=== done ==="'
  echo 'poweroff -f'
} > "$WORK/initramfs/init"
chmod +x "$WORK/initramfs/init"
(
  cd "$WORK/initramfs"
  find . -print0 | cpio --null -o -H newc 2>/dev/null | gzip -9 > "$WORK/initramfs.cpio.gz"
)

set +e
timeout 120 qemu-system-x86_64 \
  -m 1024 -smp 2 -nographic -no-reboot \
  -kernel "$KERNEL" \
  -initrd "$WORK/initramfs.cpio.gz" \
  -append 'console=ttyS0 rdinit=/init panic=-1 loglevel=7' \
  -acpitable file="$WORK/atkd.aml" > "$WORK/qemu.log" 2>&1
qemu_status=$?
set -e
grep -aE 'p16 VM ACPI test|DEVS performance result|LAST after performance|DEVS silent result|LAST after silent|DSTS result|done' "$WORK/qemu.log"
grep -aq 'LAST after performance: 0x1' "$WORK/qemu.log"
grep -aq 'LAST after silent: 0x2' "$WORK/qemu.log"
grep -aq 'DSTS result: 0x10003' "$WORK/qemu.log"
if [ "$qemu_status" -ne 0 ]; then
  echo "qemu exited with $qemu_status" >&2
  exit 1
fi
echo "VM ACPI test passed"
