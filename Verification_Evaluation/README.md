# Verification And Evaluation

This directory contains validation scripts, reproducibility helpers, generated
comparison data, and plots.

## Contents

- `verification_physics.py`: reusable physics/verification routines.
- `verification_utils.py`: plotting, CSV, JSON, and error-metric utilities.
- `generate_evaluation_figures.py`: case runner for evaluation CSV/figure
  exports.
- `external_validation.py`: MSRE delayed-neutron circulation-loss comparison.
- `reactivity_sweep.py`: transient reactivity insertion sweep.
- `async_split_prototype.py`: CPU-brokered split core/BOP scheduling prototype.
- `simulation_results/`: checked-in reference simulation data.

## Smoke Runs

From the repository root:

```sh
python3 -m Verification_Evaluation.async_split_prototype --steps 1 --control-pcm -75 --control-time-s 1 --json
python3 -m Verification_Evaluation.reactivity_sweep --quick --case-pcm 0,-75 --insertion-time-s 1
python3 -m Verification_Evaluation.generate_evaluation_figures --quick case_00_steady_state_reference
```

New generated outputs should go under `Verification_Evaluation/outputs/`, which
is ignored by Git.

## Interfaces

Each runnable script has a CLI. Use `--help` to see the full input surface.

- `async_split_prototype.py`: `--steps`, `--order`, `--n`, `--outer-dt`,
  `--control-pcm`, `--control-time-s`.
- `reactivity_sweep.py`: `--case-pcm`, `--insertion-time-s`, `--end-time-s`,
  `--baseline-dt-s`, `--n-points`, `--output-dir`.
- `external_validation.py`: `--nodes`, benchmark values, MSRE loop residence
  inputs, and `--output-dir`.
- `get_npz_data.py`: `--simulation-dir`, index range, selected `--step`, and
  `--output`.
- `read_npz.py`: input `.npz`, `--list-only`, and `--max-items`.
