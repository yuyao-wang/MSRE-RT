# FPGA vs Software One-Step Comparison

## Scope

- Board run: remote `offline_snapshot` clean retry on VCU118 split-kernel image.
- CPU one-step kernel reference: local `msr_vcu118_sw_timed.cpp` compiled for `N=200`, `hardware_substeps=1` on the same snapshot bytes.
- Physics reference: local `generate_parameters(..., steady_state_steps=180)` + `run_coupled_transient(..., 1)`.
- Python timing below is monolithic one-step `run_coupled_transient(..., 1)` timing; it is compared against combined `core+bop` FPGA time, not per-kernel split timings.
- HLS cycle summary below is from the aggressive resynthesis captured on `2026-06-17`.
- The aggressive HLS resource numbers are independent per-kernel estimates. Their DSP counts sum to `7224`, which exceeds the VCU118 limit of `6840`, so they are not a simultaneous-placement claim.
- Schedule state/operator CSVs are synthesis-schedule artifacts, not live on-board waveforms.

## Remote Run Inputs

- `Ts_core_inlet_K` = `904.994102683571`
- `rod_position` = `0.000000000000`
- `external_reactivity` = `0.000000000000`
- `Ts_HX1_L_K` = `938.312653156975`
- `Tss_HX1_0_K` = `815.610318342466`
- `Tss_HX2_L_K` = `896.122504990044`
- `Tsss_HX2_0_K` = `807.100862284530`

## Board vs CPU Kernel

| Metric | Board | CPU Kernel | Abs Diff | Rel Diff |
| --- | ---: | ---: | ---: | ---: |
| `rho` | -0.000000000000 | -0.000000000000 | 0.000e+00 | -0.000e+00 |
| `power_W` | 99382.890710337626 | 99382.890710337626 | 0.000e+00 | 0.000e+00 |
| `phi_mid` | 1.433989757311 | 1.433989757311 | 0.000e+00 | 0.000e+00 |
| `fuel_mid_K` | 928.899968010081 | 928.899968010081 | 0.000e+00 | 0.000e+00 |
| `graphite_mid_K` | 934.312747462512 | 934.312747462512 | 0.000e+00 | 0.000e+00 |
| `Ts_core_outlet_K` | 938.345660332482 | 938.345660332482 | 0.000e+00 | 0.000e+00 |
| `Ts_HX1_0_K` | 904.956069709312 | 904.956069709312 | 0.000e+00 | 0.000e+00 |
| `Tss_HX1_L_K` | 896.021394503898 | 896.021394503898 | 0.000e+00 | 0.000e+00 |
| `Tss_HX2_0_K` | 816.267385347708 | 816.267385347708 | 0.000e+00 | 0.000e+00 |
| `Tsss_HX2_L_K` | 846.499708942271 | 846.499708942271 | 0.000e+00 | 0.000e+00 |
| `Tsss_pp_0_K` | 807.980106281558 | 807.980106281558 | 0.000e+00 | 0.000e+00 |

## Board vs Physics Reference

| Metric | Board | Physics Ref | Abs Diff | Rel Diff |
| --- | ---: | ---: | ---: | ---: |
| `rho` | -0.000000000000 | 0.000000000000 | -2.220e-16 | 0.000e+00 |
| `power_W` | 99382.890710337626 | 99382.890710189677 | 1.479e-07 | 1.489e-12 |
| `phi_mid` | 1.433989757311 | 1.433989757297 | 1.341e-11 | 9.349e-12 |
| `fuel_mid_K` | 928.899968010081 | 928.899968010081 | -1.137e-13 | -1.224e-16 |
| `graphite_mid_K` | 934.312747462512 | 934.312747462512 | 2.274e-13 | 2.434e-16 |
| `Ts_core_outlet_K` | 938.345660332482 | 938.345660332482 | 0.000e+00 | 0.000e+00 |
| `Ts_HX1_0_K` | 904.956069709312 | 904.956074091238 | -4.382e-06 | -4.842e-09 |
| `Tss_HX1_L_K` | 896.021394503898 | 896.021396081329 | -1.577e-06 | -1.760e-09 |
| `Tss_HX2_0_K` | 816.267385347708 | 816.267392452220 | -7.105e-06 | -8.704e-09 |
| `Tsss_HX2_L_K` | 846.499708942271 | 846.499705378176 | 3.564e-06 | 4.210e-09 |
| `Tsss_pp_0_K` | 807.980106281558 | 807.607930660572 | 3.722e-01 | 4.608e-04 |

