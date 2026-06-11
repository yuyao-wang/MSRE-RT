# Mixed Precision Migration Plan

This document proposes a staged mixed-precision migration for the Vitis HLS kernel. The goal is to reduce BRAM pressure, DSP cost, routing pressure, and synthesis time without immediately destabilizing the neutronics physics.

The plan assumes a conservative order:

1. keep the numerically sensitive reductions and feedback paths in `double`
2. convert storage-heavy thermal and heat-exchanger state to `float`
3. only then evaluate fixed-point for bounded, well-scaled sub-domains

## Keep In Double First

These values should stay in `double` in the first mixed-precision pass because they either dominate numerical stability or amplify small errors globally.

### Global reductions and diagnostics

- `trapz_uniform()` accumulator path
- `estimate_global_rho()` final production / absorption ratio
- top-level `rho`
- top-level `power`

Reason:

- these are global reductions
- they feed diagnostics and reactivity interpretation
- accumulated rounding error is more visible here than in local transport-like state

### Neutronics state and coefficients

- `StepState.phi1[:]`
- `StepState.phi2[:]`
- `StepState.C[:, :]`
- `CrossSections.D[:, :]`
- `CrossSections.sigma_a[:, :]`
- `CrossSections.sigma_s12[:]`
- `CrossSections.nu_sigma_f[:, :]`
- `CrossSections.sigma_f[:, :]`
- `CrossSections.sigma_r[:, :]`
- `KernelParams.beta[:]`
- `KernelParams.lambda_i[:]`
- `KernelParams.neutron_velocity[:]`
- `KernelParams.nu[:]`
- `KernelParams.chi_p[:]`
- `KernelParams.chi_d[:]`
- `KernelParams.d_e[:]`
- `KernelParams.reference_multiplication_ratio`

Reason:

- this is the most stiffness-sensitive and feedback-sensitive part of the model
- delayed neutron balance and diffusion feedback are the least attractive place to introduce coarse quantization first

### Brayton / transcendental path

- `brayton_kernel()` internal arithmetic
- variables passed into `pow()`

Reason:

- this path already uses expensive transcendental arithmetic
- changing precision here complicates interpretation because arithmetic, library implementation, and timing all move at once

## Convert To Float First

These are the best first-pass candidates because they are storage-heavy, spatially local, and less globally sensitive than neutronics.

### Thermal state

- `StepState.fuel[:]`
- `StepState.graphite[:]`
- `KernelParams.T_s_ref[:]`
- `KernelParams.T_gr_ref[:]`
- `q_prime[:]` storage

Reason:

- large arrays
- strong impact on BRAM and routing
- local truncation error is easier to monitor

Implementation note:

- keep `thermal_rhs()` arithmetic and the final heat-balance reductions in `double` at first
- use `float` for stored field values, cast up on load, cast down on writeback

### Heat exchanger state

- `StepState.hx1_hot[:]`
- `StepState.hx1_cold[:]`
- `StepState.hx2_hot[:]`
- `StepState.hx2_cold[:]`
- HX inlet / outlet delay payload values

Reason:

- very storage-heavy
- mostly advection / exchange dominated
- easier to validate against the plain C++ reference with tolerance bands

### Delay and history storage

- `DelayLine.data[:]`
- `PrecursorHistory.outlet_history[:, :]`
- `PrecursorHistory.last_outlet[:]`

Reason:

- these structures consume memory across many time steps
- even if precursor arithmetic remains `double`, archived history is a practical place to save memory first

Implementation note:

- if precursor-loop stability changes too much, keep `PrecursorHistory.last_outlet[:]` in `double` and only demote the ring-buffer storage

### Geometry and slowly varying parameters

- `KernelParams.z[:]`
- `KernelParams.A_f[:]`
- HX velocities and exchange coefficients
- prescribed inlet / outlet temperatures

Reason:

- these do not need full 53-bit mantissa precision
- demoting them reduces memory traffic with very low physics risk

## Good Candidates For Later `ap_fixed`

Only attempt these after the `float` pass is validated.

### Control and mode variables

- mode flags
- delay step counters
- bounded interpolation weights
- rod position if its range is explicitly bounded

Reason:

- naturally bounded
- straightforward scaling

### Geometry and normalized profile data

- `rod_shape[:, :]`
- interpolation weights
- normalized axial profiles

Reason:

- bounded ranges make fixed-point practical
- can materially reduce BRAM

### Delay-line and HX temperatures after range study

- HX temperature arrays
- delay-line payloads

Reason:

- if operating temperature ranges are well bounded, fixed-point may be viable
- this should come only after collecting min/max traces from the plain C++ reference

## Do Not Start With `ap_fixed` Here

- neutronics flux state
- precursor state
- global `rho`
- global `power`
- any path feeding `pow()` or exponentials

Reason:

- these combine stiffness, feedback, and global accumulation
- debugging fixed-point error here is too expensive for the first migration

## Recommended Rollout Order

1. Convert `z[:]`, `A_f[:]`, HX/thermal stored temperatures, and `q_prime[:]` storage to `float`
2. Keep arithmetic in `double` where reductions or feedback are involved
3. Re-run plain C++ vs HLS-oriented kernel comparisons on short transients
4. If stable, demote delay/history storage
5. Only after that, evaluate selected `ap_fixed` replacements for bounded geometry and delay payloads

## Validation Checklist

- compare `phi_mid`, `rho`, `power`
- compare core inlet / outlet temperatures
- compare HX outlet temperatures
- compare transient shape, not just final point values
- track relative error and worst-case absolute error over the whole run
