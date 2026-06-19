# Artifact Reproducibility

MSRE-RT supports three reproducibility levels.

## 1. Software Smoke Test

```sh
python3 -m pip install -r requirements.txt
bash scripts/run_smoke_tests.sh
```

This verifies Python syntax/importability, a small split-scheduler run, and the
C++/Vitis CMake build checks.

## 2. Numerical Verification

Run a reduced transient sweep:

```sh
python3 -m Verification_Evaluation.reactivity_sweep \
  --quick \
  --case-pcm 0,-75 \
  --insertion-time-s 1 \
  --end-time-s 3 \
  --n-points 20 \
  --steady-state-steps 1 \
  --steady-state-outer-iterations 1 \
  --output-dir /tmp/msre_reactivity_smoke
```

Run a small external delayed-neutron circulation validation:

```sh
python3 -m Verification_Evaluation.external_validation \
  --nodes 20 \
  --reported-n 20 \
  --steady-steps 1 \
  --skip-present-verification \
  --output-dir /tmp/msre_external_smoke
```

## 3. Hardware-Oriented Flow

Inspect host and analysis interfaces:

```sh
python3 -m Vitis.analyze_transient_batch_bench --help
python3 -m Vitis.analyze_fpga_kernel_run --help
python3 -m Vitis.vcu118.msr_vcu118_host --help
python3 -m Vitis.vcu118.msr_transient_batch_vcu118_host --help
```

Run Vivado/Vitis HLS only on machines with the required Xilinx toolchain and
licenses. Generated bitstreams and large tool outputs should remain outside Git
unless intentionally curated.
