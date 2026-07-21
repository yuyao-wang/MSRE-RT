set top_name core_step_kernel_n200_s1
set project_name core_step_n200_s1_10ns_lowlane
set clock_period 10
set cflags {-std=c++11 -DMSR_CROSS_SECTION_LANE_FACTOR=4 -DMSR_NEUTRONICS_LANE_FACTOR=8 -DMSR_THERMAL_LANE_FACTOR=8 -DMSR_FIXED_CORE_N=200 -DMSR_FIXED_HARDWARE_SUBSTEPS=1 -DMSR_MAX_STATE_N=200}
source [file join [file normalize [file dirname [info script]]] hls_export_common.tcl]
