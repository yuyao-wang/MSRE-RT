# MSR1DPython Hardware Conversion

This repository now carries three forms of the same 1D MSR model:

- Python reference model in the repository root
- plain C++ reference solver in `cpp/msr_plain.cpp`
- Vitis HLS kernel-oriented implementation in `vitis/msr_vitis_kernel.cpp`

The conversion goal is not a line-by-line translation. The goal is to preserve the physics step ordering while reshaping the implementation into hardware-schedulable kernels.

## Current Vitis Design

The HLS kernel keeps the original high-level order:

1. cross sections
2. neutronics
3. thermal hydraulics
4. HX1
5. HX2
6. Brayton and transport-delay bookkeeping

To make that schedule synthesizable, the top-level AXI structs are copied into local working sets first, then the internal arrays are partitioned and partially unrolled. This avoids illegal `m_axi` disaggregation while still exposing intra-kernel parallelism.

Current lane factors in `vitis/msr_vitis_kernel.cpp`:

- cross sections: `4`
- neutronics: `4`
- thermal: `4`
- heat exchanger: `4`

## Reduction Design

The two timing-sensitive reductions are:

- `estimate_global_rho`, which integrates production and absorption terms
- diagnostic `power`, which integrates `q_prime`

Both now use the same blocked trapezoid reduction path:

1. generate trapezoid contributions in blocks of `8`
2. tree-reduce each block locally
3. accumulate block sums into `8` independent partial accumulators
4. tree-reduce the partial accumulators into the final scalar

This replaces a single scalar recurrence with multiple shorter recurrences. In HLS terms, that reduces pressure on the double-precision adder loop-carried dependency and gives the scheduler more room to keep `II=1` while improving the achievable clock.

The design intent is:

- block reduction to limit serial accumulation depth
- tree reduction to shorten the adder chain inside each combine step
- shared reduction logic so `power` and `rho` do not diverge structurally

## Parallelization Notes

The current HLS structure exploits parallelism in three layers:

- unroll tiny dimensions fully or nearly fully: energy groups and precursor groups
- partially unroll spatial sweeps: neutronics, thermal, HX
- pipeline regular stencil and sweep loops with `II=1` targets

The main same-step synchronization boundaries remain:

- `q_prime[:]` between neutronics and thermal
- `fuel[:]` / `graphite[:]` feedback into the next neutronics update
- `Ts_core_L`, `Tss_HX1_L`, `Tsss_HX2_L` across thermal and HX stages
- precursor outlet history and delay-line writeback across steps

That means most coarse physics kernels remain serial inside one outer step, while the main latency reduction path comes from aggressive intra-kernel parallelism and future task-level overlap across step boundaries.

For the longer design discussion, see `docs/cpp_vitis_conversion.md`.
