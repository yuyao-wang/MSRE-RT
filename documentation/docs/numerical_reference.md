# Numerical Reference

The Python reference implementation lives in `python/` and provides the
highest-level executable model.

## Main Entry Point

```sh
python3 python/main.py \
  --steps 2 \
  --n 20 \
  --steady-state-steps 1 \
  --control-pcm -75 \
  --control-time-s 1 \
  --output-dir /tmp/msre_python_smoke \
  --no-plots \
  --json
```

Common inputs include `--steps`, `--n`, `--outer-dt`, `--control-pcm`,
`--control-time-s`, `--reactivity-schedule`, `--core-inlet-mode`, and
`--output-dir`. Use `--set KEY=VALUE` for scalar parameter overrides that are
not promoted to dedicated flags.

## Role In The Artifact

The Python path provides:

- parameter generation and steady-state initialization;
- coupled transient reference behavior;
- diagnostic output used by verification scripts;
- the source-level baseline for C++ and HLS comparisons.

Generated outputs should go under `Verification_Evaluation/outputs/` or another
ignored run directory unless they are intentionally curated.
