set top_name msr_transient_batch_kernel
set project_name transient_batch_n200_s1_10ns_lowlane
set clock_period 10
set source_file msr_vitis_kernel.cpp
set cflags {-std=c++11 -DMSR_CROSS_SECTION_LANE_FACTOR=4 -DMSR_NEUTRONICS_LANE_FACTOR=8 -DMSR_THERMAL_LANE_FACTOR=8 -DMSR_HEAT_EXCHANGER_LANE_FACTOR=4 -DMSR_FIXED_CORE_N=200 -DMSR_FIXED_BOP_NX=200 -DMSR_FIXED_HARDWARE_SUBSTEPS=1 -DMSR_MAX_STATE_N=200}
source [file join [file normalize [file dirname [info script]]] hls_common.tcl]
