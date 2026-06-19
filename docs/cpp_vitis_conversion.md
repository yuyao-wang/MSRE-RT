# MSR1D Python -> Plain C++ -> Vitis HLS Conversion Notes

## Deliverables

- Plain C++ reference solver: [`cpp/msr_plain.cpp`](../cpp/msr_plain.cpp)
- Plain C++ build file: [`cpp/CMakeLists.txt`](../cpp/CMakeLists.txt)
- Vitis HLS kernel-oriented implementation: [`vitis/msr_vitis_kernel.cpp`](../vitis/msr_vitis_kernel.cpp)
- Vitis syntax-check build file: [`vitis/CMakeLists.txt`](../vitis/CMakeLists.txt)
- Experimental full-transient batch top: `msr_transient_batch_kernel()` inside [`vitis/msr_vitis_kernel.cpp`](../vitis/msr_vitis_kernel.cpp)
- Same-init plain C++ transient control runner: [`vitis/vcu118/msr_transient_batch_plain_timed.cpp`](../vitis/vcu118/msr_transient_batch_plain_timed.cpp)
- Resident transient benchmark script: [`vitis/analyze_transient_batch_bench.py`](../vitis/analyze_transient_batch_bench.py)

The C++ code keeps the Python step ordering and the same physics decomposition:

1. `neutronics`
2. `thermal_hydraulics`
3. `HX1`
4. `HX2`
5. `Brayton`
6. transport-delay / precursor-loop bookkeeping

The HLS code changes only two architectural points:

- dynamic vectors -> static arrays
- adaptive RK4 -> fixed `hardware_substeps` RK4

That change is deliberate. The plain C++ version is the numerical reference. The Vitis version is the schedulable hardware form.

The current HLS kernel also makes the interface / compute boundary explicit:

- top-level AXI structs are loaded once into local working sets
- internal arrays are then partitioned and partially unrolled
- updated state is written back only at the end of the step

This avoids illegal `m_axi` disaggregation while still enabling aggressive internal parallelism.

The current kernel file now contains two hardware-facing execution modes:

- `msr_step_kernel()`
  - reference one-step coupled advance
- `msr_transient_batch_kernel()`
  - multi-step, multi-scenario transient advance with on-chip resident state between steps

## Resident Batch Results

The current publishable resident-transient configuration is:

- full transient loop resident on FPGA-side state
- `hardware_substeps = 32`
- shared / low-lane arithmetic:
  - cross-sections `2`
  - neutronics `2`
  - thermal `4`
  - HX `2`
- resident mixed precision:
  - thermal state `float`
  - delay / history `float`
  - control streams `float`
- explicit RK4 precursor path
  - `MSR_PRECURSOR_ANALYTIC_UPDATE=0`

Validation is now reported with two CPU baselines:

- full-program plain C++
  - includes its own initialization and CSV/report path
- same-init plain C++
  - starts from the exact same state / delay / control blobs as the resident batch runner
  - isolates numerical drift from initialization drift

For the `600`-step nominal case (`0 pcm`, `outer_dt = 1 s`), the resident batch path produced:

- full-program plain C++ wall time: `4.992 s`
- resident batch CPU proxy wall time: `0.169 s`
- speedup vs full-program plain C++: `29.46x`
- same-init plain C++ wall time: `0.301 s`
- speedup vs same-init plain C++: `1.77x`

Same-init accuracy for that nominal case is tight enough to treat the resident loop as numerically preserved for the article baseline:

- `phi_mid` relative error: `6.46e-4`
- `power` relative error: `6.23e-4`
- `fuel_mid` relative error: `1.59e-4`
- `graphite_mid` relative error: `1.46e-3`
- core / HX / Brayton scalar temperatures: roughly `1e-4 .. 3e-4` relative

Against the Python / paper reference for the same nominal case, the resident batch path is also close:

- `phi_mid` relative error: `7.38e-5`
- `power` relative error: `6.41e-5`
- most scalar temperatures: about `1e-4 .. 3e-4` relative

For a `50 pcm` insertion at `300 s`, the resident batch path is retained as a stress case. It preserves the thermal / loop states well and exposes the expected stronger sensitivity of the neutronics response:

- speedup vs full-program plain C++: `28.69x`
- speedup vs same-init plain C++: `1.74x`
- same-init `phi_mid` relative error: `1.99e-2`
- same-init `power` relative error: `1.99e-2`

