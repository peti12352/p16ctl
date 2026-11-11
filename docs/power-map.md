# P16 SPBM power map

`p16ctl power` is a read-only view of the P16 System Power Budget Manager
(SPBM) registers at physical `0x1c238000`. It reads the OS, EC, UEFI, and
effective power limits, the controller status, and the known power telemetry
words.

This map is not guessed from the ASUS `DEVS` call. It comes from the community
reverse engineering in `johannhartmann/spark_hwmon` and its hardware-validated
cap experiments. Those experiments wrote PL1, PL2, SysPL1, and SysPL2
reductions and measured the resulting limits. Raising limits was not validated.

## Usage

```bash
sudo ./p16ctl power
sudo ./p16ctl power --json
```

The command opens `/dev/mem` read-only and maps one 4 KiB page. It performs no
writes.

## Registers

Base: `0x1c238000`.

| Offset | Meaning |
|---:|---|
| `0x048` | Active controller: `0x01` PL1, `0x02` PL2, `0x08` SysPL1, `0x10` SysPL2 |
| `0x04c` | Raw PROCHOT field; polarity is not validated |
| `0x100..0x11c` | OS request limits: PL1, PL2, PL3, PL4, SysPL1, SysPL2, SysPL3, SysPL4 |
| `0x120..0x13c` | EC limits for the same eight slots |
| `0x140..0x15c` | UEFI limits for the same eight slots |
| `0x160..0x17c` | Effective limits for the same eight slots |
| `0x708/0x70c` | PL1 floor/ceiling, mW |
| `0x718/0x71c` | PL2 floor/ceiling, mW |
| `0x738/0x73c` | SysPL1 floor/ceiling, mW |
| `0x748/0x74c` | SysPL2 floor/ceiling, mW |
| `0x800` | PSOC / platform power candidate, mW |
| `0x804` | Package power, mW |
| `0x80c` | PSYS / system power candidate, mW |
| `0x814` | System power, mW |
| `0x818` | Raw package temperature |
| `0x81c` | Whole-degree package temperature, C |

The eight limit slots are indexed by position:

```text
0 PL1
1 PL2
2 PL3
3 PL4
4 SysPL1
5 SysPL2
6 SysPL3
7 SysPL4
```

A zero OS request means the firmware default is active. The EC limits are the
firmware values; the effective limits are what the controller is currently
enforcing. The community cap experiments confirm that writing a lower OS value
changes the effective limit and that zero restores the current EC value.

## How this helps verify the ASUS mode

On a P16, run:

```bash
sudo ./p16ctl balanced
sudo ./p16ctl power --json
sudo ./p16ctl performance
sudo ./p16ctl power --json
```

If the ASUS `DEVS` call changes the EC or effective limits, the two reports show
it directly. This is a stronger check than `nvidia-smi` clocks because it reads
the EC/SPBM state, not a driver interpretation. The current BIOS 303 owner data
used GPU power/clock measurements, not this register map, so the map is a new
independent verification path.

## What is not validated

- Raising any limit above the EC default. Only reductions were tested.
- Writing PL3 or PL4.
- The exact units and polarity of the raw PROCHOT and diagnostic fields.
- The BIOS 303 register behavior. The published map was validated on BIOS 300.
- A safe sustained increase. The SysPL3 experiment found that SysPL2 still
  constrained the longer baseline, and the thermal/electrical headroom is not
  qualified.

Do not use this map to write power limits until a P16 owner has run a bounded,
watchdog-protected A/B test and published the result.

## Sources

- `johannhartmann/spark_hwmon`:
  `docs/n1x-register-contract.md`, `docs/validation/open-gaps-research.md`,
  `docs/validation/dgx-directory-crosscheck.json`, `tools/n1x-cap-experiment.py`.
- P16 `docs/gpu-power.md` in
  `johannhartmann/asus-proart-p16-rtx-spark-linux`.
- NVIDIA 617.42 `nvpcf.sys` descriptor accessor analysis: SPBM is kind 5;
  write direction 2; update offset 0.
- Hardware cap experiments: PL1, PL2, SysPL1, SysPL2 each selected as the
  active controller and measured under load.
