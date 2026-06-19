# Resident Transient Batch Benchmark

## CPU Baselines

- Point kinetics solver macro: `MSR_POINT_KINETICS_SOLVER=1`
- Plain C++ total wall time: `4.815236 s`
- Plain C++ per-step wall time: `8025.393 us`
- Resident batch vs full-program plain C++ speedup: `25.483x`
- Same-init plain C++ total avg: `298683.167 us`
- Same-init plain C++ per-step avg: `497.805 us`
- Resident batch vs same-init plain C++ speedup: `1.581x`

## Batch Runner

- Resident batch CPU proxy total avg: `188958.625 us`
- Resident batch CPU proxy per-step avg: `314.931 us`

## Final Diagnostics Error vs Same-Init Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 3.649965e-06 | 4.087701e-04 |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | 3.797367e+03 | 3.873909e-04 |
| `fuel_mid` | 2.359275e-01 | 2.601534e-04 |
| `graphite_mid` | 8.143143e-01 | 5.152638e-04 |
| `core_inlet` | 1.975132e-01 | 2.211250e-04 |
| `core_outlet` | 2.975483e-01 | 3.235777e-04 |
| `hx1_hot_outlet` | 1.981166e-01 | 2.217488e-04 |
| `hx1_cold_outlet` | 2.373800e-01 | 2.583076e-04 |
| `hx2_hot_outlet` | 2.983842e-01 | 3.482482e-04 |
| `hx2_cold_outlet` | 2.400333e-01 | 2.615525e-04 |
| `brayton_return` | 2.290664e-01 | 2.624016e-04 |

## Final Diagnostics Error vs Python Reference

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 1.945390e-05 | 2.174849e-03 |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | 2.116380e+04 | 2.155220e-03 |
| `fuel_mid` | 2.155350e-01 | 2.376723e-04 |
| `graphite_mid` | 6.964744e-01 | 4.407326e-04 |
| `core_inlet` | 1.983983e-01 | 2.221156e-04 |
| `core_outlet` | 2.312923e-01 | 2.515438e-04 |
| `hx1_hot_outlet` | 1.990410e-01 | 2.227832e-04 |
| `hx1_cold_outlet` | 2.319164e-01 | 2.523638e-04 |
| `hx2_hot_outlet` | 2.968425e-01 | 3.464494e-04 |
| `hx2_cold_outlet` | 2.336352e-01 | 2.545825e-04 |
| `brayton_return` | 2.149619e-01 | 2.462484e-04 |

## Final Axial State Error vs Same-Init Plain C++

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 3.649965e-06 | 2.623737e-06 |
| `fuel_temp` | 2.981359e-01 | 2.443191e-01 |
| `graphite_temp` | 8.339188e-01 | 6.053373e-01 |
| `C1` | 6.865234e-09 | 2.364092e-09 |
| `C2` | 1.965094e-09 | 7.527129e-10 |
| `C3` | 1.060019e-10 | 5.184329e-11 |
| `C4` | 2.738761e-11 | 1.965938e-11 |
| `C5` | 1.855957e-12 | 1.347380e-12 |
| `C6` | 4.210717e-09 | 4.656630e-10 |

## Final Axial State Error vs Python Reference

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 1.945390e-05 | 1.387685e-05 |
| `fuel_temp` | 2.313152e-01 | 2.156597e-01 |
| `graphite_temp` | 7.219771e-01 | 5.195389e-01 |
| `C1` | 3.106609e-10 | 2.727904e-10 |
| `C2` | 5.622953e-10 | 4.454494e-10 |
| `C3` | 2.142631e-10 | 1.510755e-10 |
| `C4` | 1.503237e-10 | 1.079584e-10 |
| `C5` | 1.048122e-11 | 7.511405e-12 |
| `C6` | 3.187720e-12 | 2.276312e-12 |