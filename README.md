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

These are now compile-time tunables, so exploratory HLS runs can lower lane factors through `add_files ... -cflags {-D...}` without forking the kernel source. The `10 ns` low-lane experiment sets all four lane factors to `2`.

The version-controlled HLS script for the next exploratory run is `vitis/hls_synth_10ns.tcl`, which sets the clock target to `10 ns` (`100 MHz`). The current `5 ns` target is still treated as a stretch goal, not the default turnaround configuration.

## Module HLS Benchmarks

The repository now also carries a module-level HLS benchmark source in `vitis/msr_vitis_module_tops.cpp`.

Those tops are intentionally separate from `msr_step_kernel`:

- `msr_cross_sections_bench`
- `msr_neutronics_bench`
- `msr_thermal_bench`
- `msr_hx1_bench`
- `msr_hx2_bench`
- `msr_power_reduction_bench`

Their purpose is fast iterative synthesis for module-level timing and resource calibration. Each top isolates one compute block while keeping the same inner implementation used by the monolithic step kernel.

The corresponding TCL entry points live under `vitis/hls_modules/` and write into `vitis/hls_module_work/`, so they do not collide with the existing monolithic `vitis/hls_work/` runs. That separation is deliberate: module experiments can be launched, deleted, and compared without perturbing the long-running full-step synthesis jobs.

Recommended use:

- start with `hls_neutronics_10ns.tcl`, because neutronics is still the dominant critical-path candidate
- use `hls_cross_sections_10ns.tcl` and `hls_power_reduction_10ns.tcl` to iterate on reduction and feedback logic quickly
- treat `hls_hx1_10ns.tcl` and `hls_hx2_10ns.tcl` as duplicated transport kernels whose reports should stay close
- only return to the full `msr_step_kernel` synthesis after a module-level change has already shown an acceptable latency / resource tradeoff

## Reduction Design

The two timing-sensitive reductions are:

- `estimate_global_rho`, which integrates production and absorption terms
- diagnostic `power`, which integrates `q_prime`

Both now use the same sliding-window trapezoid reduction path:

1. stream through `x[:]` and `y[:]` once
2. reuse the previous sample as a register-held window
3. accumulate each trapezoid contribution into one of `8` rotating partial accumulators
4. tree-reduce the partial accumulators into the final scalar

This replaces both the original scalar recurrence and the later wide blocked-read version. In HLS terms, the new structure reduces read pressure on the source arrays while still shortening the accumulation dependency chain.

The design intent is:

- sliding-window reads to cut the number of array loads per iteration
- rotating partial sums to limit serial accumulation depth
- tree reduction to shorten the final adder chain
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

That means most coarse physics kernels remain serial inside one outer step, while the main latency reduction path combines aggressive intra-kernel parallelism with host-intermediated task-level overlap across physical delay boundaries.

For the longer design discussion, see `docs/cpp_vitis_conversion.md`.
For the staged precision roadmap, see `docs/mixed_precision_plan.md`.
