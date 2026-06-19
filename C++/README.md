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
/tmp/msre_cpp_build/msr_plain 2 /tmp/msre_cpp_smoke
```

The executable arguments are `steps`, `output_dir`, `insertion_pcm`, and
`insertion_time_s`.
