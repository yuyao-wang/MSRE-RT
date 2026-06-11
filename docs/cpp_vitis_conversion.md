# MSR1D Python -> Plain C++ -> Vitis HLS Conversion Notes

## Deliverables

- Plain C++ reference solver: [`cpp/msr_plain.cpp`](../cpp/msr_plain.cpp)
- Plain C++ build file: [`cpp/CMakeLists.txt`](../cpp/CMakeLists.txt)
- Vitis HLS kernel-oriented implementation: [`vitis/msr_vitis_kernel.cpp`](../vitis/msr_vitis_kernel.cpp)
- Vitis syntax-check build file: [`vitis/CMakeLists.txt`](../vitis/CMakeLists.txt)

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

## Current Limitations

- The plain C++ reference is runnable and writes CSV traces.
- The Vitis deliverable is kernel-level HLS code, not a complete XRT host application.
- The HLS version uses fixed-step RK4 substeps instead of the Python adaptive RK4.
  - This is intentional for deterministic scheduling.
- Exact offline-vs-HLS numerical agreement still needs a dedicated comparison harness.

## Immediate Next Step

If the next milestone is hardware bring-up, the most useful follow-up is:

1. add a small XRT host wrapper around `msr_step_kernel`
2. export one Python reference case into static arrays
3. compare `phi_mid`, `power`, `Ts_core_L`, and `rho` step-by-step
