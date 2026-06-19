# Resident Transient Batch Benchmark

## CPU Reference

- Plain C++ total wall time: `2.833862 s`
- Plain C++ per-step wall time: `283386.213 us`

## Batch Runner

- Resident batch CPU proxy total avg: `2973.083 us`
- Resident batch CPU proxy per-step avg: `297.308 us`

## Final Diagnostics Error vs Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 2.391683e-04 | 2.745245e-02 |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | 1.211664e+03 | 1.229959e-04 |
| `fuel_mid` | 3.322545e+01 | 3.709854e-02 |
| `graphite_mid` | 3.693634e+01 | 2.359638e-02 |
| `core_inlet` | 3.209629e+01 | 3.642998e-02 |
| `core_outlet` | 3.375269e+01 | 3.714891e-02 |
| `hx1_hot_outlet` | 3.166452e+01 | 3.593959e-02 |
| `hx1_cold_outlet` | 3.475577e+01 | 3.824836e-02 |
| `hx2_hot_outlet` | 1.991392e+01 | 2.344690e-02 |
| `hx2_cold_outlet` | 3.690273e+01 | 4.057262e-02 |
| `brayton_return` | 3.424847e+01 | 3.955588e-02 |

## Final Axial State Error

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 7.842082e-03 | 3.393773e-03 |
| `fuel_temp` | 5.111025e+01 | 4.338371e+01 |
| `graphite_temp` | 5.342128e+02 | 2.766909e+02 |
| `C1` | 2.802951e-08 | 1.894673e-08 |
| `C2` | 9.131954e-08 | 6.248856e-08 |
| `C3` | 6.103423e-08 | 4.283359e-08 |
| `C4` | 4.397189e-08 | 3.008535e-08 |
| `C5` | 2.743208e-09 | 1.831900e-09 |
| `C6` | 1.064317e-09 | 5.562301e-10 |