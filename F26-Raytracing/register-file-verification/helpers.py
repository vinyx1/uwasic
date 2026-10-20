"""Shared constants and helpers for the reg_file cocotb tests.

Behaviour under test (from the register file spec):
- eight WLEN-bit registers, R0-R7
- parallel load: R0-R2 <- load_u.{x,y,z}, R3-R5 <- load_v.{x,y,z}; R6, R7 unchanged
- result = {R2, R1, R0}, combinational
- write port: wdata -> R[waddr] on the rising edge when wen is high
- read ports: rdata1/rdata2 are combinational reads of R[raddr1]/R[raddr2]
- no write-to-read bypass: a register being written returns its old value
  until after the edge
- load takes priority over a write in the same cycle; the write is dropped
  entirely, including writes to R6/R7
- reset is synchronous: rst_n low clears all registers to zero on the next
  rising edge
"""

import os

from cocotb.triggers import Timer

CLOCK_PERIOD_NS = 10  # One full clock cycle = 10 ns
NUM_REGS = 8

# Load variant under test, selected by run.py through REG_FILE_LOAD.
#   single: all six words are written on one edge.
#   multi:  load and load_u/load_v are held for LOAD_CYCLES cycles; each cycle
#           writes the two registers in the matching LOAD_PAIRS entry.
# ASSUMPTION (multi): the pairing and order below are unconfirmed. Edit
# LOAD_PAIRS if the RTL differs; indices are into the list [*u, *v].
LOAD_MODE = os.getenv("REG_FILE_LOAD", "single")
LOAD_PAIRS = [(0, 3), (1, 4), (2, 5)]
LOAD_CYCLES = len(LOAD_PAIRS) if LOAD_MODE == "multi" else 1


async def settle():
    await Timer(1, unit="ns")


async def tick(dut):
    """Generate one complete clock cycle (50% duty cycle)."""
    half_period = CLOCK_PERIOD_NS / 2

    dut.clk.value = 0
    await Timer(half_period, unit="ns")

    dut.clk.value = 1
    await Timer(half_period, unit="ns")

    dut.clk.value = 0


async def initialize(dut):
    # Start up the clock cycle
    dut.clk.value = 0
    dut.rst_n.value = 0
    dut.load.value = 0
    dut.load_u.value = 0
    dut.load_v.value = 0
    dut.wen.value = 0
    dut.waddr.value = 0
    dut.wdata.value = 0
    dut.raddr1.value = 0
    dut.raddr2.value = 0
    await tick(dut)
    dut.rst_n.value = 1
    await settle()


def wlen(dut):
    return len(dut.wdata)


def mask(dut):
    return (1 << wlen(dut)) - 1


def pack_vec3(dut, x, y, z):
    """Pack a vec3_t with x in the low bits, matching result = {R2, R1, R0}."""
    w = wlen(dut)
    return (z << (2 * w)) | (y << w) | x


def unpack_vec3(dut, value):
    w = wlen(dut)
    m = mask(dut)
    return value & m, (value >> w) & m, (value >> (2 * w)) & m


def edge_values(dut):
    """Corner-case data patterns sized to WLEN."""
    w = wlen(dut)
    m = mask(dut)
    alternating = int("10" * w, 2) >> w  # 0b1010... trimmed to WLEN bits
    return [
        0,
        1,
        m,                      # all ones
        1 << (w - 1),           # MSB / sign bit only
        m >> 1,                 # all ones except MSB (max positive)
        alternating & m,        # 1010...
        (~alternating) & m,     # 0101...
    ]


async def write(dut, address, data):
    dut.wen.value = 1
    dut.waddr.value = address
    dut.wdata.value = data
    await tick(dut)
    dut.wen.value = 0
    await settle()


async def load(dut, u, v):
    """Parallel load, held for LOAD_CYCLES cycles. u and v are (x, y, z) tuples."""
    dut.load.value = 1
    dut.load_u.value = pack_vec3(dut, *u)
    dut.load_v.value = pack_vec3(dut, *v)
    for _ in range(LOAD_CYCLES):
        await tick(dut)
    dut.load.value = 0
    await settle()


async def reset(dut):
    dut.rst_n.value = 0
    await tick(dut)
    dut.rst_n.value = 1
    await settle()


async def check_port(dut, port, address, expected):
    getattr(dut, f"raddr{port}").value = address
    await settle()
    actual = int(getattr(dut, f"rdata{port}").value)
    assert actual == expected, (
        f"port {port}: R{address} expected 0x{expected:x}, got 0x{actual:x}"
    )


async def check_result(dut, expected):
    """expected is the (R0, R1, R2) tuple."""
    await settle()
    actual = unpack_vec3(dut, int(dut.result.value))
    assert actual == tuple(expected), (
        "result (x, y, z) expected "
        f"({', '.join(hex(v) for v in expected)}), "
        f"got ({', '.join(hex(v) for v in actual)})"
    )


async def check_all(dut, model):
    """Check every register on both ports, plus result, against a model list."""
    for address in range(NUM_REGS):
        await check_port(dut, 1, address, model[address])
        await check_port(dut, 2, address, model[address])
    await check_result(dut, model[0:3])


async def fill_unique(dut):
    """Write a distinct nonzero value to every register; return the model."""
    m = mask(dut)
    model = [(0x10 + 0x11 * i) & m for i in range(NUM_REGS)]
    for address, value in enumerate(model):
        await write(dut, address, value)
    return model
