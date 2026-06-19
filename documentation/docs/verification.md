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
python3 -m Verification_Evaluation.async_split_prototype --help
python3 -m Verification_Evaluation.reactivity_sweep --help
python3 -m Verification_Evaluation.external_validation --help
python3 -m Verification_Evaluation.generate_evaluation_figures --help
```

These scripts cover split scheduling, transient response sweeps,
delayed-neutron circulation, and figure/table generation.

## Checked Artifacts

- `Verification_Evaluation/simulation_results/`: reference NPZ/CSV data.
- `Verification_Evaluation/figure6b.*` and `DNP_comparison.png`: curated
  verification figures.
- `Vitis/analysis_artifacts/`: board, HLS, timing, and transient-batch analysis
  summaries.

Generated outputs should go under ignored output directories unless intentionally
curated.
