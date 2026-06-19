# Python Reference Model

This directory contains the executable Python reference implementation of the
reduced MSRE model.

## Contents

- `main.py`: coupled transient driver.
- `parameters.py`: model constants, discretization, feedback settings, and
  steady-state initialization.
- `neutronics.py`, `criticality.py`, `cross_sections.py`, `point_kinetics.py`:
  neutronics, reactivity, and point-kinetics helpers.
- `thermal_hydraulics.py`, `HX1.py`, `HX2.py`, `heat_exchanger.py`,
  `power_plant.py`, `transport_delay.py`: thermal and loop transport models.
- `ode_solver.py` and the solver support files: SciPy-derived integration
  support retained by the model.

## Run

From the repository root:

```sh
python3 python/main.py
```

Simulation outputs are written under
`Verification_Evaluation/simulation_results/` so the Python code directory
stays source-only.