So the current manuscript split is:

- use the `0 pcm` resident transient as the deterministic resident-loop baseline
- report nonzero reactivity-step cases as stress / sensitivity cases rather than weakening the hardware-emulation claim

## Mapping Summary

| Python module | Plain C++ | Vitis HLS |
| --- | --- | --- |
| `cross_sections.py` | `BuildCrossSections()` | `cross_sections_kernel()` |
| `neutronics.py` | `SolveNeutronics()` | `neutronics_kernel()` + `neutronics_rhs()` |
| `thermal_hydraulics.py` | `SolveThermalHydraulics()` | `thermal_kernel()` + `thermal_rhs()` |
| `heat_exchanger.py`, `HX1.py`, `HX2.py` | `SolveHeatExchanger()`, `Hx1Config()`, `Hx2Config()` | `hx_kernel()` + `hx_rhs()` |
| `transport_delay.py` | `TransportDelay()` | `delay_line_update()` |
| `precursor_loop.py` | `PrecursorInletFromLoop()`, `RecordPrecursorOutlet()` | `precursor_inlet_from_loop()`, `record_precursor_history()` |
| `power_plant.py` | `PowerPlantTemp()` | `brayton_kernel()` |
| `main.py` | `RunSimulation()` | `msr_step_kernel()` |

## Which Kernels Can Run In Parallel

### Same outer time step

Strictly inside one step, the major blocks are mostly serial:

1. `cross_sections -> neutronics`
2. `thermal`
3. `HX1`
4. `HX2`
5. `Brayton`

The reason is data dependence, not implementation style:

- `thermal` needs `q_prime` from `neutronics`
- `HX1` needs `Ts_core_L` from `thermal`
- `HX2` needs `Tss_HX1_L` from `HX1`
- `Brayton` needs `Tsss_HX2_L` from `HX2`

So the large physics blocks are not same-step parallel kernels.

### Fine-grain parallel candidates

These are parallel inside a block:

- two-group algebra in cross-section and flux updates
- six precursor-group source / decay / advection updates
- axial cell updates in `thermal`
- axial cell updates in `HX1` and `HX2`
- six independent transport-delay FIFOs

### Cross-step parallel candidates

Task-level parallelism is available across consecutive steps:

- `Brayton(k)` can overlap with host logging and event handling for `k+1`
- `HX2(k)` can overlap with `cross_sections(k+1)` prefetch
- if the design is split into `core_kernel` and `BOP_kernel`, the core can advance while downstream loop hardware finishes the previous step

This cross-step overlap is the main latency-reduction path. Same-step full kernel parallelism is limited.

## Which Variables Form Synchronization Boundaries

These are the real boundaries between compute domains:

- `temperature_fuel[:]`, `temperature_graphite[:]`
  - boundary between `thermal` and `neutronics` through temperature feedback
- `q_prime[:]`
  - boundary from `neutronics` to `thermal`
- `Ts_core_0`
  - delayed inlet boundary into the core thermal block
- `Ts_core_L`
  - boundary from core thermal to HX1
- `Tss_HX1_L`
  - boundary from HX1 to HX2
- `Tsss_HX2_L`
  - boundary from HX2 to Brayton
- precursor outlet `C[:, N-1]`
  - boundary from core neutronics to external precursor-loop history
- delay-line writebacks
  - boundary from one step to future steps

Not every computed quantity is a synchronization boundary:

- `rho` is diagnostic only in the current code path
- `Brayton` work / efficiency terms are diagnostic unless used by a controller later

That distinction matters for hardware partitioning. Only the boundary variables must be committed before another kernel can proceed.

## Which Computations Should Be Pipelined

The best pipeline targets are the regular stencil / sweep loops:

- cross-section rebuild over axial cells
- diffusion stencil in `neutronics`
- delayed-source accumulation over precursor groups
- precursor advection update
- fuel advection / heat-exchange update
- graphite axial conduction update
- HX hot-side and cold-side sweeps

Recommended HLS policy:

- pipeline all axial loops with `II=1` target
- fully unroll the tiny dimensions:
  - energy groups = 2
  - precursor groups = 6
- keep RK4 stage boundaries explicit

