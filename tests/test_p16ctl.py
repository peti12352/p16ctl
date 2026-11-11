import json
from pathlib import Path

import pytest

import p16ctl


def test_devs_performance_call_matches_owner_recipe():
    assert p16ctl.devs_call(1) == (
        r"\_SB.ATKD.WMNB 0 0x53564544 "
        "{0x75,0x00,0x12,0x00,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0}"
    )


def test_modes_have_distinct_calls():
    calls = {p16ctl.devs_call(value) for value in p16ctl.MODES.values()}
    assert len(calls) == 3
    assert all(call.startswith(r"\_SB.ATKD.WMNB 0 0x53564544 ") for call in calls)


def test_dsts_call_is_read_shaped():
    assert p16ctl.dsts_call().endswith(
        "{0x75,0x00,0x12,0x00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0}"
    )


def test_platform_is_p16(tmp_path, monkeypatch):
    root = tmp_path / "sys"
    (root / "class/dmi/id").mkdir(parents=True)
    (root / "class/dmi/id/sys_vendor").write_text("ASUSTeK COMPUTER INC.\n")
    (root / "class/dmi/id/product_name").write_text("ProArt P16 H7607BA\n")
    (root / "class/dmi/id/board_name").write_text("H7607BA\n")
    (root / "class/dmi/id/bios_version").write_text("H7607BA.303\n")
    (root / "firmware/acpi").mkdir(parents=True)
    (root / "firmware/acpi/platform_profile").write_text("balanced\n")
    (root / "firmware/acpi/platform_profile_choices").write_text("quiet balanced performance\n")
    monkeypatch.setattr(p16ctl, "SYSFS", tmp_path)
    monkeypatch.setattr(p16ctl, "ACPI_CALL", tmp_path / "call")
    info = p16ctl.platform()
    assert p16ctl.is_p16(info)
    assert info["profile"] == "balanced"
    assert info["choices"] == "quiet balanced performance"


def test_apply_dry_run_prints_exact_call(capsys):
    assert p16ctl.main(["performance", "--dry-run"]) == 0
    assert capsys.readouterr().out.strip() == p16ctl.devs_call(1)


def test_apply_mode_writes_call(tmp_path, monkeypatch):
    monkeypatch.setattr(p16ctl, "platform", lambda: {
        "vendor": "ASUSTeK COMPUTER INC.",
        "product": "ProArt P16 H7607BA",
        "board": "H7607BA",
        "bios": "H7607BA.303",
        "acpi_call": True,
    })
    monkeypatch.setattr(p16ctl.os, "geteuid", lambda: 0)
    seen = {}

    def fake_write(call, path=None, dry_run=False):
        seen["call"] = call
        return "0x1"

    monkeypatch.setattr(p16ctl, "acpi_write", fake_write)
    result = p16ctl.apply_mode("silent")
    assert result["result"] == "0x1"
    assert seen["call"] == p16ctl.devs_call(2)


def _power_map(ec_values):
    return {
        "slots": {
            name: {"os_mw": 0, "ec_mw": value, "uefi_mw": 0, "effective_mw": value}
            for name, value in zip(p16ctl.SLOTS, ec_values)
        },
        "bounds": {},
        "controller": 0,
        "prochot": 1,
        "package_mw": 0,
        "system_mw": 0,
    }


def test_verify_passes_when_ec_limits_change(monkeypatch, capsys):
    modes = []
    maps = iter([_power_map([32000] * 8), _power_map([55000] * 8)])
    monkeypatch.setattr(p16ctl, "platform", lambda: {
        "vendor": "ASUSTeK COMPUTER INC.",
        "product": "ProArt P16 H7607BA",
        "board": "H7607BA",
        "bios": "H7607BA.303",
        "acpi_call": True,
    })
    monkeypatch.setattr(p16ctl, "apply_mode", lambda mode, **kwargs: modes.append(mode))
    monkeypatch.setattr(p16ctl, "read_power", lambda: next(maps))
    monkeypatch.setattr(p16ctl.time, "sleep", lambda _seconds: None)

    assert p16ctl.verify() == 0
    assert modes == ["balanced", "performance", "balanced"]
    assert "PASS" in capsys.readouterr().out


def test_verify_fails_when_ec_limits_do_not_change(monkeypatch, capsys):
    modes = []
    power = _power_map([32000] * 8)
    monkeypatch.setattr(p16ctl, "platform", lambda: {
        "vendor": "ASUSTeK COMPUTER INC.",
        "product": "ProArt P16 H7607BA",
        "board": "H7607BA",
        "bios": "H7607BA.303",
        "acpi_call": True,
    })
    monkeypatch.setattr(p16ctl, "apply_mode", lambda mode, **kwargs: modes.append(mode))
    monkeypatch.setattr(p16ctl, "read_power", lambda: power)
    monkeypatch.setattr(p16ctl.time, "sleep", lambda _seconds: None)

    assert p16ctl.verify() == 1
    assert modes == ["balanced", "performance", "balanced"]
    assert "FAIL" in capsys.readouterr().out


def test_decode_power_known_offsets():
    data = bytearray(0x1000)
    for index in range(8):
        for offset, value in zip((0x100, 0x120, 0x140, 0x160), (1000, 2000, 3000, 4000)):
            data[offset + index * 4:offset + index * 4 + 4] = (value + index).to_bytes(4, "little")
    for index in range(4):
        data[0x708 + index * 0x10:0x708 + index * 0x10 + 4] = (100).to_bytes(4, "little")
        data[0x70C + index * 0x10:0x70C + index * 0x10 + 4] = (250000).to_bytes(4, "little")
    data[0x048:0x04C] = (0x10).to_bytes(4, "little")
    data[0x04C:0x050] = (1).to_bytes(4, "little")
    data[0x804:0x808] = (54900).to_bytes(4, "little")
    data[0x814:0x818] = (129999).to_bytes(4, "little")

    report = p16ctl.decode_power(bytes(data))
    assert report["slots"]["PL1"] == {
        "os_mw": 1000,
        "ec_mw": 2000,
        "uefi_mw": 3000,
        "effective_mw": 4000,
    }
    assert report["slots"]["SYSPL4"]["effective_mw"] == 4007
    assert report["bounds"]["SYSPL2"] == {"min_mw": 100, "max_mw": 250000}
    assert report["controller"] == 0x10
    assert report["package_mw"] == 54900
    assert report["system_mw"] == 129999


def test_decode_recorded_p16_spbm_idle_values():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "p16-spbm-idle.json").read_text()
    )
    data = bytearray(0x1000)
    for offset, value in fixture["registers"].items():
        index = int(offset, 16)
        data[index:index + 4] = int(value).to_bytes(4, "little")
    report = p16ctl.decode_power(bytes(data))
    assert report["slots"]["PL1"]["ec_mw"] == 55000
    assert report["slots"]["SYSPL1"]["ec_mw"] == 131000
    assert report["slots"]["SYSPL4"]["ec_mw"] == 180000
    assert report["package_mw"] == 22771
    assert report["system_mw"] == 52375


def test_cli_rejects_unknown_mode(capsys):
    with pytest.raises(SystemExit) as error:
        p16ctl.main(["turbo"])
    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_wrapper_is_executable():
    wrapper = Path(__file__).parent.parent / "p16ctl"
    assert wrapper.is_file()
    assert wrapper.stat().st_mode & 0o111
