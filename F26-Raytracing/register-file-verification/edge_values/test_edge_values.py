"""reg_file tests: data edge values. See helpers.py for the behaviour under test."""

import cocotb

from helpers import (
    NUM_REGS,
    initialize,
    wlen,
    mask,
    edge_values,
    write,
    load,
    check_port,
    check_all,
)


@cocotb.test()
async def edge_values_write_port(dut):
    """Corner-case data patterns survive the write port on every register."""
    await initialize(dut)
    for value in edge_values(dut):
        for address in range(NUM_REGS):
            await write(dut, address, value)
        await check_all(dut, [value] * NUM_REGS)


@cocotb.test()
async def edge_values_load(dut):
    """Corner-case data patterns survive the parallel load on R0-R5."""
    await initialize(dut)
    for value in edge_values(dut):
        await load(dut, (value,) * 3, (value,) * 3)
        await check_all(dut, [value] * 6 + [0, 0])


@cocotb.test()
async def walking_bits(dut):
    """Walking one and walking zero across all WLEN bits (stuck/shorted bits)."""
    await initialize(dut)
    m = mask(dut)
    model = [0] * NUM_REGS

    for bit in range(wlen(dut)):
        one = 1 << bit
        zero = (~one) & m

        for address in range(NUM_REGS):
            await write(dut, address, one)
            model[address] = one #c
            await check_all(dut, model)

            await write(dut, address, zero)
            model[address] = zero
            await check_all(dut, model)
