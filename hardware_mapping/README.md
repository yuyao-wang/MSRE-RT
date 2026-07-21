# Hardware-Mapping Implementation

This directory contains the C++17 implementation that maps the numerical
reference algorithms into a static, deployment-oriented form. It bridges the
reference model and FPGA kernels while providing pre-hardware consistency
checks.

## Contents

- `msr_plain.cpp`: standalone hardware-mapping solver and CSV writer.
- `point_kinetics_shared.hpp`: shared point-kinetics update logic used by both
  the C++17 mapping and Vitis HLS code.
- `CMakeLists.txt`: portable syntax/build check for the mapping implementation.

## Build And Run

From the repository root:

```sh
cmake -S hardware_mapping -B /tmp/msre_cpp_build
cmake --build /tmp/msre_cpp_build
/tmp/msre_cpp_build/msr_plain --steps 2 --output-dir /tmp/msre_cpp_smoke
```

The executable exposes the main runtime inputs as named arguments:

```sh
/tmp/msre_cpp_build/msr_plain \
  --steps 600 \
  --n 80 \
  --outer-dt 1.0 \
  --control-pcm -75 \
  --control-time-s 300 \
  --core-inlet-mode hx_coupled \
  --output-dir verification/outputs/cpp_run
```

The old positional form is still accepted for compatibility:
`msr_plain steps output_dir control_pcm control_time_s`.
