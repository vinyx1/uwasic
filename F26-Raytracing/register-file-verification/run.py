"""pytest entry point: builds RTL and launches the cocotb tests.

Each test section lives in its own directory. Run everything with
`pytest run.py`, or one section with e.g. `pytest run.py -k timing`.
"""

import os
from pathlib import Path

import pytest
from cocotb_tools.runner import get_runner

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent

SECTIONS = [
    "reset",
    "write_port",
    "read_ports",
    "parallel_load",
    "result",
    "timing",
    "edge_values",
    "random_model",
    "sequences",
]


@pytest.mark.parametrize("section", SECTIONS)
def test_reg_file(section):
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
        test_module=f"{section}.test_{section}",
        test_dir=TEST_DIR,  # on the path, so helpers.py is importable
    )
