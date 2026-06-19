set script_dir [file normalize [file dirname [info script]]]
cd $script_dir

open_project -reset hls_work/msr_hls_prj
set_top msr_step_kernel
add_files msr_vitis_kernel.cpp -cflags {-std=c++11}
open_solution -reset solution1
set_part xcvu9p-flga2104-2L-e
create_clock -period 10
csynth_design
exit