The important nuance is that RK4 stage transitions are global barriers inside a block. You can pipeline each stage loop, but stage 2 cannot start before stage 1 has produced its intermediate state.

## Which Spatial Updates Should Be Unrolled

Good full-unroll dimensions:

- energy-group dimension
- precursor-group dimension

Good partial-unroll dimensions:

- axial cell loops in `neutronics`
- axial cell loops in `thermal`
- axial cell loops in `HX1/HX2`

Recommended practical factors:

- `neutronics` axial loops: partial unroll by 4 or 8
- `thermal` axial loops: partial unroll by 8 or 16
- `HX1/HX2` axial loops: partial unroll by 8 or 16

Current implementation:

- cross-section rebuild: partial unroll by `4`
- neutronics axial updates: partial unroll by `4`
- thermal axial updates: partial unroll by `4`
- HX1/HX2 axial updates: partial unroll by `4`
- trapezoid reductions: sliding-window accumulation with `8` rotating partial sums

Reason:

- full unroll over `N=80` is expensive in BRAM routing and DSP usage
- `neutronics` has the highest arithmetic density and the heaviest neighbor traffic, so it usually saturates routing first

## Why Neutronics Is the Critical Path

`neutronics` is the critical path for six separate reasons:

1. Largest state per cell.
   - `phi1`, `phi2`, and `6` precursor groups means `8N` state variables.
   - `thermal` and each HX block are only `2N`.

2. More arithmetic per cell.
   - diffusion stencil
   - removal / scattering
   - prompt source
   - delayed source
   - precursor production / decay / advection

3. Strong fan-out.
   - `q_prime[:]` feeds the entire thermal solve.
   - nothing downstream can start before that vector exists.

4. Temperature-dependent cross sections.
   - every step must rebuild XS from `temperature_fuel[:]` and `temperature_graphite[:]`.
   - this ties the critical block to the feedback loop.

5. RK4 stage cost multiplies everything.
   - each outer step executes four RHS evaluations per RK4 stage sequence.

6. Precursor-loop history update.
   - the outlet `C[:, N-1]` must be committed for future inlet reconstruction.

In short: `neutronics` is both the densest compute block and the earliest dependency source for the rest of the plant model.

## How To Reduce Step Latency With Task-Level Parallelism

### 1. Split the step into two coarse kernels

Use:

- `core_kernel = cross_sections + neutronics + thermal`
- `bop_kernel = HX1 + HX2 + Brayton + delay updates`

This split matches the true dependency graph better than one monolithic kernel.

### 2. Double-buffer step states

Maintain:

- `state_cur`
- `state_next`

While one kernel writes `state_next`, the other consumes the already-committed boundaries from `state_cur`.

### 3. Exploit delayed-loop slack

The external loop already contains explicit transport delays:

- `tau_hx_c`
- `tau_c_hx`
- `tau_hx_r`
- `tau_r_hx`
- `tau_r_pp`
- `tau_pp_r`

Because these are real physical delays, downstream loop calculations do not have to complete in the same cycle budget as the core update. This gives scheduling slack that should be used, not ignored.

### 4. Overlap host work with the slowest kernel

While FPGA computes:

- CPU can run logging
- event interpolation
- I/O marshaling
- optional control logic

Brayton can stay on CPU if PCIe/XRT transfer overhead is smaller than the benefit of keeping the core kernel tighter.

### 5. Prefetch next-step read-only data

While `bop_kernel(k)` runs, prepare:

- next-step temperature references if they are static
- scalar control inputs
- diagnostic buffers

This does not remove the `thermal -> neutronics` boundary, but it does remove host-side bubbles.

### 6. Keep diagnostic-only quantities off the critical path

`rho`, efficiency, and work-balance outputs should be post-step side products, not step-blocking dependencies.

## Experimental Batched Transient Kernel

`msr_transient_batch_kernel()` is the first hardware form that matches the intended throughput-oriented FPGA usage better than the single-step interface.

It does three architectural things differently:

- loops over the full transient inside the FPGA top instead of requiring one host launch per time step
- keeps state, transport delays, and precursor-loop history resident on chip for the duration of a scenario
- iterates over multiple independent scenarios in one kernel launch so the platform can be used for parameter sweeps and fault batches

The control interface is intentionally narrow:

- `states[scenario]`
- `delays[scenario]`
- `params[scenario]`
- `rod_positions[scenario, step]`
- `external_reactivities[scenario, step]`

