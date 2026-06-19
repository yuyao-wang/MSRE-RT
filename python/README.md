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
python3 python/main.py --steps 2 --output-dir /tmp/msre_python_smoke --no-plots
```

By default, simulation outputs are written under the checked reference-data
area `Verification_Evaluation/simulation_results/`. For smoke runs or new
experiments, pass `--output-dir` to write under `/tmp/...` or an ignored
artifact directory such as `Verification_Evaluation/outputs/...` so the Python
code directory stays source-only.

Common runtime inputs are exposed as arguments:

```sh
python3 python/main.py \
  --steps 600 \
  --n 80 \
  --outer-dt 1.0 \
  --control-pcm -75 \
  --control-time-s 300 \
  --core-inlet-mode hx_coupled \
  --output-dir Verification_Evaluation/outputs/python_run
```

Use `--reactivity-schedule '0:0,300:-75,360:0'` for multi-event control
histories. Use `--set KEY=VALUE` for scalar parameter overrides that are not
promoted to dedicated flags.
