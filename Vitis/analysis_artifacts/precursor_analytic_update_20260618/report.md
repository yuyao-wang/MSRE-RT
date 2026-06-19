# Analytic Precursor Update

## Timing

- Timing statistic: median of `5` alternating baseline/analytic runner invocations
- Baseline core avg: `17.844780 us`
- Analytic core avg: `20.823550 us`
- Core speedup: `0.856952x`
- Baseline total avg: `20.783300 us`
- Analytic total avg: `23.505195 us`
- Total speedup: `0.884200x`

## Accuracy vs Physics Reference

| Metric | Baseline Abs Err | Analytic Abs Err | Analytic/Baseline |
| --- | ---: | ---: | ---: |
| `power_W` | 8.012331e+01 | 2.786557e+00 | 0.034778 |
| `phi_mid` | 7.279067e-08 | 2.531540e-09 | 0.034778 |
| `fuel_mid_K` | 3.858402e-02 | 3.857239e-02 | 0.999699 |
| `graphite_mid_K` | 6.254309e-06 | 6.606989e-06 | 1.056390 |
| `Ts_core_outlet_K` | 5.336144e-06 | 2.985998e-06 | 0.559580 |
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

## Core HLS Delta

- Baseline latency: `19079..19139` cycles
- Analytic latency: `undef` cycles
- Baseline estimated clock: `7.672 ns`
- Analytic estimated clock: `3593.586 ns`
- Estimated clock ratio: `468.402763x`
- Mid-latency ratio: `undef`
- LUT: `185984` -> `615052` (`3.307016x`)
- FF: `159803` -> `486227` (`3.042665x`)
- DSP: `1486` -> `6250` (`4.205922x`)
- BRAM18K: `472` -> `6` (`0.012712x`)