Only final diagnostics and final state are written back. That keeps host traffic proportional to scenario count rather than to time-step count.

## Recommended Hardware Partition

### FPGA

- cross-section rebuild
- neutronics
- thermal hydraulics
- HX1
- HX2
- transport-delay FIFOs

### CPU / host

- Brayton if host latency is acceptable
- logging
- output sampling
- case management
- scenario / event injection

If a single-kernel HLS implementation is preferred first, keep the exact top-level order already used in [`vitis/msr_vitis_kernel.cpp`](../vitis/msr_vitis_kernel.cpp), then split into two kernels only after profiling.

## Current Implementation Status

- The plain C++ reference is runnable and writes CSV traces.
- The host-intermediated split path uses the CPU broker to commit physical delay channels, stage boundary packets, launch kernels, and read scalar boundary outputs.
- Direct board-to-board communication is not required because the core/BOP boundary is a physical transport-delay boundary.
- The HLS version uses fixed-step RK4 substeps instead of the Python adaptive RK4.
  - This is intentional for deterministic scheduling.
- The deterministic timing report should include repeats / warmup, mean / median / standard deviation or explicit bounds, 95th / 99th percentile or conservative maximum bounds, host OS / CPU / software versions, background load, and sustained multi-step behavior.

## Analytic Precursor Update Snapshot (2026-06-18)

The latest experiment replaces the explicit RK4 precursor evolution inside `neutronics_kernel()` with an analytic exponential update while keeping the prompt flux path in the RK4/IMEX-style split.

Measured against the one-step Python physics reference for `N=200`, `outer_dt=1.0 s`, `steady_state_steps=180`:

- power absolute error drops from `8.01233e+01 W` to `2.78655e+00 W` (`0.03478x`)
- `phi_mid` absolute error drops from `7.27907e-08` to `2.53153e-09` (`0.03478x`)
- `Ts_core_outlet` absolute error drops from `5.33614e-06 K` to `2.98599e-06 K` (`0.55958x`)
- BOP-side temperatures are unchanged because only the core neutronics update changed

The local CPU proxy does not show a performance win for this formulation:

- baseline one-step core median: `13.063735 us`
- analytic one-step core median: `16.894535 us`
- total coupled median: `15.214975 us` -> `19.060400 us` (`0.79825x` speedup ratio, so slower)

Remote Vitis HLS `csynth` on `xcvu9p-flga2104-2L-e` shows the naive analytic implementation is not directly hardware-viable in its current fully aggressive form:

- baseline `core_step_kernel_n200_s1`: `19079..19139` cycles, `7.672 ns` estimated clock
- analytic variant: latency `undef`, `3593.586 ns` estimated clock
- LUT: `185984` -> `615052` (`3.307x`)
- FF: `159803` -> `486227` (`3.043x`)
- DSP: `1486` -> `6250` (`4.206x`)
- BRAM18K: `472` -> `6`

Interpretation:

- the analytic precursor update is numerically attractive
- but a direct HLS translation explodes floating-point operator replication and destroys timing closure
- this reinforces the need for the architecture change already outlined in this note: resident multi-step execution, mixed precision, and shared/time-multiplexed floating-point resources instead of a naive full-unroll mapping

Artifacts for the article are under `vitis/analysis_artifacts/precursor_analytic_update_20260618_interleaved/`.

## Deterministic Timing Notes

The manuscript timing claim is the host-intermediated deterministic real-time emulation path:

1. CPU broker commits delayed boundary channels.
2. Core and BOP devices consume precommitted delayed samples.
3. Newly generated boundary values are recorded for future steps.
4. No direct inter-board link is required.

For the current `N=200`, `1 s` R12 timing case:

- same-source CPU C++ split reference: `13.047735 us` per step from `200` timed repeats after `20` warmup repeats
- measured host/JTAG-AXI board wait path: `3.043 ms` per step (`1.496 ms` core wait + `1.547 ms` BOP wait)
- cycle-accounted HLS-only split-pair latency: `321.14..322.34 us` at the deployed `20 ns` clock
- sustained `600`-step host/JTAG budget inferred from the repeated step protocol: `1.826 s` wall time for `600 s` simulated time
- resident transient batch log: `600` consecutive outer steps in `173.623 ms`, or `289.371 us/step`
