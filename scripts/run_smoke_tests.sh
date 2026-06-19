#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python3 -m py_compile python/*.py Verification_Evaluation/*.py Vitis/*.py Vitis/vcu118/*.py

python3 -m Verification_Evaluation.async_split_prototype \
  --steps 1 \
  --n 20 \
  --steady-state-steps 1 \
  --control-pcm -75 \
  --control-time-s 0 \
  --json

cmake -S C++ -B /tmp/msre_cpp_build
cmake --build /tmp/msre_cpp_build

cmake -S Vitis -B /tmp/msre_vitis_build
cmake --build /tmp/msre_vitis_build
