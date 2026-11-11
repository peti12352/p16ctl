"""Set and verify the ASUS ProArt P16 performance thermal mode."""

from __future__ import annotations

import argparse
import json
import mmap
import os
import struct
import sys
import time
from pathlib import Path

ACPI_CALL = Path("/proc/acpi/call")
SYSFS = Path("/")
POWER_BASE = 0x1C238000
POWER_SIZE = 0x1000
WMNB = r"\_SB.ATKD.WMNB"
DEVS = 0x53564544
DSTS = 0x53545344
TTP = bytes((0x75, 0x00, 0x12, 0x00))
MODES = {"balanced": 0, "performance": 1, "silent": 2}
EXPECTED = {
    "balanced": "about 32 W",
    "performance": "about 55 W",
    "silent": "about 22 W",
}
TESTED_BIOS = "H7607BA.303"
SLOTS = ("PL1", "PL2", "PL3", "PL4", "SYSPL1", "SYSPL2", "SYSPL3", "SYSPL4")


class P16Error(RuntimeError):
    pass


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def platform() -> dict:
    return {
        "vendor": _read(SYSFS / "sys/class/dmi/id/sys_vendor"),
        "product": _read(SYSFS / "sys/class/dmi/id/product_name"),
        "board": _read(SYSFS / "sys/class/dmi/id/board_name"),
        "bios": _read(SYSFS / "sys/class/dmi/id/bios_version"),
        "profile": _read(SYSFS / "sys/firmware/acpi/platform_profile"),
        "choices": _read(SYSFS / "sys/firmware/acpi/platform_profile_choices"),
        "acpi_call": ACPI_CALL.exists(),
    }


def is_p16(info: dict) -> bool:
    text = " ".join(str(info.get(key) or "") for key in ("vendor", "product", "board")).lower()
    return "asus" in text and ("h7607" in text or "proart p16" in text)


def mode_buffer(mode: int) -> bytes:
    if mode not in MODES.values():
        raise ValueError("invalid mode")
    return TTP + bytes((mode,)) + bytes(15)


def format_buffer(data: bytes) -> str:
    head = ",".join(f"0x{byte:02x}" for byte in data[:4])
    tail = ",".join(str(byte) if byte < 10 else f"0x{byte:02x}" for byte in data[4:])
    return f"{head},{tail}"


def wmnb(command: int, payload: bytes) -> str:
    return f"{WMNB} 0 0x{command:08x} {{{format_buffer(payload)}}}"


def devs_call(mode: int) -> str:
    return wmnb(DEVS, mode_buffer(mode))


def dsts_call() -> str:
    return wmnb(DSTS, TTP + bytes(16))


def acpi_write(call: str, path: Path | None = None, dry_run: bool = False) -> str:
    if dry_run:
        return "dry-run"
    path = path or ACPI_CALL
    with path.open("w", encoding="ascii") as handle:
        handle.write(call + "\n")
    time.sleep(0.05)
    with path.open("r", encoding="ascii", errors="replace") as handle:
        return handle.read().replace("\x00", "").strip()


def apply_mode(
    mode: str,
    *,
    dry_run: bool = False,
    quiet: bool = False,
    call_path: Path | None = None,
) -> dict:
    if mode not in MODES:
        raise P16Error(f"unknown mode: {mode}")
    info = platform()
    if not dry_run and not is_p16(info):
        raise P16Error("not an ASUS ProArt P16 H7607")
    if not dry_run and not info["acpi_call"]:
        raise P16Error("acpi_call is missing; install it and run sudo modprobe acpi_call")
    if not dry_run and os.geteuid() != 0:
        raise P16Error(f"run as root: sudo p16ctl {mode}")
    if not dry_run and not quiet and info["bios"] != TESTED_BIOS:
        print(f"warning: tested BIOS is {TESTED_BIOS}; this is {info['bios'] or 'unknown'}", file=sys.stderr)
    call = devs_call(MODES[mode])
    result = acpi_write(call, call_path, dry_run)
    return {"mode": mode, "call": call, "result": result, "expected": EXPECTED[mode]}


