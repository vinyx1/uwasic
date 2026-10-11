"""reg_file tests: realistic usage sequences. See helpers.py for the behaviour under test."""

import cocotb

from helpers import (
    settle,
    initialize,
    mask,
    write,
    load,
    check_port,
    check_result,
    check_all,
)


@cocotb.test()
async def vector_macro_op_sequence(dut):
    """Load u, v; micro-ops read sources and write results; decode reads result.
    Essentially, act as the decode+FU
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
