set top_name core_step_kernel_n80_s1
set project_name core_step_n80_s1_10ns_lowlane
set clock_period 10
set cflags {-std=c++11 -DMSR_CROSS_SECTION_LANE_FACTOR=2 -DMSR_NEUTRONICS_LANE_FACTOR=2 -DMSR_THERMAL_LANE_FACTOR=2 -DMSR_FIXED_CORE_N=80 -DMSR_FIXED_HARDWARE_SUBSTEPS=1}
source [file join [file normalize [file dirname [info script]]] hls_common.tcl]
