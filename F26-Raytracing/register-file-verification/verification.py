"""Black-box cocotb tests for reg_file.

Behaviour under test (from the register file spec):
- eight WLEN-bit registers, R0-R7
- parallel load: R0-R2 <- load_u.{x,y,z}, R3-R5 <- load_v.{x,y,z}; R6, R7 unchanged
- result = {R2, R1, R0}, combinational
- write port: wdata -> R[waddr] on the rising edge when wen is high
- read ports: rdata1/rdata2 are combinational reads of R[raddr1]/R[raddr2]
- no write-to-read bypass: a register being written returns its old value
  until after the edge
- load takes priority over a write in the same cycle
- reset (rst_n low) clears all registers to zero

Open questions (not tested here):
- whether reset is synchronous or asynchronous; every reset below is
  applied across a clock edge, so either implementation passes
- whether load also blocks a same-cycle write to R6/R7
"""

import random

import cocotb
from cocotb.triggers import Timer

CLOCK_PERIOD_NS = 10  # One full clock cycle = 10 ns
NUM_REGS = 8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    """Parallel load. u and v are (x, y, z) tuples."""
    dut.load.value = 1
    dut.load_u.value = pack_vec3(dut, *u)
    dut.load_v.value = pack_vec3(dut, *v)
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


# ---------------------------------------------------------------------------
# 1. Reset
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 2. Write port
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 3. Read ports
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 4. Parallel load
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 5. Result output
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 6. Timing and hazards
# ---------------------------------------------------------------------------


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
    """load and wen in the same cycle: load wins for R0-R5."""
    await initialize(dut)
    m = mask(dut)
    u = (0x21 & m, 0x22 & m, 0x23 & m)
    v = (0x24 & m, 0x25 & m, 0x26 & m)
    for address in range(6):
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


# ---------------------------------------------------------------------------
# 7. Data edge values
# ---------------------------------------------------------------------------


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
    for bit in range(wlen(dut)):
        one = 1 << bit
        zero = (~one) & m
        for address in range(NUM_REGS):
            await write(dut, address, one)
            await check_port(dut, 1, address, one)
            await write(dut, address, zero)
            await check_port(dut, 2, address, zero)


# ---------------------------------------------------------------------------
# 8. Randomized with reference model
# ---------------------------------------------------------------------------


@cocotb.test()
async def random_against_model(dut):
    """Random load/write/read/reset traffic checked every cycle against a model."""
    await initialize(dut)
    m = mask(dut)
    model = [0] * NUM_REGS

    for cycle in range(1000):
        do_reset = random.random() < 0.01
        do_load = random.random() < 0.2
        do_write = random.random() < 0.6
        u = tuple(random.randint(0, m) for _ in range(3))
        v = tuple(random.randint(0, m) for _ in range(3))
        waddr = random.randrange(NUM_REGS)
        wdata = random.randint(0, m)
        raddr1 = random.randrange(NUM_REGS)
        raddr2 = random.randrange(NUM_REGS)

        # Spec says load and wen never happen together; keep the random
        # traffic legal and cover priority in load_priority_over_write.
        if do_load:
            do_write = False

        dut.rst_n.value = 0 if do_reset else 1
        dut.load.value = int(do_load)
        dut.load_u.value = pack_vec3(dut, *u)
        dut.load_v.value = pack_vec3(dut, *v)
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
        elif do_load:
            model[0:6] = [*u, *v]
        elif do_write:
            model[waddr] = wdata

    dut.rst_n.value = 1
    dut.load.value = 0
    dut.wen.value = 0
    await check_all(dut, model)


# ---------------------------------------------------------------------------
# 9. Realistic usage sequences
# ---------------------------------------------------------------------------


@cocotb.test()
async def vector_macro_op_sequence(dut):
    """Load u, v; micro-ops read sources and write results; decode reads result.

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


@cocotb.test()
async def back_to_back_macro_ops(dut):
    """A second macro-op's load replaces R0-R5 but keeps R6/R7 scratch values."""
    await initialize(dut)
    m = mask(dut)
    await load(dut, (1, 2, 3), (4, 5, 6))
    await write(dut, 6, 0x5A & m)
    await write(dut, 0, 0x77 & m)
    await check_result(dut, (0x77 & m, 2, 3))

    await load(dut, (7, 8, 9), (10, 11, 12))
    await check_all(dut, [7, 8, 9, 10, 11, 12, 0x5A & m, 0])