## HLS Cycle Summary

| Kernel | Latency (cycles) | HLS Est. Clock (ns) | Latency at deployed 20 ns clock (us) | LUT | FF | DSP | BRAM |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `core_step_kernel_n200_s1` | 13723..13783 | 7.672 | 274.460..275.660 | 686798 | 622831 | 6034 | 40 |
| `bop_step_kernel_n200_s1` | 2334..2334 | 7.419 | 46.680..46.680 | 164114 | 127440 | 1190 | 48 |

Note: the last latency column is computed as cycles × `20.0 ns` for comparison with the deployed board clock; it is not derived from the HLS-estimated clock.

## Aggressive HLS Delta vs Previous Build

| Kernel | Previous HLS Mid (us) | New HLS Mid (us) | New/Prev | LUT x | FF x | DSP x | BRAM x |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `core` | 382.180 | 275.060 | 0.7197x | 3.69x | 3.90x | 4.06x | 0.08x |
| `bop` | 66.460 | 46.680 | 0.7024x | 2.16x | 2.61x | 2.74x | 0.46x |

## Python vs FPGA Timing

| Reference | Python Avg (us) | FPGA HLS Mid (us) | FPGA Wait (us) | FPGA/Python Speedup from HLS | FPGA/Python Speedup from Wait |
| --- | ---: | ---: | ---: | ---: | ---: |
| `coupled_one_step` | 18339.542 | 321.740 | 3043.000 | 57.00112x | 6.02680x |

## Remote Host Timing

- `clean_retry_status.log` total wall time: `75.000 s`
- Bitstream: `C:\Users\yuyao\MSR1DPython_vitis\b_clean\outputs\msr_split_vcu118.bit`
- CPU timed runner: repeats `200`, warmup `20`, checksum `22041991.579656`
- Python timed reference: repeats `20`, warmup `2`, avg `18339.542 us`

| Kernel | Reg Write (ms) | AP Start Write (ms) | Exec Wait (ms) | Total (ms) | Polls |
| --- | ---: | ---: | ---: | ---: | ---: |
| `bop` | 10.993 | 1.292 | 1.547 | 13.951 | 1 |
| `core` | 9.667 | 1.329 | 1.496 | 12.666 | 1 |

## Schedule Artifacts

- `core_step_kernel_n200_s1`: 3 states, states CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/core_step_kernel_n200_s1_states.csv`, ops CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/core_step_kernel_n200_s1_operations.csv`, cycle trace CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/core_step_kernel_n200_s1_cycle_trace.csv`
- `bop_step_kernel_n200_s1`: 3 states, states CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/bop_step_kernel_n200_s1_states.csv`, ops CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/bop_step_kernel_n200_s1_operations.csv`, cycle trace CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/bop_step_kernel_n200_s1_cycle_trace.csv`
- `cross_sections_kernel`: 32 states, states CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/cross_sections_kernel_states.csv`, ops CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/cross_sections_kernel_operations.csv`, cycle trace CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/cross_sections_kernel_cycle_trace.csv`
- `neutronics_kernel`: 61 states, states CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/neutronics_kernel_states.csv`, ops CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/neutronics_kernel_operations.csv`, cycle trace CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/neutronics_kernel_cycle_trace.csv`
- `thermal_kernel`: 19 states, states CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/thermal_kernel_states.csv`, ops CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/thermal_kernel_operations.csv`, cycle trace CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/thermal_kernel_cycle_trace.csv`
- `hx_kernel`: 18 states, states CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/hx_kernel_states.csv`, ops CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/hx_kernel_operations.csv`, cycle trace CSV `/Users/ouuyou/Project/MSRE_Project/MSR1DPython/vitis/analysis_artifacts/fpga_compare_20260617/hx_kernel_cycle_trace.csv`
