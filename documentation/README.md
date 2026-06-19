# Documentation

This directory is the documentation entry point for MSRE-RT. The root README is
kept as the project homepage; implementation details, reproducibility notes, and
hardware evidence live here.

## Guide

| File | Purpose |
| --- | --- |
| [`docs/model.md`](docs/model.md) | Model scope, physics blocks, and transport-delay boundaries |
| [`docs/numerical_reference.md`](docs/numerical_reference.md) | Python reference simulation and runtime inputs |
| [`docs/cpp_solver.md`](docs/cpp_solver.md) | Plain C++ solver and same-source verification role |
| [`docs/fpga_hls_design.md`](docs/fpga_hls_design.md) | HLS kernel split, synthesis scripts, and report locations |
| [`docs/host_runtime.md`](docs/host_runtime.md) | Host-mediated board runtime and dual-FPGA protocol |
| [`docs/verification.md`](docs/verification.md) | Verification scripts, smoke runs, and checked result artifacts |
| [`docs/hardware_results.md`](docs/hardware_results.md) | Hardware timing, resource, and board-readback summaries |
| [`docs/reproducibility.md`](docs/reproducibility.md) | Artifact reproducibility levels and command sequences |

## Supporting Artifacts

- `readme_assets/`: figures used directly by the root README.
- `synthesis_reports/`: HLS reports copied from local synthesis runs.
- `tex_note/`: non-manuscript LaTeX notes and support images.

New simulation, verification, and synthesis outputs should be written to
ignored output directories unless they are intentionally curated for the public
artifact. The manuscript drafting directory `paper_writing/` is intentionally
excluded from Git and is not part of this documentation tree.
