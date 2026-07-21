set top_name core_step_kernel
set project_name core_step_10ns
set clock_period 10
set cflags {-std=c++11}
source [file join [file normalize [file dirname [info script]]] hls_common.tcl]
