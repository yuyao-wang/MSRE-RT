# Resident Transient Batch Benchmark

## CPU Reference

- Plain C++ total wall time: `5.265511 s`
- Plain C++ per-step wall time: `8775.851 us`

## Batch Runner

- Resident batch CPU proxy total avg: `183427.959 us`
- Resident batch CPU proxy per-step avg: `305.713 us`

## Final Diagnostics Error vs Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 8.487334e-04 | 6.600080e-02 |
| `rho` | 1.263106e-12 | 2.526212e-08 |
| `power` | 1.263981e+06 | 9.195116e-02 |
| `fuel_mid` | 5.610809e+00 | 6.117890e-03 |
| `graphite_mid` | 2.511798e+01 | 1.494086e-02 |
| `core_inlet` | 5.673402e+00 | 6.307087e-03 |
| `core_outlet` | 4.901592e+00 | 5.255611e-03 |
| `hx1_hot_outlet` | 5.596630e+00 | 6.220701e-03 |
| `hx1_cold_outlet` | 4.749355e+00 | 5.097673e-03 |
| `hx2_hot_outlet` | 2.666531e+00 | 3.091834e-03 |
| `hx2_cold_outlet` | 4.107728e+00 | 4.421172e-03 |
| `brayton_return` | 3.918411e+00 | 4.435709e-03 |

## Final Axial State Error

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 1.202929e-02 | 5.045274e-03 |
| `fuel_temp` | 2.777852e+01 | 1.993891e+01 |
| `graphite_temp` | 6.901841e+02 | 3.113152e+02 |
| `C1` | 6.841765e-08 | 5.842604e-08 |
| `C2` | 6.000577e-08 | 4.018642e-08 |
| `C3` | 7.783834e-08 | 5.436451e-08 |
| `C4` | 5.779666e-08 | 3.943178e-08 |
| `C5` | 3.852063e-09 | 2.439708e-09 |
| `C6` | 1.644342e-09 | 7.651736e-10 |