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

## Dual-FPGA Protocol

The split design can place the reactor core and BOP kernels on separate VCU118
devices. The host maintains the delayed boundary channels and launches each
kernel with committed values from the proper model step. No direct
board-to-board transport is required for the checked protocol.

## Host Tools

Useful entry points:

```sh
python3 -m Vitis.vcu118.msr_vcu118_host --help
python3 -m Vitis.vcu118.msr_transient_batch_vcu118_host --help
```

Address maps and Vivado build helpers live under `Vitis/vcu118/`.
