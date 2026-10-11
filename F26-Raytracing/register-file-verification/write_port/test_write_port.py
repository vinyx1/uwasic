"""reg_file tests: write port. See helpers.py for the behaviour under test."""

import cocotb

from helpers import (
    NUM_REGS,
    tick,
    initialize,
    mask,
    write,
    check_port,
    check_all,
    fill_unique,
)


@cocotb.test()
async def write_and_read_all_registers(dut):
    """Each of the eight registers accepts a write; two ports read independently."""
    await initialize(dut)
    m = mask(dut)
    values = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]
    for address, value in enumerate(values):
        await write(dut, address, value & m)

    last = NUM_REGS - 1
    for address, value in enumerate(values):
        await check_port(dut, 1, address, value & m)
        await check_port(dut, 2, last - address, values[last - address] & m)


@cocotb.test()
async def write_enable_blocks_changes(dut):
    """wen=0 must leave an already initialized register unchanged."""
    await initialize(dut)
    m = mask(dut)
    for address in (0, 2, NUM_REGS - 1):
        await write(dut, address, 0xA5 & m)
        dut.wen.value = 0
        dut.waddr.value = address
        dut.wdata.value = 0x5A & m
        await tick(dut)
        await check_port(dut, 1, address, 0xA5 & m)
        await check_port(dut, 2, address, 0xA5 & m)


@cocotb.test()
async def write_only_target_changes(dut):
    """Writing one register leaves the other seven untouched (address decode)."""
    await initialize(dut)
    m = mask(dut)
    model = await fill_unique(dut)
    for address in range(NUM_REGS):
        model[address] = (~model[address]) & m
        await write(dut, address, model[address])
        await check_all(dut, model)


@cocotb.test()
async def overwrite_same_register(dut):
    """Back-to-back writes to the same register: the last one wins."""
    await initialize(dut)
    m = mask(dut)
    dut.wen.value = 1
    dut.waddr.value = 4
    for value in (0x01, 0x02, 0x03):
        dut.wdata.value = value & m
        await tick(dut)
    dut.wen.value = 0
    await check_port(dut, 1, 4, 0x03 & m)


@cocotb.test()
async def back_to_back_writes(dut):
    """A different register is written on every cycle with no idle cycles."""
    await initialize(dut)
    m = mask(dut)
    model = [(0xC0 + i) & m for i in range(NUM_REGS)]
    dut.wen.value = 1
    for address, value in enumerate(model):
        dut.waddr.value = address
        dut.wdata.value = value
        await tick(dut)
    dut.wen.value = 0
    await check_all(dut, model)
