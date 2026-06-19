# Hardware Results

This page summarizes the hardware-oriented evidence currently tracked in the
artifact. The detailed source of truth remains the checked reports and analysis
artifacts.

## Front-Page Result Snapshot

| Item | Result |
| --- | --- |
| Hardware platform | Host-mediated VCU118 / dual-FPGA-ready split-kernel workflow |
| Core kernel | `core_step_kernel_n200_s1`, 13,723..13,783 cycles in `fpga_compare_20260617` |
| BOP kernel | `bop_step_kernel_n200_s1`, 2,334 cycles in `fpga_compare_20260617` |
| HLS-only sequential step estimate | 321.74 us |
| Current board wait path | 3,043 us |
| Speedup over Python one-step reference | 57.0x HLS-only; 6.03x current board wait path |

See
`Vitis/analysis_artifacts/fpga_compare_20260617/report.md`
for the timing and readback comparison that feeds this table.

## Synthesis Reports

The curated synthesis reports under `documentation/synthesis_reports/` include
`csynth` reports, schedule XML, design XML, schedule diagrams, and extracted
report bundles.

## Board Evidence

README hardware figures are stored under `documentation/readme_assets/`.
The board setup photo is intentionally kept below the architecture and results
sections so the project homepage first communicates the system workflow.
