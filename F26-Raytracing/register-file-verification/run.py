"""pytest entry point: builds RTL and launches the cocotb tests."""

import os
from pathlib import Path

import pytest
from cocotb_tools.runner import get_runner

ROOT = Path(__file__).resolve().parents[1]


def test_reg_file():
    # Change these filenames if the actual project uses different names.
    sources = [
        ROOT / "rtl" / "tinytracer_pkg.sv",
        ROOT / "rtl" / "reg_file.sv",
    ]
    missing = [str(p.relative_to(ROOT)) for p in sources if not p.exists()]
    if missing:
        pytest.skip("RTL not yet available: " + ", ".join(missing))

    runner = get_runner(os.getenv("SIM", "verilator"))
    runner.build(
        sources=sources,  # package comes before module
        hdl_toplevel="reg_file",
        build_dir=ROOT / "sim_build",
        always=True,
    )
    runner.test(
        hdl_toplevel="reg_file",
        test_module="test_reg_file",
        test_dir=ROOT / "tests",
    )
