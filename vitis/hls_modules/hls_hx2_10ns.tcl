set top_name msr_hx2_bench
set project_name hx2_10ns
set clock_period 10
set cflags {-std=c++17}
source [file join [file normalize [file dirname [info script]]] hls_common.tcl]
