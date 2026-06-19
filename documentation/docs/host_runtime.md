# Host Runtime

The hardware workflow is host-mediated. The CPU is responsible for preparing
state, parameters, and delayed boundary values before launching the FPGA
kernels.

## Current Validated Path

The checked board path uses VCU118 hardware-manager access through JTAG-AXI:

```text
CPU host -> hw_server / Vivado Hardware Manager -> JTAG-AXI -> AXI control and BRAM windows
```

This path is useful for deterministic board validation and readback comparison.
It is not presented as the final high-throughput production transport.

## Dual-FPGA-Ready Protocol

The split design is structured so the reactor core and BOP kernels can be
placed on separate VCU118 devices. The currently reported board measurements are
from the host-mediated VCU118 JTAG-AXI validation path, while the same host
protocol maintains the delayed boundary channels needed for dual-FPGA
deployment. No direct board-to-board transport is required for the checked
protocol.

## Host Tools

Useful entry points:

```sh
python3 -m Vitis.vcu118.msr_vcu118_host --help
python3 -m Vitis.vcu118.msr_transient_batch_vcu118_host --help
```

Address maps and Vivado build helpers live under `Vitis/vcu118/`.
