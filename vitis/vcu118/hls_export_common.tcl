if {![info exists top_name]} {
    error "top_name must be set before sourcing hls_export_common.tcl"
}

if {![info exists project_name]} {
    set project_name $top_name
}

if {![info exists clock_period]} {
    set clock_period 10
}

if {![info exists part_name]} {
    set part_name xcvu9p-flga2104-2L-e
}

if {![info exists cflags]} {
    set cflags {-std=c++11}
}

set script_dir [file normalize [file dirname [info script]]]
set vitis_dir [file normalize [file join $script_dir ..]]
if {![info exists source_file]} {
    set source_file [file join $vitis_dir msr_vitis_module_tops.cpp]
} elseif {[file pathtype $source_file] ne "absolute"} {
    set source_file [file join $vitis_dir $source_file]
}

set work_root [file normalize [file join $vitis_dir hls_export_work]]
file mkdir $work_root
cd $work_root

open_project -reset $project_name
set_top $top_name
add_files $source_file -cflags $cflags
open_solution -reset solution1
set_part $part_name
create_clock -period $clock_period
csynth_design
export_design -format ip_catalog -rtl verilog

puts "EXPORTED_PROJECT=[file join $work_root $project_name]"
puts "EXPORTED_IP_DIR=[file join $work_root $project_name solution1 impl ip]"
exit
