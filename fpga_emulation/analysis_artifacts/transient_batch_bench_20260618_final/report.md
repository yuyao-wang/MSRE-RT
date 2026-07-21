# Resident Transient Batch Benchmark

## CPU Reference

- Plain C++ total wall time: `5.199357 s`
- Plain C++ per-step wall time: `8665.595 us`

## Batch Runner

- Resident batch CPU proxy total avg: `173622.667 us`
- Resident batch CPU proxy per-step avg: `289.371 us`

## Final Diagnostics Error vs Python Reference

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 1.945390e-05 | 2.174848e-03 |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | 2.116379e+04 | 2.155220e-03 |
| `fuel_mid` | 2.155350e-01 | 2.376723e-04 |
| `graphite_mid` | 6.964744e-01 | 4.407326e-04 |
| `core_inlet` | 1.983983e-01 | 2.221156e-04 |
| `core_outlet` | 2.312923e-01 | 2.515438e-04 |
| `hx1_hot_outlet` | 1.990410e-01 | 2.227832e-04 |
| `hx1_cold_outlet` | 2.319164e-01 | 2.523638e-04 |
| `hx2_hot_outlet` | 2.968425e-01 | 3.464494e-04 |
| `hx2_cold_outlet` | 2.336352e-01 | 2.545825e-04 |
| `brayton_return` | 2.149619e-01 | 2.462484e-04 |

## Final Axial State Error

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 1.945390e-05 | 1.387685e-05 |
| `fuel_temp` | 2.313152e-01 | 2.156597e-01 |
| `graphite_temp` | 7.219771e-01 | 5.195431e-01 |
| `C1` | 3.106657e-10 | 2.727929e-10 |
| `C2` | 5.623000e-10 | 4.454509e-10 |
| `C3` | 2.142630e-10 | 1.510754e-10 |
| `C4` | 1.503237e-10 | 1.079584e-10 |
| `C5` | 1.048122e-11 | 7.511403e-12 |
| `C6` | 3.187719e-12 | 2.276312e-12 |