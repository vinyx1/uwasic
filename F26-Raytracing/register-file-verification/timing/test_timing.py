"""reg_file tests: timing and hazards. See helpers.py for the behaviour under test."""

import cocotb

from helpers import (
    NUM_REGS,
    settle,
    tick,
    initialize,
    mask,
    pack_vec3,
    unpack_vec3,
    write,
    load,
    reset,
    check_all,
    fill_unique,
)


@cocotb.test()
async def write_visible_next_cycle(dut):
    """A value written on an edge is readable immediately after that edge."""
    await initialize(dut)
    m = mask(dut)
    dut.raddr1.value = 5
    dut.raddr2.value = 5
    await write(dut, 5, 0x3C & m)
    assert int(dut.rdata1.value) == 0x3C & m
    assert int(dut.rdata2.value) == 0x3C & m


@cocotb.test()
async def read_during_write_returns_old(dut):
    """No bypass: before the edge, reading the register being written gives the old value."""
    await initialize(dut)
    m = mask(dut)
    old, new = 0x11 & m, 0xEE & m
    for address in (0, 3, NUM_REGS - 1):
        await write(dut, address, old)

        dut.wen.value = 1
        dut.waddr.value = address
        dut.wdata.value = new
        dut.raddr1.value = address
        dut.raddr2.value = address
        await settle()  # clk still low: write is pending
        assert int(dut.rdata1.value) == old, f"R{address}: rdata1 bypassed wdata"
        assert int(dut.rdata2.value) == old, f"R{address}: rdata2 bypassed wdata"
        if address == 0:
            assert unpack_vec3(dut, int(dut.result.value))[0] == old, (
                "result.x bypassed wdata"
            )

        await tick(dut)
        dut.wen.value = 0
        await settle()
        assert int(dut.rdata1.value) == new
        assert int(dut.rdata2.value) == new


@cocotb.test()
async def read_during_load_returns_old(dut):
    """Before the edge, a pending load is not visible on the read ports or result."""
    await initialize(dut)
    m = mask(dut)
    model = await fill_unique(dut)
    dut.load.value = 1
    dut.load_u.value = pack_vec3(dut, m, m, m)
    dut.load_v.value = pack_vec3(dut, m, m, m)
    await check_all(dut, model)  # clk still low
    dut.load.value = 0


@cocotb.test()
async def load_priority_over_write(dut):
    """load and wen in the same cycle: load wins and the write is dropped, even to R6/R7."""
    await initialize(dut)
    m = mask(dut)
    u = (0x21 & m, 0x22 & m, 0x23 & m)
    v = (0x24 & m, 0x25 & m, 0x26 & m)
    for address in range(NUM_REGS):
        await reset(dut)
        dut.load.value = 1
        dut.load_u.value = pack_vec3(dut, *u)
        dut.load_v.value = pack_vec3(dut, *v)
        dut.wen.value = 1
        dut.waddr.value = address
        dut.wdata.value = 0xFF & m
        await tick(dut)
        dut.load.value = 0
        dut.wen.value = 0
        await check_all(dut, [*u, *v, 0, 0])
