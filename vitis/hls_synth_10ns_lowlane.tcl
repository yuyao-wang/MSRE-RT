set script_dir [file normalize [file dirname [info script]]]
cd $script_dir

open_project -reset hls_work/msr_hls_prj
set_top msr_step_kernel
add_files msr_vitis_kernel.cpp -cflags {-std=c++17 -DMSR_CROSS_SECTION_LANE_FACTOR=2 -DMSR_NEUTRONICS_LANE_FACTOR=2 -DMSR_THERMAL_LANE_FACTOR=2 -DMSR_HEAT_EXCHANGER_LANE_FACTOR=2}
open_solution -reset solution1
set_part xcu200-fsgd2104-2-e
create_clock -period 10
csynth_design
exit
