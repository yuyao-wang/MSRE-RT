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
python3 -m Verification_Evaluation.async_split_prototype --steps 1 --json
python3 -m Verification_Evaluation.reactivity_sweep --quick
python3 -m Verification_Evaluation.generate_evaluation_figures --quick case_00_steady_state_reference
```

New generated outputs should go under `Verification_Evaluation/outputs/`, which
is ignored by Git.
