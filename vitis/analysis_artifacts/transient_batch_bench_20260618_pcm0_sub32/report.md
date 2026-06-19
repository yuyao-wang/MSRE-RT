# Resident Transient Batch Benchmark

## CPU Reference

- Plain C++ total wall time: `5.379019 s`
- Plain C++ per-step wall time: `8965.031 us`

## Batch Runner

- Resident batch CPU proxy total avg: `175180.958 us`
- Resident batch CPU proxy per-step avg: `291.968 us`

## Final Diagnostics Error vs Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 3.531263e-04 | 4.119358e-02 |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | 2.538549e+05 | 2.659625e-02 |
| `fuel_mid` | 6.501382e+00 | 7.119780e-03 |
| `graphite_mid` | 2.516845e+00 | 1.595917e-03 |
| `core_inlet` | 5.984216e+00 | 6.656478e-03 |
| `core_outlet` | 6.458416e+00 | 6.976654e-03 |
| `hx1_hot_outlet` | 5.912529e+00 | 6.575741e-03 |
| `hx1_cold_outlet` | 6.394696e+00 | 6.912144e-03 |
| `hx2_hot_outlet` | 3.761082e+00 | 4.371941e-03 |
| `hx2_cold_outlet` | 6.077660e+00 | 6.580667e-03 |
| `brayton_return` | 5.681857e+00 | 6.468313e-03 |

## Final Axial State Error

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 7.825886e-03 | 3.346465e-03 |
| `fuel_temp` | 2.418814e+01 | 1.757330e+01 |
| `graphite_temp` | 5.792529e+02 | 2.699257e+02 |
| `C1` | 2.426221e-08 | 1.607342e-08 |
| `C2` | 8.419514e-08 | 5.716339e-08 |
| `C3` | 5.820168e-08 | 4.079962e-08 |
| `C4` | 4.199215e-08 | 2.866935e-08 |
| `C5` | 2.609396e-09 | 1.752264e-09 |
| `C6` | 1.065063e-09 | 5.367198e-10 |