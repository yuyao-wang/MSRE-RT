# Resident Transient Batch Benchmark

## CPU Reference

- Plain C++ total wall time: `5.363019 s`
- Plain C++ per-step wall time: `8938.366 us`

## Batch Runner

- Resident batch CPU proxy total avg: `7777.084 us`
- Resident batch CPU proxy per-step avg: `12.962 us`

## Final Diagnostics Error vs Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | nan | nan |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | nan | nan |
| `fuel_mid` | nan | nan |
| `graphite_mid` | nan | nan |
| `core_inlet` | nan | nan |
| `core_outlet` | nan | nan |
| `hx1_hot_outlet` | nan | nan |
| `hx1_cold_outlet` | nan | nan |
| `hx2_hot_outlet` | nan | nan |
| `hx2_cold_outlet` | nan | nan |
| `brayton_return` | 2.300691e+02 | 2.619141e-01 |

## Final Axial State Error

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | nan | nan |
| `fuel_temp` | nan | nan |
| `graphite_temp` | nan | nan |
| `C1` | nan | nan |
| `C2` | nan | nan |
| `C3` | nan | nan |
| `C4` | nan | nan |
| `C5` | nan | nan |
| `C6` | nan | nan |