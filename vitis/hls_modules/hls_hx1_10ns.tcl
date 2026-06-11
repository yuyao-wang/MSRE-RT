set top_name msr_hx1_bench
set project_name hx1_10ns
set clock_period 10
set cflags {-std=c++17}
source [file join [file normalize [file dirname [info script]]] hls_common.tcl]
