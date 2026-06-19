# Plain C++ Solver

The plain C++ reference lives in `C++/`. It is used to verify that the
hardware-oriented implementation preserves the Python model semantics while
moving toward static, synthesis-friendly source.

## Build

```sh
cmake -S C++ -B /tmp/msre_cpp_build
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

## Verification Role

The C++ solver is the intermediate reference between Python and HLS. It is
useful for syntax/build checks, one-step timing comparisons, and same-source
kernel readback validation.
