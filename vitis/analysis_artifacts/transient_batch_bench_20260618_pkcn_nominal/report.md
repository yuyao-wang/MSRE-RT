# Resident Transient Batch Benchmark

## CPU Baselines

- Point kinetics solver macro: `MSR_POINT_KINETICS_SOLVER=2`
- Plain C++ total wall time: `4.792635 s`
- Plain C++ per-step wall time: `7987.725 us`
- Resident batch vs full-program plain C++ speedup: `26.602x`
- Same-init plain C++ total avg: `297507.375 us`
- Same-init plain C++ per-step avg: `495.846 us`
- Resident batch vs same-init plain C++ speedup: `1.651x`

## Batch Runner

- Resident batch CPU proxy total avg: `180163.625 us`
- Resident batch CPU proxy per-step avg: `300.273 us`

## Final Diagnostics Error vs Same-Init Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 4.249402e-04 | 4.544606e-02 |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | 4.661496e+05 | 4.541257e-02 |
| `fuel_mid` | 4.674692e-01 | 5.153392e-04 |
| `graphite_mid` | 4.951248e-01 | 3.135540e-04 |
| `core_inlet` | 1.794887e-01 | 2.009498e-04 |
| `core_outlet` | 8.090397e-01 | 8.793251e-04 |
| `hx1_hot_outlet` | 1.807541e-01 | 2.023191e-04 |
| `hx1_cold_outlet` | 2.545637e-01 | 2.770010e-04 |
| `hx2_hot_outlet` | 2.491109e-01 | 2.907574e-04 |
| `hx2_cold_outlet` | 2.290290e-01 | 2.495646e-04 |
| `brayton_return` | 2.365573e-01 | 2.709803e-04 |

## Final Diagnostics Error vs Python Reference

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 1.945391e-05 | 2.174850e-03 |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | 2.116381e+04 | 2.155222e-03 |
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
| `phi` | 4.249402e-04 | 3.028014e-04 |
| `fuel_temp` | 8.103992e-01 | 5.254014e-01 |
| `graphite_temp` | 5.108682e-01 | 3.540876e-01 |
| `C1` | 2.077633e-06 | 5.518995e-07 |
| `C2` | 2.131609e-07 | 5.130050e-08 |
| `C3` | 1.061150e-08 | 4.149827e-09 |
| `C4` | 3.371605e-09 | 2.398789e-09 |
| `C5` | 2.324887e-10 | 1.662903e-10 |
| `C6` | 1.314657e-06 | 1.698873e-07 |

## Final Axial State Error vs Python Reference

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 1.945391e-05 | 1.387686e-05 |
| `fuel_temp` | 2.313152e-01 | 2.156597e-01 |
| `graphite_temp` | 7.219771e-01 | 5.195515e-01 |
| `C1` | 3.106664e-10 | 2.727957e-10 |
| `C2` | 5.623012e-10 | 4.454531e-10 |
| `C3` | 2.142632e-10 | 1.510756e-10 |
| `C4` | 1.503238e-10 | 1.079585e-10 |
| `C5` | 1.048123e-11 | 7.511410e-12 |
| `C6` | 3.187721e-12 | 2.276314e-12 |