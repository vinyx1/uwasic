"""reg_file tests: reset. See helpers.py for the behaviour under test."""

import cocotb
from cocotb.triggers import Timer

from helpers import (
    CLOCK_PERIOD_NS,
    NUM_REGS,
    tick,
    initialize,
    mask,
    pack_vec3,
    write,
    load,
    reset,
    check_port,
    check_all,
    fill_unique,
)


@cocotb.test()
async def reset_clears_all(dut):
    """Reset clears every register and result to zero."""
    await initialize(dut)
    await check_all(dut, [0] * NUM_REGS)

    await fill_unique(dut)
    await reset(dut)
    await check_all(dut, [0] * NUM_REGS)


@cocotb.test()
async def reset_mid_operation(dut):
    """Reset in the middle of activity clears everything; operation then resumes."""
    await initialize(dut)
    m = mask(dut)
    await load(dut, (1, 2, 3), (4, 5, 6))
    await write(dut, 6, 0x77 & m)

    await reset(dut)
    await check_all(dut, [0] * NUM_REGS)

    await write(dut, 7, 0x42 & m)
    await check_port(dut, 1, 7, 0x42 & m)


@cocotb.test()
async def reset_is_synchronous(dut):
    """rst_n low with no rising edge leaves registers unchanged; the edge clears them."""
    await initialize(dut)
    model = await fill_unique(dut)

    dut.rst_n.value = 0
    await Timer(CLOCK_PERIOD_NS * 2, unit="ns")  # clk held low, no edge
    await check_all(dut, model)

    await tick(dut)
    dut.rst_n.value = 1
    await check_all(dut, [0] * NUM_REGS)


@cocotb.test()
async def reset_beats_load_and_wen(dut):
    """With rst_n low, load and wen are ignored."""
    await initialize(dut)
    m = mask(dut)
    dut.rst_n.value = 0
    dut.load.value = 1
    dut.load_u.value = pack_vec3(dut, m, m, m)
    dut.load_v.value = pack_vec3(dut, m, m, m)
    dut.wen.value = 1
    dut.waddr.value = 7
    dut.wdata.value = m
    await tick(dut)
    dut.load.value = 0
    dut.wen.value = 0
    dut.rst_n.value = 1
    await check_all(dut, [0] * NUM_REGS)
