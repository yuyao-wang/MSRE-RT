# Resident Transient Batch Benchmark

## CPU Reference

- Plain C++ total wall time: `2.774466 s`
- Plain C++ per-step wall time: `2774466.417 us`

## Batch Runner

- Resident batch CPU proxy total avg: `35.458 us`
- Resident batch CPU proxy per-step avg: `35.458 us`

## Final Diagnostics Error vs Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 2.388759e-04 | 2.741774e-02 |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | 8.087293e+01 | 8.207837e-06 |
| `fuel_mid` | 3.260076e+01 | 3.640081e-02 |
| `graphite_mid` | 3.742292e+01 | 2.391320e-02 |
| `core_inlet` | 3.288629e+01 | 3.732657e-02 |
| `core_outlet` | 3.541789e+01 | 3.898121e-02 |
| `hx1_hot_outlet` | 3.244730e+01 | 3.682845e-02 |
| `hx1_cold_outlet` | 3.552462e+01 | 3.909216e-02 |
| `hx2_hot_outlet` | 2.016631e+01 | 2.374366e-02 |
| `hx2_cold_outlet` | 3.760286e+01 | 4.133625e-02 |
| `brayton_return` | 3.488127e+01 | 4.028049e-02 |

## Final Axial State Error

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 7.842125e-03 | 3.393898e-03 |
| `fuel_temp` | 1.155623e+02 | 4.564053e+01 |
| `graphite_temp` | 5.333212e+02 | 2.766631e+02 |
| `C1` | 2.803944e-08 | 1.914061e-08 |
| `C2` | 9.134492e-08 | 6.251359e-08 |
| `C3` | 6.104938e-08 | 4.284368e-08 |
| `C4` | 4.398400e-08 | 3.009312e-08 |
| `C5` | 2.744092e-09 | 1.832418e-09 |
| `C6` | 1.064379e-09 | 5.563715e-10 |