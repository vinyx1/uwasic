# F26-Raytracing (UW ASIC, TinyTracer)

Verilog/SystemVerilog raytracing accelerator ("TinyTracer"). Docs: https://uw-asic.github.io/TinyTracer/ (module pages live under `modules/`, e.g. `modules/exu/reg_file/`). The docs are the source of truth for behavior; if the RTL or tests disagree, say so rather than silently picking one.

## Layout

- `register-file-verification/reg_file_tb.py` is the whole reg_file testbench: spec notes, helpers, cocotb tests and the pytest entry point, all in one file.
- Expected RTL (not in this repo yet): `rtl/tinytracer_pkg.sv` and `rtl/reg_file.sv`, relative to this directory. The pytest entry point skips if they are missing; edit `sources` there if the real paths differ.
- `.vsetup` is environment setup; check it before assuming tool versions.

## Running the reg_file tests

```
cd register-file-verification
pytest reg_file_tb.py            # both load variants
pytest reg_file_tb.py -k multi   # one variant
```

Simulator is Verilator by default (`SIM=<name>` to override), via the cocotb runner. pytest builds the RTL, then cocotb imports the same file as `reg_file_tb` and runs only the cocotb tests. Tests are WLEN-agnostic (width read from `len(dut.wdata)`). Test function names must not start with `test` or pytest will try to collect them.

## reg_file spec (from the docs page)

- Eight `WLEN`-bit registers R0-R7 (WLEN default 16). One write port (`wen`, `waddr`, `wdata`), two combinational read ports (`raddr1/2` -> `rdata1/2`), combinational `result = {R2, R1, R0}`.
- Parallel load (`load` high): R0-R2 <- `load_u.{x,y,z}`, R3-R5 <- `load_v.{x,y,z}`; R6, R7 unchanged.
- No write-to-read bypass: reading a register in the cycle it is written returns the old value.
- `load` and a write in the same cycle: docs say this "should not occur"; if it does, load takes priority.
- Decode Unit uses load and `result`; FU Control uses the write and read ports. They never touch the register file in the same cycle.

## Assumptions the tests make that the docs do NOT state

Confirm against the RTL or the design owners before treating these as requirements:

- Reset is **synchronous** (docs only say `rst_n` low clears all registers).
- A write dropped by load priority is dropped **entirely**, including to R6/R7.
- `vec3_t` is 3 x WLEN, x in the low bits.

## Open question: multicycle load

Someone mentioned two load versions, single-cycle and multicycle ("2 words instead of 6"), with inputs unchanged. This is secondhand and not yet confirmed as a design change; the docs page still describes only the single-cycle load. The tests cover both via `REG_FILE_LOAD=single|multi` (set by the pytest entry point), with this guess:

- `load` and `load_u/load_v` are held for 3 cycles; cycle k writes the pair in `LOAD_PAIRS = [(0,3),(1,4),(2,5)]` (indices into `[*u, *v]`).

Unconfirmed: the pairing/order, whether `load` is held or pulsed once, whether the RTL variant is a separate file or a parameter (the pytest entry point builds the same sources for both), and what happens if `load` drops early (untested). Update `LOAD_PAIRS` and this section once known.

## Conventions

- Match the existing style in `reg_file_tb.py`: helper functions at the top, tests grouped under section comments, short docstrings.
- Prefer deleting redundant tests over adding overlapping ones.
