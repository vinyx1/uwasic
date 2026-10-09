"""Black-box cocotb tests for reg_file.

Assumptions to confirm against the spec:
- writes take effect at the rising edge of clk
- reads are combinational
- rst_n is active low (its exact reset timing/value is not tested here)
"""

import cocotb
from cocotb.triggers import Timer


async def settle():
    await Timer(1, unit="ns")


async def tick(dut):
    """Manually generate one clean rising edge and return clk low."""
    dut.clk.value = 0
    await settle()
    dut.clk.value = 1
    await settle()
    dut.clk.value = 0
    await settle()


async def initialize(dut):
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


async def write(dut, address, data):
    dut.wen.value = 1
    dut.waddr.value = address
    dut.wdata.value = data
    await tick(dut)
    dut.wen.value = 0
    await settle()


async def check_port(dut, port, address, expected):
    getattr(dut, f"raddr{port}").value = address
    await settle()
    actual = int(getattr(dut, f"rdata{port}").value)
    assert actual == expected, (
        f"port {port}: R{address} expected 0x{expected:x}, got 0x{actual:x}"
    )


@cocotb.test()
async def write_and_read_all_registers(dut):
    """Each of the six registers accepts a write; two ports read independently."""
    await initialize(dut)
    mask = (1 << len(dut.wdata)) - 1
    values = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66]
    for address, value in enumerate(values):
        await write(dut, address, value & mask)

    for address, value in enumerate(values):
        await check_port(dut, 1, address, value & mask)
        await check_port(dut, 2, 5 - address, values[5 - address] & mask)


@cocotb.test()
async def write_enable_blocks_changes(dut):
    """wen=0 must leave an already initialized register unchanged."""
    await initialize(dut)
    mask = (1 << len(dut.wdata)) - 1
    await write(dut, 2, 0xA5 & mask)
    dut.wen.value = 0
    dut.waddr.value = 2
    dut.wdata.value = 0x5A & mask
    await tick(dut)
    await check_port(dut, 1, 2, 0xA5 & mask)
    await check_port(dut, 2, 2, 0xA5 & mask)
