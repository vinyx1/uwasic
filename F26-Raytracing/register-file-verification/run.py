"""pytest entry point: builds RTL and launches the cocotb tests.

All tests live in test_reg_file.py and run once per load variant. Run
everything with `pytest run.py`, or one variant with e.g. `pytest run.py -k multi`.
"""

import os
from pathlib import Path

import pytest
from cocotb_tools.runner import get_runner

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent

LOAD_MODES = ["single", "multi"]


@pytest.mark.parametrize("load_mode", LOAD_MODES)
def test_reg_file(load_mode):
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
        build_dir=ROOT / "sim_build" / load_mode,
        always=True,
    )
    runner.test(
        hdl_toplevel="reg_file",
        test_module="test_reg_file",
        test_dir=TEST_DIR,  # on the path, so helpers.py is importable
        extra_env={"REG_FILE_LOAD": load_mode},
    )
