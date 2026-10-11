"""reg_file tests: result output. See helpers.py for the behaviour under test."""

import cocotb

from helpers import (
    NUM_REGS,
    tick,
    initialize,
    mask,
    write,
    load,
    check_result,
    fill_unique,
)


@cocotb.test()
async def result_is_r2_r1_r0(dut):
    """result.x/y/z mirror R0/R1/R2 after writes through the write port."""
    await initialize(dut)
    m = mask(dut)
    await write(dut, 0, 0x0A & m)
    await write(dut, 1, 0x0B & m)
    await write(dut, 2, 0x0C & m)
    await check_result(dut, (0x0A & m, 0x0B & m, 0x0C & m))


@cocotb.test()
async def result_tracks_single_writes(dut):
    """Writing one of R0-R2 changes only that component; R3-R7 don't affect result."""
    await initialize(dut)
    m = mask(dut)
    model = await fill_unique(dut)

    await write(dut, 1, 0xEE & m)
    model[1] = 0xEE & m
    await check_result(dut, model[0:3])

    for address in range(3, NUM_REGS):
        await write(dut, address, m)
    await check_result(dut, model[0:3])


@cocotb.test()
async def scalar_result_in_r0(dut):
    """Scalar macro-op: load, then R0 written at least one cycle later -> result.x."""
    await initialize(dut)
    m = mask(dut)
    await load(dut, (1, 2, 3), (4, 5, 6))
    await tick(dut)  # micro-op in flight
    await write(dut, 0, 0x99 & m)
    await check_result(dut, (0x99 & m, 2, 3))
