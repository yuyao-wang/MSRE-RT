# Resident Transient Batch Benchmark

## CPU Reference

- Plain C++ total wall time: `3.110217 s`
- Plain C++ per-step wall time: `311021.721 us`

## Batch Runner

- Resident batch CPU proxy total avg: `1521.750 us`
- Resident batch CPU proxy per-step avg: `152.175 us`

## Final Diagnostics Error vs Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | nan | nan |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | nan | nan |
| `fuel_mid` | nan | nan |
| `graphite_mid` | nan | nan |
| `core_inlet` | 3.209568e+01 | 3.642929e-02 |
| `core_outlet` | nan | nan |
| `hx1_hot_outlet` | 3.166470e+01 | 3.593979e-02 |
| `hx1_cold_outlet` | 6.569960e+02 | 7.230173e-01 |
| `hx2_hot_outlet` | 1.991422e+01 | 2.344726e-02 |
| `hx2_cold_outlet` | 3.690242e+01 | 4.057229e-02 |
| `brayton_return` | 3.424835e+01 | 3.955574e-02 |

## Final Axial State Error

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | nan | nan |
| `fuel_temp` | 3.209568e+01 | nan |
| `graphite_temp` | nan | nan |
| `C1` | nan | nan |
| `C2` | nan | nan |
| `C3` | nan | nan |
| `C4` | nan | nan |
| `C5` | nan | nan |
| `C6` | nan | nan |