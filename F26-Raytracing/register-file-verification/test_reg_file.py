"""reg_file tests. See helpers.py for the behaviour under test.

Run in either load variant (REG_FILE_LOAD=single|multi, set by run.py). Tests
that only make sense for the multicycle load are skipped in single mode.
"""

import random

import cocotb
from cocotb.triggers import Timer

from helpers import (
    CLOCK_PERIOD_NS,
    LOAD_CYCLES,
    LOAD_MODE,
    LOAD_PAIRS,
    NUM_REGS,
    settle,
    tick,
    initialize,
    wlen,
    mask,
    edge_values,
    pack_vec3,
    unpack_vec3,
    write,
    load,
    reset,
    check_port,
    check_result,
    check_all,
    fill_unique,
)

multi_only = cocotb.test(skip=LOAD_MODE != "multi")


# --- reset -------------------------------------------------------------------


@cocotb.test()
async def reset_clears_all(dut):
    """Reset clears every register and result to zero."""
    await initialize(dut)
    await check_all(dut, [0] * NUM_REGS)

    await fill_unique(dut)
    await reset(dut)
    await check_all(dut, [0] * NUM_REGS)


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
    for _ in range(LOAD_CYCLES):
        await tick(dut)
    dut.load.value = 0
    dut.wen.value = 0
    dut.rst_n.value = 1
    await check_all(dut, [0] * NUM_REGS)


# --- write port --------------------------------------------------------------


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


# --- read ports and result ---------------------------------------------------


@cocotb.test()
async def ports_independent(dut):
    """Every (raddr1, raddr2) pair, including the same register, reads correctly.

    Reads are combinational: no clock edge occurs between address changes.
    """
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
async def result_tracks_r0_r2_only(dut):
    """result is {R2, R1, R0}: writing one of them changes only that component."""
    await initialize(dut)
    m = mask(dut)
    model = await fill_unique(dut)
    await check_result(dut, model[0:3])

    for address in range(3):
        model[address] = (0xE0 + address) & m
        await write(dut, address, model[address])
        await check_result(dut, model[0:3])

    for address in range(3, NUM_REGS):
        await write(dut, address, m)
    await check_result(dut, model[0:3])


# --- load --------------------------------------------------------------------


@cocotb.test()
async def load_maps_correctly(dut):
    """u.x/y/z -> R0/R1/R2, v.x/y/z -> R3/R4/R5; R6 and R7 keep their values."""
    await initialize(dut)
    m = mask(dut)
    await write(dut, 6, 0x66 & m)
    await write(dut, 7, 0x77 & m)
    u = (0x01 & m, 0x02 & m, 0x03 & m)
    v = (0x04 & m, 0x05 & m, 0x06 & m)
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
    for _ in range(LOAD_CYCLES + 1):
        await tick(dut)
    await check_all(dut, model)


@cocotb.test()
async def back_to_back_loads(dut):
    """A second load replaces R0-R5 but keeps R6/R7 scratch values."""
    await initialize(dut)
    m = mask(dut)
    await load(dut, (1, 2, 3), (4, 5, 6))
    await write(dut, 6, 0x5A & m)
    await write(dut, 0, 0x77 & m)
    await check_result(dut, (0x77 & m, 2, 3))

    await load(dut, (7, 8, 9), (10, 11, 12))
    await check_all(dut, [7, 8, 9, 10, 11, 12, 0x5A & m, 0])


@cocotb.test()
async def load_priority_over_write(dut):
    """load and wen in the same cycle: load wins and the write is dropped, even to R6/R7.

    wen stays high for the whole load, so in multi mode this covers every cycle.
    """
    await initialize(dut)
    m = mask(dut)
    u = (0x21 & m, 0x22 & m, 0x23 & m)
    v = (0x24 & m, 0x25 & m, 0x26 & m)
    for address in range(NUM_REGS):
        await reset(dut)
        dut.wen.value = 1
        dut.waddr.value = address
        dut.wdata.value = 0xFF & m
        await load(dut, u, v)
        dut.wen.value = 0
        await check_all(dut, [*u, *v, 0, 0])


# --- no bypass ---------------------------------------------------------------


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
    """Before the first edge, a pending load is not visible on the read ports or result."""
    await initialize(dut)
    m = mask(dut)
    model = await fill_unique(dut)
    dut.load.value = 1
    dut.load_u.value = pack_vec3(dut, m, m, m)
    dut.load_v.value = pack_vec3(dut, m, m, m)
    await check_all(dut, model)  # clk still low
    dut.load.value = 0


# --- data edge values --------------------------------------------------------


@cocotb.test()
async def edge_values_write_and_load(dut):
    """Corner-case data patterns survive the write port (R0-R7) and the load (R0-R5)."""
    await initialize(dut)
    for value in edge_values(dut):
        for address in range(NUM_REGS):
            await write(dut, address, value)
        await check_all(dut, [value] * NUM_REGS)

        await reset(dut)
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
            model[address] = one  # other registers must not be modified
            await check_all(dut, model)

            await write(dut, address, zero)
            model[address] = zero
            await check_all(dut, model)


# --- randomized against a model ----------------------------------------------


