set top_name msr_power_reduction_bench
set project_name power_reduction_10ns
set clock_period 10
set cflags {-std=c++17}
source [file join [file normalize [file dirname [info script]]] hls_common.tcl]
