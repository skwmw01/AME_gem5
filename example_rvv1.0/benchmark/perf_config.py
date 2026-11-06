#
# Copyright (c) 2026 BOSC & ICT, CAS
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

"""Common AME/RVV performance configuration with explicit ROI events.

The example suite intentionally exposes one guest CPU configuration: the
timing ``RiscvMinorCPU``.  The guest remains a normal RISC-V bare-metal ELF;
the report path is passed through gem5's native RISC-V semihosting interface.
"""

import argparse
import shlex
import sys
import json
from pathlib import Path
from m5.stats.gem5stats import get_simstat

import m5
from m5.objects import (
    AddrRange,
    BadAddr,
    Bridge,
    DDR3_1600_8x8,
    HiFive,
    IOXBar,
    MemCtrl,
    PMAChecker,
    RiscvBareMetal,
    RiscvRTC,
    RiscvSemihosting,
    RiscvSystem,
    Root,
    SrcClockDomain,
    SystemXBar,
    VoltageDomain,
)
from m5.objects.BaseMinorCPU import makeMinorDefaultFUPool
from m5.objects.RiscvCPU import RiscvMinorCPU

parser = argparse.ArgumentParser()
parser.add_argument(
    "--cmd",
    required=True,
    help="bare-metal ELF and arguments",
)
parser.add_argument("--cpu", choices=("minor",), default="minor")
parser.add_argument("--mem-size", default="128MiB")
parser.add_argument(
    "--matrix-op-lat",
    type=int,
    default=16,
    help="Ztt MatrixUnit operation and issue latency in cycles",
)
parser.add_argument(
    "--vector-op-lat",
    type=int,
    default=6,
    help="non-memory RVV VectorUnit operation latency in cycles",
)
parser.add_argument("--vlen", type=int, choices=(128, 256, 512, 1024), default=256)
parser.add_argument("--max-ticks", type=int, default=30000000000000)
parser.add_argument("--roi-json", required=True)
args = parser.parse_args()
if args.matrix_op_lat < 1 or args.vector_op_lat < 1:
    parser.error("Matrix and Vector latencies must be positive")
command = shlex.split(args.cmd)
if not command:
    parser.error("--cmd must contain a bare-metal ELF")

memory_start = 0x7FFFF000
reset_vector_size = 0x1000

system = RiscvSystem(exit_on_work_items=True)
system.mem_mode = "timing"
system.mem_ranges = [
    AddrRange(
        start=memory_start,
        size=args.mem_size,
    )
]
system.workload = RiscvBareMetal(
    bootloader=command[0],
    semihosting=RiscvSemihosting(
        cmd_line=" ".join(command),
        files_root_dir="/",
    ),
)

system.iobus = IOXBar()
system.membus = SystemXBar()
system.membus.badaddr_responder = BadAddr(warn_access="warn")
system.membus.default = system.membus.badaddr_responder.pio
system.system_port = system.membus.cpu_side_ports

system.platform = HiFive()
system.platform.rtc = RiscvRTC(frequency="100MHz")
system.platform.clint.int_pin = system.platform.rtc.int_pin
system.platform.pci_host.internal_connect()
system.platform.pci_host.connect_upper_bus(system.iobus, True)
system.platform.attachOnChipIO(system.membus)
system.platform.attachOffChipIO(system.iobus)
system.platform.attachPlic()
system.platform.setNumCores(1)

system.bridge = Bridge(delay="50ns")
system.bridge.mem_side_port = system.iobus.cpu_side_ports
system.bridge.cpu_side_port = system.membus.mem_side_ports
system.bridge.ranges = system.platform._off_chip_ranges()

system.iobridge = Bridge(delay="50ns", ranges=system.mem_ranges)
system.iobridge.cpu_side_port = system.iobus.mem_side_ports
system.iobridge.mem_side_port = system.membus.cpu_side_ports

system.cache_line_size = 64
system.voltage_domain = VoltageDomain(voltage="1V")
system.clk_domain = SrcClockDomain(
    clock="1GHz", voltage_domain=system.voltage_domain
)
system.cpu_clk_domain = SrcClockDomain(
    clock="1GHz", voltage_domain=VoltageDomain()
)

system.cpu = RiscvMinorCPU(
    clk_domain=system.cpu_clk_domain,
    cpu_id=0,
    executeFuncUnits=makeMinorDefaultFUPool(
        matrix_op_lat=args.matrix_op_lat,
        vector_op_lat=args.vector_op_lat,
    ),
)
system.cpu.icache_port = system.membus.cpu_side_ports
system.cpu.dcache_port = system.membus.cpu_side_ports
system.cpu.createInterruptController()
system.cpu.createThreads()
for isa in system.cpu.isa:
    isa.vlen = args.vlen
    isa.elen = 64

system.cpu.mmu.pma_checker = PMAChecker(
    uncacheable=[
        *system.platform._on_chip_ranges(),
        *system.platform._off_chip_ranges(),
    ]
)

system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8(range=system.mem_ranges[0])
system.mem_ctrl.port = system.membus.mem_side_ports

root = Root(full_system=True, system=system)
m5.instantiate()
# Read only CPU statistics at ROI end; no per-region 100KB text dumps.
def cpu_stats():
    snapshot = get_simstat([system.cpu])
    committed = snapshot.commitStats0
    kinds = committed.committedInstType.value
    return {
        "instructions": int(committed.numInsts.value),
        "ops": int(committed.numOps.value),
        "vector_instructions": int(committed.numVecInsts.value),
        "matrix_instructions": sum(int(kinds[k].value) for k in
                                   ("Matrix", "MatrixMov", "MatrixOP")),
        "loads": int(committed.numLoadInsts.value),
        "stores": int(committed.numStoreInsts.value),
        "instruction_types": {k: int(v.value) for k, v in kinds.items()},
    }

regions = []
active = None
while True:
    remaining = args.max_ticks - m5.curTick()
    if remaining <= 0:
        sys.exit("benchmark exceeded simulated tick limit")
    event = m5.simulate(remaining)
    cause = event.getCause()
    if cause == "workbegin":
        if active is not None:
            sys.exit("nested benchmark regions")
        m5.stats.reset()
        active = (event.getCode(), m5.curTick())
    elif cause == "workend":
        if active is None or event.getCode() != active[0]:
            sys.exit("unmatched benchmark region end")
        region = cpu_stats()
        region.update(repeat=active[0], start_tick=active[1],
                      end_tick=m5.curTick(), ticks=m5.curTick() - active[1])
        regions.append(region)
        active = None
    elif cause == "semi:ADP_Stopped_ApplicationExit":
        if event.getCode() or active is not None or not regions:
            sys.exit("guest failed or did not complete its measured regions")
        result = {
            "regions": regions, "total_ticks": m5.curTick(),
            "clock_hz": 1000000000, "ticks_per_cycle": 1000,
            "vlen": args.vlen, "matrix_op_lat": args.matrix_op_lat,
            "vector_op_lat": args.vector_op_lat,
        }
        Path(args.roi_json).write_text(json.dumps(result, indent=2) + "\n")
        print(f"[PASS] benchmark completed {len(regions)} regions")
        break
    else:
        sys.exit("unexpected benchmark exit: " + cause)