@cocotb.test()
async def random_against_model(dut):
    """Random load/write/read/reset traffic checked every cycle against a model."""
    await initialize(dut)
    m = mask(dut)
    model = [0] * NUM_REGS

    for cycle in range(1000):
        if random.random() < 0.15:
            u = tuple(random.randint(0, m) for _ in range(3))
            v = tuple(random.randint(0, m) for _ in range(3))
            await load(dut, u, v)
            model[0:6] = [*u, *v]
            await check_all(dut, model)
            continue

        do_reset = random.random() < 0.01
        do_write = random.random() < 0.6
        waddr = random.randrange(NUM_REGS)
        wdata = random.randint(0, m)
        raddr1 = random.randrange(NUM_REGS)
        raddr2 = random.randrange(NUM_REGS)

        dut.rst_n.value = 0 if do_reset else 1
        dut.wen.value = int(do_write)
        dut.waddr.value = waddr
        dut.wdata.value = wdata
        dut.raddr1.value = raddr1
        dut.raddr2.value = raddr2
        await settle()

        # Before the edge: reads reflect the current state (no bypass).
        r1 = int(dut.rdata1.value)
        r2 = int(dut.rdata2.value)
        res = unpack_vec3(dut, int(dut.result.value))
        assert r1 == model[raddr1], (
            f"cycle {cycle}: rdata1 R{raddr1} expected 0x{model[raddr1]:x}, got 0x{r1:x}"
        )
        assert r2 == model[raddr2], (
            f"cycle {cycle}: rdata2 R{raddr2} expected 0x{model[raddr2]:x}, got 0x{r2:x}"
        )
        assert res == tuple(model[0:3]), (
            f"cycle {cycle}: result expected {model[0:3]}, got {list(res)}"
        )

        await tick(dut)

        if do_reset:
            model = [0] * NUM_REGS
        elif do_write:
            model[waddr] = wdata

    dut.rst_n.value = 1
    dut.wen.value = 0
    await check_all(dut, model)


# --- realistic sequence ------------------------------------------------------


@cocotb.test()
async def vector_macro_op_sequence(dut):
    """Act as decode + FU Control: load u, v; micro-ops read sources and write
    results; decode reads result.

    Models u + v computed one component at a time, using R6 as scratch:
    R6 <- R0 + R3, R0 <- R6, and so on.
    """
    await initialize(dut)
    m = mask(dut)
    u = (3, 5, 7)
    v = (10, 20, 30)
    await load(dut, u, v)

    for i in range(3):
        dut.raddr1.value = i
        dut.raddr2.value = i + 3
        await settle()
        a = int(dut.rdata1.value)
        b = int(dut.rdata2.value)
        assert (a, b) == (u[i], v[i])
        await write(dut, 6, (a + b) & m)

        dut.raddr1.value = 6
        await settle()
        await write(dut, i, int(dut.rdata1.value))

    await check_result(dut, tuple((u[i] + v[i]) & m for i in range(3)))
    await check_port(dut, 1, 6, (u[2] + v[2]) & m)
    await check_port(dut, 1, 7, 0)


# --- multicycle load only ----------------------------------------------------


@multi_only
async def multiload_partial_states(dut):
    """Each load cycle writes only its pair of registers; the rest keep old values."""
    await initialize(dut)
    m = mask(dut)
    model = await fill_unique(dut)
    u = (0xA1 & m, 0xA2 & m, 0xA3 & m)
    v = (0xB1 & m, 0xB2 & m, 0xB3 & m)
    words = [*u, *v]

    dut.load.value = 1
    dut.load_u.value = pack_vec3(dut, *u)
    dut.load_v.value = pack_vec3(dut, *v)
    for cycle, pair in enumerate(LOAD_PAIRS):
        await tick(dut)
        for index in pair:
            model[index] = words[index]
        await check_all(dut, model)  # includes result and R6/R7
    dut.load.value = 0
    await check_all(dut, model)


@multi_only
async def multiload_reset_mid_load(dut):
    """Reset between load cycles clears everything, and the load does not resume."""
    await initialize(dut)
    m = mask(dut)
    u = (0xA1 & m, 0xA2 & m, 0xA3 & m)
    v = (0xB1 & m, 0xB2 & m, 0xB3 & m)
    for reset_after in range(1, LOAD_CYCLES):
        await fill_unique(dut)
        dut.load.value = 1
        dut.load_u.value = pack_vec3(dut, *u)
        dut.load_v.value = pack_vec3(dut, *v)
        for _ in range(reset_after):
            await tick(dut)

        await reset(dut)  # load still high
        dut.load.value = 0
        await tick(dut)
        await check_all(dut, [0] * NUM_REGS)


@multi_only
async def multiload_write_after_load_completes(dut):
    """A write on the cycle right after the last load cycle is accepted normally."""
    await initialize(dut)
    m = mask(dut)
    u = (1, 2, 3)
    v = (4, 5, 6)
    await load(dut, u, v)
    await write(dut, 0, 0x99 & m)  # R0 was loaded in cycle 1
    await write(dut, 5, 0x98 & m)  # R5 was loaded in the last cycle
    await check_all(dut, [0x99 & m, 2, 3, 4, 5, 0x98 & m, 0, 0])
