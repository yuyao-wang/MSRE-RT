# VCU118 bring-up notes

This repository currently contains HLS synthesis entry points for the two split kernels:

- `core_step_kernel_n200_s1`
- `bop_step_kernel_n200_s1`

The HLS scripts already target `xcvu9p-flga2104-2L-e`, which matches the VCU118 device family.

What is available now:

- HLS synthesis scripts and source for the two kernels
- Vivado hardware-manager helper scripts to detect and program a connected board
- Vitis HLS helper scripts to export the two kernels as Vivado IP
- A reproducible first-pass VCU118 Vivado flow that builds a board-level wrapper and emits a `.bit`
- First-pass host-control tooling that drives the design through `jtag_axi`

What is not available yet:

- No checked-in `.xclbin` or PCIe/XRT host flow
- No autonomous on-FPGA scheduler that chains the two kernels without host intervention

Remote host status checked on 2026-06-15:

- `C:\Xilinx\Vivado\2023.2\bin\vivado.bat` exists
- `C:\Xilinx\Vitis_HLS\2023.2\bin\vitis_hls.bat` exists
- Full `Vitis` was not found
- Vivado Hardware Manager can see one device through Digilent JTAG:
  - target: `localhost:3121/xilinx_tcf/Digilent/210308A62113`
  - device: `xcvu9p_0`
  - part: `xcvu9p`
- The board appeared unconfigured at the time of the check (`DONE=0` before programming)

Current limitation discovered on 2026-06-16:

- The board-level Vivado flow now reaches validated block-design generation and wrapper emission on the remote host.
- Bitstream generation is currently blocked on that machine by a missing Vivado synthesis license for `xcvu9p` / VCU118.

## Windows usage

Detect the connected board:

```bat
windows_vivado_detect_hw.bat
```

Program a bitstream:

```bat
windows_vivado_program_hw.bat path\to\design.bit
windows_vivado_program_hw.bat path\to\design.bit path\to\design.ltx
```

Export both HLS kernels as Vivado IP:

```bat
windows_vitis_hls_export_n200_s1.bat
```

That produces IP under the corresponding HLS project directories, typically:

- `..\hls_export_work\core_step_n200_s1_10ns_lowlane\solution1\impl\ip`
- `..\hls_export_work\bop_step_n200_s1_10ns_lowlane\solution1\impl\ip`

Build the first VCU118 bitstream:

```bat
windows_vivado_build_vcu118_bitstream.bat
```

Outputs are written under:

- `..\build_vcu118\outputs\msr_split_vcu118.bit`
- `..\build_vcu118\outputs\msr_split_vcu118.xsa`

Run a Vivado JTAG-AXI plan:

```bat
windows_vivado_run_jtag_axi_host.bat path\to\plan.tcl
```

Generate a minimal smoke-test payload on a machine with Python 3:

```bat
py -3 msr_vcu118_host.py prepare-smoke --out-dir path\to\host_smoke
```

That produces packed `.bin` / `.hex32` memory images plus a `smoke_plan.tcl` that:

- writes the `core` state and parameter buffers
- writes the `bop` state and parameter buffers
- sets the AXI-Lite pointer/scalar arguments
- starts each kernel and polls `ap_done`
- reads the boundary buffers back into `*.hex32`

Decode a boundary dump:

```bat
py -3 msr_vcu118_host.py decode-boundary --kind core --input path\to\core_boundary_out.hex32
py -3 msr_vcu118_host.py decode-boundary --kind bop --input path\to\bop_boundary_out.hex32
```

## First-pass architecture

The first hardware image is intentionally conservative:

- VCU118 board clock `default_250mhz_clk1` is converted to a 50 MHz fabric clock
- The host reaches the design through `jtag_axi`
- Both HLS kernels are instantiated as independent AXI-controlled accelerators
- State, parameter, and boundary buffers live in on-chip AXI BRAM, not DDR4

This is the debuggable host-intermediated board architecture used for deterministic split-kernel bring-up on the actual board.

## Host control layer

The host-side AXI tooling:

- pack the MSR state and parameter structs into the mapped BRAM regions
- write scalar control arguments through the HLS AXI-Lite register banks
- start each kernel, poll completion, and read back boundary outputs

The current host control layer is:

- `msr_vcu118_host.py`
- `vivado_jtag_axi_host.tcl`
- `windows_vivado_run_jtag_axi_host.bat`

Current hardware bring-up finding from 2026-06-16:

- `hw_axi_1` enumerates correctly after programming the current `.bit`
- But live AXI transactions to both the AXI-Lite control window and the BRAM windows time out on the presently programmed image
- The first wrapper revision exposed a top-level `reset` pin without a guaranteed board-side drive, so the board-level build script has been updated to tie `proc_sys_reset/ext_reset_in` inactive by default for the next bitstream spin
