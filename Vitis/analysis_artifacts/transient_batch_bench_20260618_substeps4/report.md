# Resident Transient Batch Benchmark

## CPU Reference

- Plain C++ total wall time: `5.131766 s`
- Plain C++ per-step wall time: `8552.943 us`

## Batch Runner

- Resident batch CPU proxy total avg: `32932.500 us`
- Resident batch CPU proxy per-step avg: `54.888 us`

## Final Diagnostics Error vs Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | nan | nan |
| `rho` | 5.587935e-11 | 2.235174e-08 |
| `power` | nan | nan |
| `fuel_mid` | nan | nan |
| `graphite_mid` | nan | nan |
| `core_inlet` | nan | nan |
| `core_outlet` | nan | nan |
| `hx1_hot_outlet` | nan | nan |
| `hx1_cold_outlet` | nan | nan |
| `hx2_hot_outlet` | nan | nan |
| `hx2_cold_outlet` | nan | nan |
| `brayton_return` | 1.058810e+03 | 6.202190e-01 |

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