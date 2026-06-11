set top_name core_step_kernel
set project_name core_step_10ns_lowlane
set clock_period 10
set cflags {-std=c++11 -DMSR_CROSS_SECTION_LANE_FACTOR=2 -DMSR_NEUTRONICS_LANE_FACTOR=2 -DMSR_THERMAL_LANE_FACTOR=2}
source [file join [file normalize [file dirname [info script]]] hls_common.tcl]
