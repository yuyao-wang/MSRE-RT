# Resident Transient Batch Benchmark

## CPU Baselines

- Plain C++ total wall time: `4.991822 s`
- Plain C++ per-step wall time: `8319.704 us`
- Resident batch vs full-program plain C++ speedup: `29.456x`
- Same-init plain C++ total avg: `300567.083 us`
- Same-init plain C++ per-step avg: `500.945 us`
- Resident batch vs same-init plain C++ speedup: `1.774x`

## Batch Runner

- Resident batch CPU proxy total avg: `169467.041 us`
- Resident batch CPU proxy per-step avg: `282.445 us`

## Final Diagnostics Error vs Same-Init Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 5.765713e-06 | 6.464003e-04 |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | 6.105308e+03 | 6.234669e-04 |
| `fuel_mid` | 1.442339e-01 | 1.590605e-04 |
| `graphite_mid` | 2.295910e+00 | 1.455620e-03 |
| `core_inlet` | 1.772129e-01 | 1.984024e-04 |
| `core_outlet` | 1.103918e-01 | 1.200733e-04 |
| `hx1_hot_outlet` | 1.783337e-01 | 1.996105e-04 |
| `hx1_cold_outlet` | 9.113665e-02 | 9.918710e-05 |
| `hx2_hot_outlet` | 2.303009e-01 | 2.688086e-04 |
| `hx2_cold_outlet` | 8.976513e-02 | 9.782865e-05 |
| `brayton_return` | 9.064307e-02 | 1.038505e-04 |

## Final Diagnostics Error vs Python Reference

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 6.583860e-07 | 7.375924e-05 |
| `rho` | 0.000000e+00 | 0.000000e+00 |
| `power` | 6.285823e+02 | 6.414598e-05 |
| `fuel_mid` | 1.961595e-01 | 2.163115e-04 |
| `graphite_mid` | 1.807554e-01 | 1.144203e-04 |
| `core_inlet` | 1.951187e-01 | 2.184448e-04 |
| `core_outlet` | 1.975174e-01 | 2.148195e-04 |
| `hx1_hot_outlet` | 1.956882e-01 | 2.190313e-04 |
| `hx1_cold_outlet` | 1.995132e-01 | 2.171113e-04 |
| `hx2_hot_outlet` | 2.840213e-01 | 3.314906e-04 |
| `hx2_cold_outlet` | 2.039973e-01 | 2.222945e-04 |
| `brayton_return` | 1.884594e-01 | 2.158952e-04 |

## Final Axial State Error vs Same-Init Plain C++

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 5.765713e-06 | 4.169794e-06 |
| `fuel_temp` | 1.772129e-01 | 1.463656e-01 |
| `graphite_temp` | 2.295910e+00 | 1.635327e+00 |
| `C1` | 6.036973e-08 | 2.806088e-08 |
| `C2` | 3.145909e-09 | 1.945445e-09 |
| `C3` | 1.197269e-10 | 7.920979e-11 |
| `C4` | 4.430180e-11 | 3.143898e-11 |
| `C5` | 4.058180e-12 | 2.220905e-12 |
| `C6` | 1.507912e-09 | 5.839100e-10 |

## Final Axial State Error vs Python Reference

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 6.584494e-07 | 4.744075e-07 |
| `fuel_temp` | 1.975426e-01 | 1.964199e-01 |
| `graphite_temp` | 2.524382e-01 | 1.595186e-01 |
| `C1` | 3.801412e-11 | 3.770279e-11 |
| `C2` | 3.322124e-11 | 3.123457e-11 |
| `C3` | 6.708641e-12 | 4.867663e-12 |
| `C4` | 4.472048e-12 | 3.228972e-12 |
| `C5` | 3.081433e-13 | 2.233762e-13 |
| `C6` | 9.331492e-14 | 6.760408e-14 |