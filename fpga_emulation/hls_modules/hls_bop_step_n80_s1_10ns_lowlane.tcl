set top_name bop_step_kernel_n80_s1
set project_name bop_step_n80_s1_10ns_lowlane
set clock_period 10
set cflags {-std=c++11 -DMSR_HEAT_EXCHANGER_LANE_FACTOR=2 -DMSR_FIXED_BOP_NX=80 -DMSR_FIXED_HARDWARE_SUBSTEPS=1}
source [file join [file normalize [file dirname [info script]]] hls_common.tcl]
