# Validation

`p16ctl verify` is the direct check. It sets balanced, reads the SPBM limits,
sets performance, reads again, then restores balanced.

```bash
sudo ./p16ctl verify
```

The command prints `PASS` only if the EC or effective limits changed. It prints
`FAIL` if the ASUS mode did not reach the SPBM controller. It uses the same
`/dev/mem` read path as `p16ctl power`.

Expected on the tested BIOS 303 machine:

```text
PASS: performance changed the EC limits
  SYSPL1: EC 126000 -> 130000 mW, effective ...
```

The exact values are not required. A change in at least one EC or effective
slot is the result.

## Optional load check

After a PASS, compare power and clock under a GPU load:

```bash
sudo ./p16ctl balanced
nvidia-smi --query-gpu=clocks.sm,power.draw --format=csv -lms 500
sudo ./p16ctl performance
nvidia-smi --query-gpu=clocks.sm,power.draw --format=csv -lms 500
sudo ./p16ctl balanced
```

Run the load in another terminal. The owner measured about 32 W / 1530 MHz in
balanced and about 55 W / 1980 MHz in performance.

## Report

Post the output of `p16ctl verify` with the BIOS version from `p16ctl status`.
Remove hostnames and usernames before posting.

## Limits

- One owner-tested BIOS 303 unit; `verify` has not been run by this repository's
  authors on P16 hardware.
- A VM cannot validate the ASUS EC. The QEMU test only validates the ACPI call
  path. See [vm-validation.md](vm-validation.md).
- Raising SPBM limits above the EC defaults is not implemented or validated.
