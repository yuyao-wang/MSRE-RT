# Vitis HLS And VCU118 Code

This directory contains the hardware-oriented implementation and helper tooling.

## Contents

- `msr_vitis_kernel.cpp`: HLS kernel implementation.
- `msr_vitis_module_tops.cpp`: module-level HLS benchmark tops.
- `hls_modules/`: HLS TCL entry points for individual kernels and batch runs.
- `vcu118/`: VCU118 host, Vivado, programming, and Windows helper scripts.
- `analysis_artifacts/`: checked-in numerical and timing comparison artifacts.
- `bitstreams/`: optional Vivado bitstream artifacts when generated and small
  enough to keep in Git.

## Build Check

The CMake target is a C++ syntax/build check for the HLS-oriented source. It
does not replace Vivado/Vitis HLS synthesis.

```sh
cmake -S Vitis -B /tmp/msre_vitis_build
cmake --build /tmp/msre_vitis_build
```

HLS synthesis scripts remain under `Vitis/hls_modules/`.