def _u32(data: bytes | mmap.mmap, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def decode_power(data: bytes | mmap.mmap) -> dict:
    if len(data) < POWER_SIZE:
        raise ValueError("power map is too short")
    slots = {
        name: {
            "os_mw": _u32(data, 0x100 + index * 4),
            "ec_mw": _u32(data, 0x120 + index * 4),
            "uefi_mw": _u32(data, 0x140 + index * 4),
            "effective_mw": _u32(data, 0x160 + index * 4),
        }
        for index, name in enumerate(SLOTS)
    }
    bounds = {
        name: {
            "min_mw": _u32(data, 0x708 + index * 0x10),
            "max_mw": _u32(data, 0x70C + index * 0x10),
        }
        for index, name in enumerate(("PL1", "PL2", "SYSPL1", "SYSPL2"))
    }
    return {
        "slots": slots,
        "bounds": bounds,
        "controller": _u32(data, 0x048),
        "prochot": _u32(data, 0x04C),
        "package_mw": _u32(data, 0x804),
        "system_mw": _u32(data, 0x814),
    }


def read_power(path: str = "/dev/mem") -> dict:
    if os.geteuid() != 0:
        raise P16Error("run as root: sudo p16ctl power")
    fd = os.open(path, os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, POWER_SIZE, prot=mmap.PROT_READ, offset=POWER_BASE) as memory:
            return decode_power(memory)
    finally:
        os.close(fd)


def verify(quiet: bool = False) -> int:
    if not is_p16(platform()):
        raise P16Error("verify requires an ASUS ProArt P16 H7607")
    apply_mode("balanced", quiet=quiet)
    time.sleep(1)
    before = read_power()
    apply_mode("performance", quiet=quiet)
    time.sleep(1)
    after = read_power()
    apply_mode("balanced", quiet=True)
    changed = {
        name: {
            "ec_before_mw": before["slots"][name]["ec_mw"],
            "ec_after_mw": after["slots"][name]["ec_mw"],
            "effective_before_mw": before["slots"][name]["effective_mw"],
            "effective_after_mw": after["slots"][name]["effective_mw"],
        }
        for name in SLOTS
        if before["slots"][name]["ec_mw"] != after["slots"][name]["ec_mw"]
        or before["slots"][name]["effective_mw"] != after["slots"][name]["effective_mw"]
    }
    if changed:
        print("PASS: performance changed the EC limits")
        for name, values in changed.items():
            print(
                f"  {name}: EC {values['ec_before_mw']} -> {values['ec_after_mw']} mW, "
                f"effective {values['effective_before_mw']} -> {values['effective_after_mw']} mW"
            )
        return 0
    print("FAIL: EC limits unchanged")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="p16ctl", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in MODES:
        mode = sub.add_parser(name, help=f"set {name} mode")
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--quiet", action="store_true")
        mode.set_defaults(command="mode", mode=name)

    power = sub.add_parser("power", help="read EC power limits")
    power.add_argument("--json", action="store_true")
    power.set_defaults(command="power")

    check = sub.add_parser("verify", help="verify performance changes EC limits")
    check.add_argument("--quiet", action="store_true")
    check.set_defaults(command="verify")

    info = sub.add_parser("status", help="show platform and ACPI state")
    info.set_defaults(command="status")

    args = parser.parse_args(argv)
    try:
        if args.command == "mode":
            result = apply_mode(args.mode, dry_run=args.dry_run, quiet=args.quiet)
            print(result["call"] if args.dry_run else f"{args.mode} requested; EC result {result['result']}")
            return 0
        if args.command == "power":
            report = read_power()
            if args.json:
                print(json.dumps(report, indent=2))
                return 0
            for name, values in report["slots"].items():
                print(
                    f"{name:6} os={values['os_mw']:6} ec={values['ec_mw']:6} "
                    f"effective={values['effective_mw']:6} mW"
                )
            print(f"package={report['package_mw']} mW system={report['system_mw']} mW")
            return 0
        if args.command == "verify":
            return verify(args.quiet)
        if args.command == "status":
            data = platform()
            print(f"product: {data['product'] or 'unknown'}")
            print(f"bios: {data['bios'] or 'unknown'}")
            print(f"platform_profile: {data['profile'] or 'unknown'}")
            print(f"choices: {data['choices'] or 'unknown'}")
            print(f"acpi_call: {'present' if data['acpi_call'] else 'missing'}")
            return 0
        raise P16Error("unknown command")
    except (P16Error, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
