import shutil
import subprocess
from pathlib import Path

import pytest


def test_wmnb_deves_buffer_sets_mode_and_dsts_is_constant(tmp_path):
    iasl = shutil.which("iasl")
    acpiexec = shutil.which("acpiexec")
    if not iasl or not acpiexec:
        pytest.skip("iasl and acpiexec are not installed")

    asl = Path(__file__).parent / "fixtures" / "asus_wmnb.asl"
    prefix = tmp_path / "asus_wmnb"
    compiled = subprocess.run(
        [iasl, "-p", str(prefix), str(asl)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    aml = prefix.with_suffix(".aml")
    assert aml.is_file()

    command = (
        r"execute \_SB.ATKD.TEST;"
        r"execute \_SB.ATKD.LAST;"
        r"execute \_SB.ATKD.TS2;"
        r"execute \_SB.ATKD.LAST;"
        r"execute \_SB.ATKD.WMNB 0 0x53545344 "
        r"{0x75,0x00,0x12,0x00,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0}"
    )
    run = subprocess.run(
        [acpiexec, "-b", command, str(aml)],
        check=False,
        capture_output=True,
        text=True,
    )
    output = run.stdout + run.stderr
    assert "Evaluation of \\_SB.ATKD.TEST returned" in output
    assert output.count("[Integer] = 0000000000000001") >= 2
    assert output.count("[Integer] = 0000000000000002") == 1
    assert "[Integer] = 0000000000010003" in output
