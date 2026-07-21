# Verification

Verification is organized around small smoke checks, numerical consistency
scripts, and checked analysis artifacts.

## Smoke

```sh
bash scripts/run_smoke_tests.sh
```

The smoke script compiles Python files, runs the split-scheduler prototype for
one short case, and builds the C++ and Vitis CMake targets.

## Numerical Checks

```sh
python3 -m verification.async_split_prototype --help
python3 -m verification.reactivity_sweep --help
python3 -m verification.external_validation --help
python3 -m verification.generate_evaluation_figures --help
```

These scripts cover split scheduling, transient response sweeps,
delayed-neutron circulation, and figure/table generation.

## Checked Artifacts

- `verification/simulation_results/`: reference NPZ/CSV data.
- `verification/figure6b.*` and `DNP_comparison.png`: curated
  verification figures.
- `fpga_emulation/analysis_artifacts/`: board, HLS, timing, and transient-batch analysis
  summaries.

Generated outputs should go under ignored output directories unless intentionally
curated.
