# FPGA And HLS Design

The hardware-oriented source lives in `Vitis/`. It contains HLS kernels,
module-level benchmark tops, VCU118 host tooling, Vivado scripts, and checked
analysis artifacts.

## Split Kernels

The main split design uses two shape-specialized kernels for the `Nz = 200,
s = 1` study:

- `core_step_kernel_n200_s1`
- `bop_step_kernel_n200_s1`

The core kernel handles the reactor-core update, while the BOP kernel handles
the heat-exchanger and downstream loop update. The host runtime stages delayed
boundary values between the two.

## Build Check

The local CMake target is a C++ syntax/build check for the HLS-oriented source:

```sh
cmake -S Vitis -B /tmp/msre_vitis_build
cmake --build /tmp/msre_vitis_build
```

Vivado/Vitis HLS synthesis uses TCL entry points under `Vitis/hls_modules/`.
Example scripts include:

```sh
vitis_hls -f Vitis/hls_modules/hls_core_step_n200_s1_10ns_lowlane.tcl
vitis_hls -f Vitis/hls_modules/hls_bop_step_n200_s1_10ns_lowlane.tcl
```

## Reports

Tracked HLS reports, schedule XML, design XML, and schedule diagrams are under
`documentation/synthesis_reports/`. Analysis summaries from board and timing
runs are under `Vitis/analysis_artifacts/`.
