# Analytic Precursor Update

## Timing

- Timing statistic: median of `5` independent runner invocations
- Baseline core avg: `16.786060 us`
- Analytic core avg: `16.779800 us`
- Core speedup: `1.000373x`
- Baseline total avg: `19.616905 us`
- Analytic total avg: `18.919570 us`
- Total speedup: `1.036858x`

## Accuracy vs Physics Reference

| Metric | Baseline Abs Err | Analytic Abs Err | Analytic/Baseline |
| --- | ---: | ---: | ---: |
| `power_W` | 8.012330e+01 | 2.786550e+00 | 0.034778 |
| `phi_mid` | 7.279066e-08 | 2.531533e-09 | 0.034778 |
| `fuel_mid_K` | 3.858402e-02 | 3.857239e-02 | 0.999699 |
| `graphite_mid_K` | 6.254307e-06 | 6.606991e-06 | 1.056390 |
| `Ts_core_outlet_K` | 5.336143e-06 | 2.985998e-06 | 0.559580 |
| `Ts_HX1_0_K` | 7.284111e-04 | 7.284111e-04 | 1.000000 |
| `Tss_HX1_L_K` | 9.541793e-03 | 9.541793e-03 | 1.000000 |
| `Tss_HX2_0_K` | 2.019352e-03 | 2.019352e-03 | 1.000000 |
| `Tsss_HX2_L_K` | 5.959324e-03 | 5.959324e-03 | 1.000000 |
| `Tsss_pp_0_K` | 3.215546e-01 | 3.215546e-01 | 1.000000 |

## Reference Snapshot

- `Ts_core_inlet` = `848.070101351825`
- `Ts_HX1_L` = `873.656187497335`
- `Tss_HX1_0` = `828.922402710882`
- `Tss_HX2_L` = `872.748845722047`
- `Tsss_HX2_0` = `830.677434568028`
