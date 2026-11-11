# The P16 GPU power unlock

## Short version

On the tested ASUS ProArt P16 H7607BA, the remaining GPU power limiter is the
ASUS EC thermal policy, not NVIDIA NVPCF. The ASUS ACPI method
`\_SB.ATKD.WMNB` with the `DEVS(0x00120075, 1)` call selects the performance
policy. It raises the sustained GPU budget from about 32 W to about 55 W.

```bash
sudo modprobe acpi_call
sudo ./p16ctl performance
```

Revert:

```bash
sudo ./p16ctl balanced
```

## Owner-tested configuration

| Item | Value |
|---|---|
| Laptop | ASUS ProArt P16 H7607BA |
| BIOS | `H7607BA.303` (2026-09-22) |
| EC | 3.3 |
| GPU | NVIDIA RTX Spark N1X, `10de:2e03`, VBIOS `9A.0B.35.00.04` |
| Kernel | Omarchy `7.3.0-41-omarchy`, native firmware DSDT |
| NVIDIA | 620.70.06 open modules and matching GSP firmware |
| ACPI helper | `acpi_call` |

The owner measured 180 s FP32 cuBLAS runs with `nvidia-smi` sampling at 500 ms.
The medians below use samples with GPU utilization at or above 50 percent.

| Policy | GPU power | SM clock | FP32 |
|---|---:|---:|---:|
| silent | 22.6 W | 1144 MHz | 9.3 TFLOP/s |
| balanced | 32.0 W | 1573 MHz | 12.8 TFLOP/s |
| performance | 54.9 W | 1976 MHz | 15.8 TFLOP/s |

Source: [issue 1521 comment 6741487270](https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1521#issuecomment-6741487270)
and the [owner gist](https://gist.github.com/aibix0001/28fe3c678d374db39aa36239bf94f21e).

## Exact ACPI call

The tool writes this line to `/proc/acpi/call`:

```text
\_SB.ATKD.WMNB 0 0x53564544 {0x75,0x00,0x12,0x00,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0}
```

Breakdown:

| Field | Meaning |
|---|---|
| `\_SB.ATKD.WMNB` | ASUS ATK ACPI WMI dispatch method |
| `0x53564544` | ASCII `DEVS` |
| `0x00120075` | ASUS `throttle_thermal_policy` object |
| `1` | performance; `0` balanced; `2` silent |

The 20-byte buffer is `75 00 12 00 <mode> 00 ... 00`.

The addendum reports:

> The call is `DEVS(0x00120075, 1)` = ASUS performance / "overboost" (EC cmd 0x11 = 4). Balanced (v=0) is the 32 W budget the stock kernel showed, and silent is 22 W.

> Without the ASUS WMI driver (stock kernel), the same budget can be selected by calling `\_SB.ATKD.WMNB 0 0x53564544 {0x75,0,0x12,0, v, 0...}` (20-byte buffer) via acpi_call.

Source: [issue 1521 comment 6742271714](https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1521#issuecomment-6742271714).

## Why the NVPCF path did not unlock it

The project began with the assumption that the P16 was capped because Linux did
not consume NVIDIA's encrypted NVPCF 3.0 table. The analysis produced a complete
transport model, but the P16 platform reply has no budget data:

| Subfunction | BIOS 303 reply |
|---:|---|
| 0 | Unicode `"?"`, which is `0x3f` |
| 1 | fixed 128-byte blob |
| 2 | six zero bytes |
| 3 | six zero bytes |
| 4 | integer 0 |
| 5 | integer 0 |

The owner's disassembly of the BIOS 303 `NPCF` method is in the gist as
`npcf-bios303.dsl`. The same report says:

> 620 already queries NVPCF 0x300, and this NPCF carries no budget data.

> `RMSkipACPIBattCap=1` alone changes nothing (32 W on AC and on battery on the stock kernel).

> 620 powerd (sha256 eb9e0371...) quits after about 0.25 s.

Source: [issue 1521 comment 6741487270](https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1521#issuecomment-6741487270).

## BIOS 300 vs BIOS 303

The original 754 MHz P4 state was reported on BIOS `H7607BA.300`. On BIOS 303
with the native DSDT, the owner reports:

> **No 754 MHz state on BIOS 303** with the native DSDT: none on 615 or 620, AC or battery, before or after replug.

This does not prove that the BIOS update alone fixes every P16. It does mean the
two problems should be kept separate:

1. BIOS 300 / stale DSDT: reported 754 MHz floor and `0x400`.
2. BIOS 303 / native DSDT: no 754 MHz floor, but a sustained 32 W balanced
   budget until the ASUS performance policy is selected.

If your machine is still on BIOS 300, `p16ctl` can still set the EC policy, but
it cannot repair the older DSDT or the 754 MHz state. Capture your DSDT/SSDT and
compare before attributing a result to the tool.

## Readback is not available

`DSTS(0x00120075)` returns a constant `0x00010003`, so the firmware does not
report the current mode. `p16ctl verify` reads the SPBM limits before and after
performance mode; that is the direct check. A GPU load and `nvidia-smi` are an
optional second check.

The EC keeps the mode across warm reboots. The boot service re-applies it after a
cold boot.

## Installing acpi_call

`/proc/acpi/call` is provided by the out-of-tree `acpi_call` module. Install it
for the running kernel, then load it:

```bash
sudo modprobe acpi_call
ls -l /proc/acpi/call
```

Common package names:

| Distribution | Package |
|---|---|
| Arch / Omarchy | `acpi_call-dkms` from the AUR |
| Debian / Ubuntu | `acpi-call-dkms` |
| Fedora | `akmod-acpi_call` from RPM Fusion, if available |

`./scripts/install-acpi-call.sh` checks for the device and prints these
instructions.

## Boot service

```bash
sudo ./scripts/install.sh
systemctl status p16-performance.service
```

The unit runs `p16ctl performance --quiet` once per boot when
`/proc/acpi/call` exists. It is a oneshot unit with `RemainAfterExit=yes`.

Remove:

```bash
sudo ./scripts/install.sh --uninstall
```

## Verification

```bash
sudo ./p16ctl verify
```

`PASS` means the EC or effective limits changed. The expected GPU result on the
tested machine is roughly 32 W and 1530 MHz in balanced versus 55 W and 1980 MHz
in performance. Other workloads, ambient temperature, and skin temperature
change the absolute numbers.

The owner's 180 s performance runs reached 81 C GPU and 86 C ACPI zones. Watch
thermals. If the machine becomes unstable or too hot, revert to balanced or
silent.

## Rollback

```bash
sudo ./p16ctl balanced
sudo ./p16ctl silent
```

`balanced` restores the stock 32 W budget. `silent` selects the 22 W budget.
The EC keeps the last selected mode across warm reboots. A cold boot returns to
the firmware default unless the service or a manual command applies another
mode.
