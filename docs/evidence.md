# Evidence

The unlock is based on one owner-reported, hardware-tested P16 result. The
repository authors have not repeated it on P16 hardware. Treat the evidence as
strong for the tested machine and untested for other BIOS versions and models.

## Primary source

- NVIDIA open-gpu-kernel-modules issue 1521:
  <https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1521>
- P16 BIOS 303 data and tools:
  <https://gist.github.com/aibix0001/28fe3c678d374db39aa36239bf94f21e>
- Gist revision: `7ed8bb785656bd8c2dd9a8a1ebc5349f0f8ea840`,
  2026-11-09 15:16:32 +0100.

## Exact claims

### The working call

Source:
<https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1521#issuecomment-6742271714>

> The call is `DEVS(0x00120075, 1)` = ASUS performance / "overboost" (EC cmd 0x11 = 4). Balanced (v=0) is the 32 W budget the stock kernel showed, and silent is 22 W. `INIT` has no effect.

> Without the ASUS WMI driver (stock kernel), the same budget can be selected by calling `\_SB.ATKD.WMNB 0 0x53564544 {0x75,0,0x12,0, v, 0...}` (20-byte buffer) via acpi_call.

### The measured effect

Source:
<https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1521#issuecomment-6741487270>

> **The sustained GPU budget follows the ASUS firmware thermal policy, and the ASUS WMI driver has to be loaded**

| Kernel / ASUS policy | sustained W | SM MHz | TFLOP/s |
|---|---:|---:|---:|
| stock 7.3 (no asus-wmi), any driver/AC/battery | ~32 | ~1550 | 12.4-12.9 |
| PR 1958 kernel, `quiet` | ~22 | ~1105 | 9.0 |
| PR 1958 kernel, `balanced` (boot default) | ~55 | ~1970 | 15.7 |
| PR 1958 kernel, `performance` | ~55 (67 W burst) | ~1950 | 15.7 |

Source:
<https://gist.github.com/aibix0001/28fe3c678d374db39aa36239bf94f21e>

The gist `README.md` reports medians from 180 s FP32 cuBLAS runs:

| Policy | GPU power | SM clock | FP32 |
|---|---:|---:|---:|
| silent | 22.6 W | 1144 MHz | 9.3 TFLOP/s |
| balanced | 32.0 W | 1573 MHz | 12.8 TFLOP/s |
| performance | 54.9 W | 1976 MHz | 15.8 TFLOP/s |

The same gist records `h1` balanced and `h2` performance metadata, including
the 620.70.06 driver string and the 180 s run shape.

### BIOS 303 has no 754 MHz state

Source:
<https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1521#issuecomment-6741487270>

> **No 754 MHz state on BIOS 303** with the native DSDT: none on 615 or 620, AC or battery, before or after replug.

> **`RMSkipACPIBattCap=1` alone changes nothing** (32 W on AC and on battery on the stock kernel). The key appears only in the GSP firmware strings, not in the open RM source.

> 620 powerd (sha256 eb9e0371...) quits after about 0.25 s.

### NPCF is a static stub on BIOS 303

Source: gist `npcf-bios303.dsl`

The `NPCF` method checks `Arg1 == 0x300`, then returns:

- subfunction 0: `Unicode ("?")`
- subfunction 1: a fixed `Buffer (0x80)`
- subfunctions 2 and 3: `Buffer (0x06)` of zeros
- subfunctions 4 and 5: `Zero`

The source comment in the issue:

> 620 already queries NVPCF 0x300, and this NPCF carries no budget data.

### The 620 binary does contain a 3.x consumer

The official NVIDIA 620.70.06 Linux aarch64 driver package contains a
`nvidia-powerd` binary with `DsmConfig3xBase`, `DsmConfig3xSubfunc`,
`DsmConfig3xSubscribed`, `DsmConfig3xReadPrimitive`, `DsmConfig3xWritePrimitive`,
and `DsmConfig3xCriticalStatus`. The string
`INFO: %sTrying NVPCF DSM 3x initialization` is present.

This corrects the earlier source-only statement that no public 3.x consumer
exists. The binary still exits after about 0.25 s on the P16, and the P16 NPCF
reply has no budget data, so the consumer is not a solution here.

The package also lists the P16 GPU:

```text
NVIDIA RTX Spark N1X (6144-core Blackwell RTX GPU)       2E03            K
NVIDIA RTX Spark N1X (5120-core Blackwell RTX GPU)       2E06            K
```

