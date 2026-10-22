# F26-Raytracing (UW ASIC, TinyTracer)

Verilog/SystemVerilog raytracing accelerator ("TinyTracer"). Docs: https://uw-asic.github.io/TinyTracer/ (module pages under `modules/`, e.g. `modules/exu/reg_file/`). The docs are the source of truth for behavior; if RTL or tests disagree with them, say so rather than silently picking one.

The user may be assigned different modules over time. Don't assume the current task is `reg_file`; check what they ask for.

## Chip architecture

Source: block diagram supplied by the user. Block and signal names below come from it. Descriptions of what a block *does* are inferred from names and wiring unless the docs say otherwise; verify on the docs site before relying on them.

Five regions:

- **I/O**: UART and a clock divider. Receives the `render` command and scene upload data (`obj_data`, to the SRAM mux); sends finished pixels out (`pixel_colour` from the accumulator).
- **SRAM**: SRAM Mux plus Scene Data (512 x 16). The mux arbitrates between `obj_data` writes from I/O and `sram_addr` reads from the Ray Tracing Unit; `sram_req` goes to the scene memory and `sram_word` comes back to the Header Registers and the Request Path.
- **Ray Tracing Unit (RTU)**: the per-ray control and datapath.
  - **Controller**: takes `render` from I/O, pulses `load` to the Header Registers and `start` to the Ray Generator, and sends `spp_log2` (log2 samples per pixel) to the accumulator's Bit Shifter.
  - **Header Registers**: scene header data loaded from SRAM; feed the Request Path and drive `sram_addr`.
  - **Ray Generator** (with **RNG**), **Intersection Unit** and **Shader Core**: the three clients that issue `request`s to the Request Path and get a `flag` back. Each also has a two-way link to the Ray State Registers.
  - **Ray State Registers**: per-ray state shared by those three units. Sends `sample` to the accumulator's Sample Buffer. Supplies `operands` to the Request Path and receives `results`.
  - **Request Path**: arbitrates and prepares requests: Operand Select, Size Shifter, Sign Flip and a Request Register. Also reads `sram_word`. Emits `macroop_req` to the Execution Unit and receives `macroop_resp`.
- **Execution Unit (EXU)**: executes macro-ops.
  - **Decode** (with **uOp ROM**): accepts a `macroop_req`, loads operands `u`, `v` into the Register File in one cycle, expands the macro-op into micro-ops (`uOp`, `fmt`) for FU Control, collects `done`, reads `result` from the Register File, and returns `macroop_resp`.
  - **Register File**: operand and intermediate storage (see below).
  - **FU Control**: issues micro-ops to the functional units using the Register File's read ports and write port; sends `request` to the functional units and gets `result` back.
  - **Functional Units**: ALU, Multiplier, CORDIC (with a LUT).
- **Accumulator**: **Sample Buffer** collects `sample`s from the Ray State Registers; **Bit Shifter** scales the accumulated sum by `spp_log2` (a shift in place of a divide) and sends `pixel_colour` to I/O.

Dataflow in one line: UART `render` -> Controller -> Ray Generator/Intersection/Shader (via Request Path) -> macro-ops to the EXU -> FUs -> results back to Ray State Registers -> samples to the Accumulator -> `pixel_colour` out over UART.

## Layout

- `register-file-verification/reg_file_tb.py`: the whole reg_file testbench (spec notes, helpers, cocotb tests, pytest entry point) in one file.
- Expected RTL (not in this repo yet): `rtl/tinytracer_pkg.sv`, `rtl/reg_file.sv`, relative to this directory. The pytest entry point skips if they are missing; edit `sources` there if the real paths differ.
- `.vsetup`: environment setup; check it before assuming tool versions.

## Module: reg_file (EXU Register File)

Eight `WLEN`-bit registers R0-R7 (WLEN default 16). One write port, two combinational read ports, combinational `result = {R2, R1, R0}`. Decode uses the parallel load and `result`; FU Control uses the write and read ports; they never access it in the same cycle. Parallel load puts u.{x,y,z} in R0-R2 and v.{x,y,z} in R3-R5, leaving R6/R7 alone. No write-to-read bypass. Load beats a same-cycle write. Full spec: docs page `modules/exu/reg_file/`.

Run its tests:

```
cd register-file-verification
pytest reg_file_tb.py            # both load variants
pytest reg_file_tb.py -k multi   # one variant
```

Verilator by default (`SIM=<name>` to override), via the cocotb runner. pytest builds the RTL, then cocotb imports the same file as `reg_file_tb` and runs only the cocotb tests. Tests are WLEN-agnostic. Test function names must not start with `test` or pytest will try to collect them.

The tests assume things the docs do not state; confirm against the RTL before treating them as requirements: reset is **synchronous**; a write dropped by load priority is dropped **entirely** (including R6/R7); `vec3_t` is 3 x WLEN with x in the low bits.

**Multicycle load.** Someone mentioned single-cycle vs multicycle load ("2 words instead of 6"). The user later clarified that the Decode Unit manages it: `load` stays high for 3 cycles and Decode presents pair 1, then pair 2, then pair 3 (one pair per cycle, nothing captured up front). The docs page still describes only the single-cycle load. The tests cover both via `REG_FILE_LOAD=single|multi`; `drive_load_cycle` and `LOAD_PAIRS = [(0,3),(1,4),(2,5)]` in `reg_file_tb.py` hold the convention.

Still guessed, not confirmed: the pairing/order, which port lanes a pair's words occupy (tests assume u[k] on `load_u` lane k and v[k] on `load_v` lane k, with the other lanes driven to a deliberately wrong value), whether the variant is a separate RTL file or a parameter, and early-drop behavior (untested). Update those two spots and this note once known.

## Conventions

- Match the existing style in `reg_file_tb.py`: helpers at the top, tests under section comments, short docstrings.
- Prefer deleting redundant tests over adding overlapping ones.
