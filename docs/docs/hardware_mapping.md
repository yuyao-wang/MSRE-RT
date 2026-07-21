# Hardware-Mapping Implementation

The C++17 implementation lives in `hardware_mapping/`. It translates the
numerical-reference algorithms into a static, deployment-oriented form and
checks that model semantics are preserved before FPGA integration.

## Build

```sh
cmake -S hardware_mapping -B /tmp/msre_cpp_build
cmake --build /tmp/msre_cpp_build
```

## Run

```sh
/tmp/msre_cpp_build/msr_plain \
  --steps 2 \
  --n 20 \
  --steady-state-steps 1 \
  --control-pcm -75 \
  --control-time-s 1 \
  --output-dir /tmp/msre_cpp_smoke
```

The executable accepts named inputs such as `--steps`, `--n`, `--outer-dt`,
`--steady-state-steps`, `--core-inlet-mode`, `--v-core`, `--control-pcm`,
`--control-time-s`, and `--output-dir`. The older positional form remains
accepted for compatibility.

## Mapping And Verification Role

This layer bridges the Python numerical reference and Vitis HLS kernels. It is
used for build checks, one-step timing comparisons, algorithm mapping, and
same-source kernel readback validation.
