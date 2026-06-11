if {![info exists top_name]} {
    error "top_name must be set before sourcing hls_common.tcl"
}

if {![info exists project_name]} {
    set project_name $top_name
}

if {![info exists clock_period]} {
    set clock_period 10
}

if {![info exists part_name]} {
    set part_name xcu200-fsgd2104-2-e
}

if {![info exists source_file]} {
    set source_file msr_vitis_module_tops.cpp
}

if {![info exists cflags]} {
    set cflags {-std=c++17}
}

set script_dir [file normalize [file dirname [info script]]]
set vitis_dir [file normalize [file join $script_dir ..]]
cd $vitis_dir

open_project -reset [file join hls_module_work $project_name]
set_top $top_name
add_files $source_file -cflags $cflags
open_solution -reset solution1
set_part $part_name
create_clock -period $clock_period
csynth_design
exit