Source: official `NVIDIA-Linux-aarch64-620.70.06.run`,
`README.txt:10086`, package SHA-256
`3fa65a9271e0dde2a4e58c4965c38885a02a3a42accdcb26fc817410607f3e03`.

## Reproducibility notes

The exact ACPI call is unit-tested in `tests/test_p16ctl.py`:

```text
\_SB.ATKD.WMNB 0 0x53564544 {0x75,0x00,0x12,0x00,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0}
```

The test does not write to `/proc/acpi/call` and does not require P16 hardware.
The installer and service are shell-syntax checked. The GPU measurements are
the owner's, not this repository's.

## Evidence hashes

| File | SHA-256 |
|---|---|
| gist `README.md` | `4ebf03d962ee2f5f2f47c1d3e54ca06f3461a308649c168c2797ca00065528e5` |
| gist `ADDENDUM.md` | `010f49c062970bdeb7e88d45431ffa0c57eaa484d3b136f6492f99fccb6efaf4` |
| gist `set-ttp.sh` | `35b9ca4bc9f1014e6e628d1c6b29cf10dc3601d206675ab85f41b676dcff9ffb` |
| gist `npcf-bios303.dsl` | `1bf7e7f26cbe3fb6cd8d9a5a9223f20f652effe335d046aee7839cc256b41ec8` |
| NVIDIA 620.70.06 aarch64 run | `3fa65a9271e0dde2a4e58c4965c38885a02a3a42accdcb26fc817410607f3e03` |

## Limits

- One P16 owner, one BIOS 303 unit, one driver stack.
- The EC mode has no reliable readback.
- Absolute power and clock values depend on workload, temperature, and fan
  policy.
- BIOS 300 behavior and other ASUS N1X models are not established.

## Independent corroboration

A second P16 owner (`seankd3`) reported sustained 0x4 GPU power of 47.6-61.6 W
and median SM clocks of 2034-2177 MHz on the ASUS-WMI kernel, versus about 32 W
on the stock kernel. Source:
<https://github.com/NVIDIA/open-gpu-kernel-modules/issues/1521#issuecomment-6709119982>.

> The SM clock stayed between 1430 and 2424 MHz, with a median of 2034 MHz. The 754 MHz state did not return.

This supports the higher ASUS WMI/EC budget independently. It did not isolate
the exact `DEVS(0x00120075,1)` call; that is the `aibix0001` result above.

## Standard ASUS interface

The call is not a one-off guess. It is the same interface the Linux `asus-wmi`
driver and G-Helper use:

- Linux `drivers/platform/x86/asus-wmi.c` defines
  `ASUS_WMI_DEVID_THROTTLE_THERMAL_POLICY = 0x00120075` and writes it through
  `DEVS`.
- The mode values are `0` balanced, `1` turbo/performance, `2` silent.
- G-Helper's `AsusACPI.cs` uses the same `DEVS` and `DSTS` method IDs
  (`0x53564544` and `0x53545344`) and the same performance-mode ID.
- The ASUS reverse-engineering notes at
  <https://github.com/dvalfrid/rigstats/blob/918900938ce11c1967cf5093228d9249a951d0dd/docs/asus-laptop-acpi.md>
  summarize it as: "One id: `0x00120075` (ROG/TUF 'throttle thermal policy':
  0 Balanced, 1 Turbo, 2 Silent)".

This makes `p16ctl performance` equivalent to selecting the performance
`platform_profile` on a kernel with working ASUS WMI. On the P16 stock kernel
without ASUS WMI, the direct ACPI call is the available path.

## Prior art

The unlock was demonstrated before this repository:

- `aibix0001` published the exact `DEVS(0x00120075,1)` call and the 32 W to
  55 W measurements in the [issue 1521 gist](https://gist.github.com/aibix0001/28fe3c678d374db39aa36239bf94f21e).
- `LeonMarzollDev/proart-p16-linux` implements the same ASUS EC mode in
  [`drivers/proart-battery`](https://github.com/LeonMarzollDev/proart-p16-linux/tree/main/drivers/proart-battery)
  and exposes it as `platform_profile`; its
  [`docs/technical-notes.md`](https://github.com/LeonMarzollDev/proart-p16-linux/blob/main/docs/technical-notes.md)
  documents the `DEVS 0x00120075` mailbox writes.

This repository does not claim first discovery. Its contribution is the
userspace ACPI tool, the one-command EC verification, and the packaged
reproducibility.
