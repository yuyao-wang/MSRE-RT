# Plain C++ Reference Solver

This directory contains the plain C++ reference implementation used to compare
against the Python model and the HLS-oriented Vitis implementation.

## Contents

- `msr_plain.cpp`: standalone C++ transient solver and CSV writer.
- `point_kinetics_shared.hpp`: shared point-kinetics update logic used by both
  plain C++ and Vitis code.
- `CMakeLists.txt`: portable syntax/build check for the C++ reference solver.

## Build And Run

From the repository root:

```sh
cmake -S C++ -B /tmp/msre_cpp_build
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
  --output-dir Verification_Evaluation/outputs/cpp_run
```

The old positional form is still accepted for compatibility:
`msr_plain steps output_dir control_pcm control_time_s`.
