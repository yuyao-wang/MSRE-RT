# Resident Transient Batch Benchmark

## CPU Baselines

- Plain C++ total wall time: `4.992731 s`
- Plain C++ per-step wall time: `8321.218 us`
- Resident batch vs full-program plain C++ speedup: `28.685x`
- Same-init plain C++ total avg: `302040.583 us`
- Same-init plain C++ per-step avg: `503.401 us`
- Resident batch vs same-init plain C++ speedup: `1.735x`

## Batch Runner

- Resident batch CPU proxy total avg: `174050.958 us`
- Resident batch CPU proxy per-step avg: `290.085 us`

## Final Diagnostics Error vs Same-Init Plain C++

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 2.812423e-04 | 1.992450e-02 |
| `rho` | 2.374873e-11 | 4.749745e-08 |
| `power` | 3.065394e+05 | 1.994329e-02 |
| `fuel_mid` | 5.992013e-01 | 6.523379e-04 |
| `graphite_mid` | 2.833011e+00 | 1.399464e-03 |
| `core_inlet` | 1.630741e-01 | 1.819840e-04 |
| `core_outlet` | 1.082714e+00 | 1.152515e-03 |
| `hx1_hot_outlet` | 1.649374e-01 | 1.840228e-04 |
| `hx1_cold_outlet` | 2.729726e-01 | 2.908036e-04 |
| `hx2_hot_outlet` | 1.794913e-01 | 2.070512e-04 |
| `hx2_cold_outlet` | 1.280625e-01 | 1.365487e-04 |
| `brayton_return` | 7.107122e-03 | 7.972763e-06 |

## Final Diagnostics Error vs Python Reference

| Metric | Abs Error | Rel Error |
| --- | ---: | ---: |
| `phi_mid` | 1.383415e-02 | 1.147695e+08 |
| `rho` | 2.374873e-11 | 4.749745e-08 |
| `power` | 1.506401e+07 | 1.259494e+11 |
| `fuel_mid` | 1.273285e+06 | 9.992796e-01 |
| `graphite_mid` | 3.835273e+07 | 9.999471e-01 |
| `core_inlet` | 3.430793e+05 | 9.973954e-01 |
| `core_outlet` | 1.962512e+06 | 9.995221e-01 |
| `hx1_hot_outlet` | 3.383564e+05 | 9.973585e-01 |
| `hx1_cold_outlet` | 2.014378e+06 | 9.995341e-01 |
| `hx2_hot_outlet` | 1.156663e+06 | 9.992512e-01 |
| `hx2_cold_outlet` | 2.152398e+06 | 9.995645e-01 |
| `brayton_return` | 2.001633e+06 | 9.995548e-01 |

## Final Axial State Error vs Same-Init Plain C++

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 2.812423e-04 | 2.007698e-04 |
| `fuel_temp` | 1.174292e+00 | 7.461148e-01 |
| `graphite_temp` | 2.835854e+00 | 2.031679e+00 |
| `C1` | 1.578758e-05 | 1.039814e-05 |
| `C2` | 1.977920e-07 | 1.351957e-07 |
| `C3` | 2.804978e-09 | 2.016920e-09 |
| `C4` | 2.186873e-09 | 1.572202e-09 |
| `C5` | 1.523473e-10 | 1.092362e-10 |
| `C6` | 1.899951e-08 | 2.681581e-09 |

## Final Axial State Error vs Python Reference

| Series | Max Abs Error | RMS Error |
| --- | ---: | ---: |
| `phi` | 1.383415e-02 | 9.878091e-03 |
| `fuel_temp` | 1.962512e+06 | 1.327780e+06 |
| `graphite_temp` | 5.910129e+07 | 3.945277e+07 |
| `C1` | 5.571776e-04 | 3.058446e-04 |
| `C2` | 5.577896e-06 | 2.912637e-06 |
| `C3` | 1.576482e-07 | 1.125220e-07 |
| `C4` | 1.077236e-07 | 7.740545e-08 |
| `C5` | 7.479352e-09 | 5.365976e-09 |
| `C6` | 2.272150e-09 | 1.624492e-09 |