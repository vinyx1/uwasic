"""reg_file tests: randomized with reference model. See helpers.py for the behaviour under test."""

import random

import cocotb

from helpers import (
    NUM_REGS,
    settle,
    tick,
    initialize,
    mask,
    pack_vec3,
    unpack_vec3,
    check_all,
)


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
