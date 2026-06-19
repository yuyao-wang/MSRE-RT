set top_name msr_thermal_bench
set project_name thermal_10ns
set clock_period 10
set cflags {-std=c++11}
source [file join [file normalize [file dirname [info script]]] hls_common.tcl]
