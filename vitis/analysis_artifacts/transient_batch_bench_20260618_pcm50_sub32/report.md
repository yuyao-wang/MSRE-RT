# Resident Transient Batch Benchmark

## CPU Reference

- Plain C++ total wall time: `5.481054 s`
- Plain C++ per-step wall time: `9135.090 us`

## Batch Runner

- Resident batch CPU proxy total avg: `198228.917 us`
- Resident batch CPU proxy per-step avg: `330.382 us`

## Final Diagnostics Error vs Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 1.539528e-03 | 1.252196e-01 |
| `rho` | 2.374873e-11 | 4.749745e-08 |
| `power` | 2.722106e+06 | 2.205580e-01 |
| `fuel_mid` | 3.214228e+00 | 3.489329e-03 |
| `graphite_mid` | 1.561401e+02 | 8.345063e-02 |
| `core_inlet` | 5.141948e+00 | 5.706496e-03 |
| `core_outlet` | 4.968406e-01 | 5.292013e-04 |
| `hx1_hot_outlet` | 5.072907e+00 | 5.629084e-03 |
| `hx1_cold_outlet` | 2.896706e-01 | 3.085978e-04 |
| `hx2_hot_outlet` | 7.257418e-01 | 8.366480e-04 |
| `hx2_cold_outlet` | 4.584352e-02 | 4.889043e-05 |
| `brayton_return` | 1.070764e-02 | 1.201158e-05 |

## Final Axial State Error

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 1.213397e-02 | 4.882742e-03 |
| `fuel_temp` | 2.915093e+01 | 2.086470e+01 |
| `graphite_temp` | 9.705302e+02 | 3.978094e+02 |
| `C1` | 8.277170e-06 | 3.782545e-06 |
| `C2` | 1.277335e-07 | 4.374091e-08 |
| `C3` | 6.194309e-08 | 4.328835e-08 |
| `C4` | 4.707270e-08 | 3.209857e-08 |
| `C5` | 4.023030e-09 | 2.077573e-09 |
| `C6` | 1.661542e-09 | 6.897161e-10 |