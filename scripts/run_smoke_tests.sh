#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python3 -m py_compile reference_model/*.py verification/*.py fpga_emulation/*.py fpga_emulation/vcu118/*.py

python3 -m verification.async_split_prototype \
  --steps 1 \
  --n 20 \
  --steady-state-steps 1 \
  --control-pcm -75 \
  --control-time-s 0 \
  --json

cmake -S hardware_mapping -B /tmp/msre_cpp_build
cmake --build /tmp/msre_cpp_build

cmake -S fpga_emulation -B /tmp/msre_vitis_build
cmake --build /tmp/msre_vitis_build
