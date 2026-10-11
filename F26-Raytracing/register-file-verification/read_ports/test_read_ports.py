"""reg_file tests: read ports. See helpers.py for the behaviour under test."""

import random

import cocotb

from helpers import (
    NUM_REGS,
    settle,
    tick,
    initialize,
    fill_unique,
)


@cocotb.test()
async def ports_independent(dut):
    """Every (raddr1, raddr2) combination returns the right data on both ports."""
    await initialize(dut)
    model = await fill_unique(dut)
    for a1 in range(NUM_REGS):
        for a2 in range(NUM_REGS):
            dut.raddr1.value = a1
            dut.raddr2.value = a2
            await settle()
            r1 = int(dut.rdata1.value)
            r2 = int(dut.rdata2.value)
            assert r1 == model[a1], f"raddr1={a1}, raddr2={a2}: rdata1=0x{r1:x}"
            assert r2 == model[a2], f"raddr1={a1}, raddr2={a2}: rdata2=0x{r2:x}"


@cocotb.test()
async def both_ports_same_reg(dut):
    """Both ports may address the same register at once."""
    await initialize(dut)
    model = await fill_unique(dut)
    for address in range(NUM_REGS):
        dut.raddr1.value = address
        dut.raddr2.value = address
        await settle()
        assert int(dut.rdata1.value) == model[address]
        assert int(dut.rdata2.value) == model[address]


@cocotb.test()
async def reads_are_combinational(dut):
    """rdata follows raddr with no clock edge in between."""
    await initialize(dut)
    model = await fill_unique(dut)
    dut.clk.value = 0
    for address in random.sample(range(NUM_REGS), NUM_REGS):
        dut.raddr1.value = address
        dut.raddr2.value = (address + 1) % NUM_REGS
        await settle()  # no tick
        assert int(dut.rdata1.value) == model[address]
        assert int(dut.rdata2.value) == model[(address + 1) % NUM_REGS]
