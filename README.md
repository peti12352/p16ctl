# p16ctl

Set and verify the ASUS ProArt P16 performance thermal mode on Linux.

Stock balanced mode holds the GPU near 32 W. The ASUS performance mode raises it
to about 55 W on the tested BIOS 303 machine.

```bash
sudo modprobe acpi_call
sudo ./scripts/install.sh
sudo ./p16ctl performance
sudo ./p16ctl verify
```

`acpi_call` is required. `scripts/install-acpi-call.sh` checks it and prints the
package names for Arch, Debian, and Fedora.

## Commands

```text
p16ctl performance   set ASUS performance mode
p16ctl balanced      restore stock mode
p16ctl silent        set quiet mode
p16ctl power         read EC power limits (read-only)
p16ctl verify        check that performance changes EC limits
p16ctl status        show platform and ACPI state
```

Mode commands accept `--dry-run`, which prints the exact ACPI call.

Revert with `sudo ./p16ctl balanced`.

## What it changes

`DEVS(0x00120075, v)` is the standard ASUS `throttle_thermal_policy` interface
used by Linux `asus-wmi` and G-Helper:

```text
v = 0  balanced
v = 1  performance
v = 2  silent
```

The exact call is:

```text
\_SB.ATKD.WMNB 0 0x53564544 {0x75,0x00,0x12,0x00,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0}
```

It writes no voltage, clock, vBIOS, or NVIDIA NVPCF data. The EC keeps the mode
across warm reboots; the boot service re-applies it.

## Verify

```bash
sudo ./p16ctl verify
```

It sets balanced, reads the SPBM limits, sets performance, reads again, and
restores balanced. `PASS` means the EC or effective limits changed. `FAIL` means
the mode did not reach the EC on that unit.

`sudo ./scripts/validate.sh` runs the same check.

## Prior art

The mode is not new. `aibix0001` published the exact call and the 32 W to 55 W
measurement in the issue 1521 gist. `LeonMarzollDev/proart-p16-linux` implements
the same EC mode in its `proart_battery` driver. This repo packages the userspace
ACPI path and adds the EC verification.

## Test

```bash
python3 -m pytest -q
python3 -m ruff check .
bash -n scripts/*.sh
```

The AML and QEMU tests are optional; see `docs/vm-validation.md`.

## Disclaimer

Not affiliated with ASUSTeK Computer Inc. or NVIDIA Corporation. This
software is provided as-is, without warranty. Selecting a thermal policy can
affect power, cooling, stability, and warranty coverage. Use at your own risk.

## Status

Owner-validated on BIOS `H7607BA.303`. The repo authors do not own a P16, so
`p16ctl verify` has not run here on hardware. Run it on a P16 to produce the
final EC proof.

GPL-2.0-only. See `LICENSE`.
