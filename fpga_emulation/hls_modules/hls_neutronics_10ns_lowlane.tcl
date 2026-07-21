set top_name msr_neutronics_bench
set project_name neutronics_10ns_lowlane
set clock_period 10
set cflags {-std=c++11 -DMSR_NEUTRONICS_LANE_FACTOR=2}
source [file join [file normalize [file dirname [info script]]] hls_common.tcl]
