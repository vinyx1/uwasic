"""reg_file tests: parallel load. See helpers.py for the behaviour under test."""

import cocotb

from helpers import (
    tick,
    initialize,
    mask,
    pack_vec3,
    write,
    load,
    check_all,
    fill_unique,
)


@cocotb.test()
async def load_maps_correctly(dut):
    """u.x/y/z -> R0/R1/R2 and v.x/y/z -> R3/R4/R5, in a single cycle."""
    await initialize(dut)
    m = mask(dut)
    u = (0x01 & m, 0x02 & m, 0x03 & m)
    v = (0x04 & m, 0x05 & m, 0x06 & m)
    await load(dut, u, v)
    await check_all(dut, [*u, *v, 0, 0])


@cocotb.test()
async def load_preserves_r6_r7(dut):
    """Parallel load leaves R6 and R7 unchanged."""
    await initialize(dut)
    m = mask(dut)
    await write(dut, 6, 0x66 & m)
    await write(dut, 7, 0x77 & m)
    u = (0x10 & m, 0x20 & m, 0x30 & m)
    v = (0x40 & m, 0x50 & m, 0x60 & m)
    await load(dut, u, v)
    await check_all(dut, [*u, *v, 0x66 & m, 0x77 & m])


@cocotb.test()
async def load_low_does_nothing(dut):
    """load_u/load_v are ignored while load is low."""
    await initialize(dut)
    model = await fill_unique(dut)
    m = mask(dut)
    dut.load.value = 0
    dut.load_u.value = pack_vec3(dut, m, m, m)
    dut.load_v.value = pack_vec3(dut, m, m, m)
    await tick(dut)
    await check_all(dut, model)


@cocotb.test()
async def consecutive_loads(dut):
    """Two loads in a row: the second overwrites the first."""
    await initialize(dut)
    m = mask(dut)
    u2 = (0xB1 & m, 0xB2 & m, 0xB3 & m)
    v2 = (0xB4 & m, 0xB5 & m, 0xB6 & m)
    dut.load.value = 1
    dut.load_u.value = pack_vec3(dut, 0xA1 & m, 0xA2 & m, 0xA3 & m)
    dut.load_v.value = pack_vec3(dut, 0xA4 & m, 0xA5 & m, 0xA6 & m)
    await tick(dut)
    dut.load_u.value = pack_vec3(dut, *u2)
    dut.load_v.value = pack_vec3(dut, *v2)
    await tick(dut)
    dut.load.value = 0
    await check_all(dut, [*u2, *v2, 0, 0])
