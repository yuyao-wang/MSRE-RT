# Resident Transient Batch Benchmark

## CPU Reference

- Plain C++ total wall time: `5.253626 s`
- Plain C++ per-step wall time: `8756.043 us`

## Batch Runner

- Resident batch CPU proxy total avg: `7830.042 us`
- Resident batch CPU proxy per-step avg: `13.050 us`

## Final Diagnostics Error vs Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | nan | nan |
| `rho` | 2.374873e-11 | 4.749745e-08 |
| `power` | nan | nan |
| `fuel_mid` | nan | nan |
| `graphite_mid` | nan | nan |
| `core_inlet` | nan | nan |
| `core_outlet` | nan | nan |
| `hx1_hot_outlet` | nan | nan |
| `hx1_cold_outlet` | nan | nan |
| `hx2_hot_outlet` | nan | nan |
| `hx2_cold_outlet` | nan | nan |
| `brayton_return` | 2.430980e+02 | 2.727017e-01 |

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