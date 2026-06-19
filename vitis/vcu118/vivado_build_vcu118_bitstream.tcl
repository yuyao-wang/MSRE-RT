source [file join [file normalize [file dirname [info script]]] msr_vcu118_address_map.tcl]

proc require_dir {path description} {
    if {![file isdirectory $path]} {
        error "$description does not exist: $path"
    }
}

proc require_file {path description} {
    if {![file exists $path]} {
        error "$description does not exist: $path"
    }
}

proc get_first_ipdef {pattern description} {
    set defs [get_ipdefs -all $pattern]
    if {[llength $defs] == 0} {
        error "Unable to locate IP definition for $description with pattern $pattern"
    }
    return [lindex $defs 0]
}

proc maybe_connect_net {source_pin sink_path} {
    set sink_pin [get_bd_pins -quiet $sink_path]
    if {[llength $sink_pin] > 0} {
        connect_bd_net $source_pin $sink_pin
    }
}

proc create_axi_bram_pair {name depth_words clock_pin resetn_pin data_width} {
    set ctrl_name ${name}_ctrl
    set mem_name ${name}_mem

    create_bd_cell -type ip -vlnv xilinx.com:ip:axi_bram_ctrl $ctrl_name
    create_bd_cell -type ip -vlnv xilinx.com:ip:blk_mem_gen $mem_name

    set_property -dict [list \
        CONFIG.DATA_WIDTH $data_width \
        CONFIG.SINGLE_PORT_BRAM {1} \
        CONFIG.PROTOCOL {AXI4} \
    ] [get_bd_cells $ctrl_name]

    set_property -dict [list \
        CONFIG.Memory_Type {Single_Port_RAM} \
        CONFIG.Use_Byte_Write_Enable {true} \
        CONFIG.Byte_Size {8} \
        CONFIG.Write_Width_A $data_width \
        CONFIG.Read_Width_A $data_width \
        CONFIG.Write_Depth_A $depth_words \
        CONFIG.Register_PortA_Output_of_Memory_Primitives {false} \
    ] [get_bd_cells $mem_name]

    connect_bd_intf_net [get_bd_intf_pins ${ctrl_name}/BRAM_PORTA] [get_bd_intf_pins ${mem_name}/BRAM_PORTA]
    connect_bd_net $clock_pin [get_bd_pins ${ctrl_name}/s_axi_aclk]
    connect_bd_net $resetn_pin [get_bd_pins ${ctrl_name}/s_axi_aresetn]

    return $ctrl_name
}

proc assign_slave {addr_space_path segment_path offset range} {
    set addr_space [get_bd_addr_spaces -quiet $addr_space_path]
    if {[llength $addr_space] == 0} {
        error "Unable to locate address space: $addr_space_path"
    }

    set seg [get_bd_addr_segs -quiet $segment_path]
    if {[llength $seg] == 0} {
        error "Unable to locate address segment: $segment_path"
    }
    assign_bd_address -target_address_space $addr_space -offset $offset -range $range $seg
}

set script_dir [file normalize [file dirname [info script]]]
set vitis_dir [file normalize [file join $script_dir ..]]
set export_root [file normalize [file join $vitis_dir hls_export_work]]
set build_root_default [file normalize [file join $vitis_dir build_vcu118]]
if {[info exists ::env(MSR_VCU118_BUILD_ROOT)] && $::env(MSR_VCU118_BUILD_ROOT) ne ""} {
    set build_root [file normalize $::env(MSR_VCU118_BUILD_ROOT)]
} else {
    set build_root $build_root_default
}
set project_dir [file normalize [file join $build_root msr_split_vcu118]]
set output_dir [file normalize [file join $build_root outputs]]
set constraints_dir [file normalize [file join $build_root constraints]]
set bd_name msr_split_vcu118_bd
set project_name msr_split_vcu118

set core_ip_repo [file join $export_root core_step_n200_s1_10ns_lowlane solution1 impl ip]
set bop_ip_repo [file join $export_root bop_step_n200_s1_10ns_lowlane solution1 impl ip]

require_dir $core_ip_repo "Exported core-step IP repository"
require_dir $bop_ip_repo "Exported bop-step IP repository"

file mkdir $build_root
file mkdir $output_dir
file mkdir $constraints_dir

create_project $project_name $project_dir -part xcvu9p-flga2104-2L-e -force
set_property board_part xilinx.com:vcu118:part0:2.4 [current_project]
set_property ip_repo_paths [list $core_ip_repo $bop_ip_repo] [current_project]
update_ip_catalog -rebuild

set core_vlnv [get_first_ipdef *:core_step_kernel_n200_s1:* core_step_kernel_n200_s1]
set bop_vlnv [get_first_ipdef *:bop_step_kernel_n200_s1:* bop_step_kernel_n200_s1]
set core_cell core_0
set bop_cell bop_0

create_bd_design $bd_name

create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz clk_wiz_0
set_property -dict [list \
    CONFIG.PRIM_SOURCE {Differential_clock_capable_pin} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {50.000} \
    CONFIG.USE_LOCKED {true} \
] [get_bd_cells clk_wiz_0]
apply_board_connection -board_interface "default_250mhz_clk1" -ip_intf "/clk_wiz_0/CLK_IN1_D" -diagram $bd_name

create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant xlconstant_0
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {0}] [get_bd_cells xlconstant_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant xlconstant_1
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] [get_bd_cells xlconstant_1]
connect_bd_net [get_bd_pins xlconstant_0/dout] [get_bd_pins clk_wiz_0/reset]

create_bd_cell -type ip -vlnv xilinx.com:ip:jtag_axi jtag_axi_0
create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect smartconnect_0
set_property -dict [list CONFIG.NUM_SI {7} CONFIG.NUM_MI {8}] [get_bd_cells smartconnect_0]

create_bd_cell -type ip -vlnv $core_vlnv $core_cell
create_bd_cell -type ip -vlnv $bop_vlnv $bop_cell

set clk_pin [get_bd_pins clk_wiz_0/clk_out1]
set peripheral_resetn_pin [get_bd_pins xlconstant_1/dout]
set interconnect_resetn_pin [get_bd_pins xlconstant_1/dout]

connect_bd_net $clk_pin [get_bd_pins jtag_axi_0/aclk]
connect_bd_net $peripheral_resetn_pin [get_bd_pins jtag_axi_0/aresetn]
connect_bd_net $clk_pin [get_bd_pins smartconnect_0/aclk]
connect_bd_net $interconnect_resetn_pin [get_bd_pins smartconnect_0/aresetn]

foreach ctrl_name [list $core_cell $bop_cell] {
    foreach pin_name [list ap_clk ap_rst_n s_axi_control_aclk s_axi_control_aresetn m_axi_gmem0_aclk m_axi_gmem0_aresetn m_axi_gmem1_aclk m_axi_gmem1_aresetn m_axi_gmem2_aclk m_axi_gmem2_aresetn] {
        if {[string match "*aclk" $pin_name]} {
            maybe_connect_net $clk_pin ${ctrl_name}/$pin_name
        } elseif {[string match "*rst_n" $pin_name] || [string match "*aresetn" $pin_name]} {
            maybe_connect_net $peripheral_resetn_pin ${ctrl_name}/$pin_name
        } else {
            maybe_connect_net $clk_pin ${ctrl_name}/$pin_name
        }
    }
}

connect_bd_intf_net [get_bd_intf_pins jtag_axi_0/M_AXI] [get_bd_intf_pins smartconnect_0/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins ${core_cell}/m_axi_gmem0] [get_bd_intf_pins smartconnect_0/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins ${core_cell}/m_axi_gmem1] [get_bd_intf_pins smartconnect_0/S02_AXI]
connect_bd_intf_net [get_bd_intf_pins ${core_cell}/m_axi_gmem2] [get_bd_intf_pins smartconnect_0/S03_AXI]
connect_bd_intf_net [get_bd_intf_pins ${bop_cell}/m_axi_gmem0] [get_bd_intf_pins smartconnect_0/S04_AXI]
connect_bd_intf_net [get_bd_intf_pins ${bop_cell}/m_axi_gmem1] [get_bd_intf_pins smartconnect_0/S05_AXI]
connect_bd_intf_net [get_bd_intf_pins ${bop_cell}/m_axi_gmem2] [get_bd_intf_pins smartconnect_0/S06_AXI]

set core_state_ctrl [create_axi_bram_pair core_state $MSR_VCU118_WORD_DEPTH_MAP(core_state) $clk_pin $peripheral_resetn_pin 64]
set core_params_ctrl [create_axi_bram_pair core_params $MSR_VCU118_WORD_DEPTH_MAP(core_params) $clk_pin $peripheral_resetn_pin 64]
set core_boundary_ctrl [create_axi_bram_pair core_boundary $MSR_VCU118_WORD_DEPTH_MAP(core_boundary) $clk_pin $peripheral_resetn_pin 512]
set bop_state_ctrl [create_axi_bram_pair bop_state $MSR_VCU118_WORD_DEPTH_MAP(bop_state) $clk_pin $peripheral_resetn_pin 64]
set bop_params_ctrl [create_axi_bram_pair bop_params $MSR_VCU118_WORD_DEPTH_MAP(bop_params) $clk_pin $peripheral_resetn_pin 64]
set bop_boundary_ctrl [create_axi_bram_pair bop_boundary $MSR_VCU118_WORD_DEPTH_MAP(bop_boundary) $clk_pin $peripheral_resetn_pin 512]

connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M00_AXI] [get_bd_intf_pins ${core_cell}/s_axi_control]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M01_AXI] [get_bd_intf_pins ${bop_cell}/s_axi_control]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M02_AXI] [get_bd_intf_pins ${core_state_ctrl}/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M03_AXI] [get_bd_intf_pins ${core_params_ctrl}/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M04_AXI] [get_bd_intf_pins ${core_boundary_ctrl}/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M05_AXI] [get_bd_intf_pins ${bop_state_ctrl}/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M06_AXI] [get_bd_intf_pins ${bop_params_ctrl}/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M07_AXI] [get_bd_intf_pins ${bop_boundary_ctrl}/S_AXI]

assign_bd_address

set all_master_spaces [list \
    /jtag_axi_0/Data \
    /${core_cell}/Data_m_axi_gmem0 \
    /${core_cell}/Data_m_axi_gmem1 \
    /${core_cell}/Data_m_axi_gmem2 \
    /${bop_cell}/Data_m_axi_gmem0 \
    /${bop_cell}/Data_m_axi_gmem1 \
    /${bop_cell}/Data_m_axi_gmem2 \
]

set memory_segments [list \
    [list /${core_state_ctrl}/S_AXI/Mem0 core_state] \
    [list /${core_params_ctrl}/S_AXI/Mem0 core_params] \
    [list /${core_boundary_ctrl}/S_AXI/Mem0 core_boundary] \
    [list /${bop_state_ctrl}/S_AXI/Mem0 bop_state] \
    [list /${bop_params_ctrl}/S_AXI/Mem0 bop_params] \
    [list /${bop_boundary_ctrl}/S_AXI/Mem0 bop_boundary] \
]

foreach addr_space $all_master_spaces {
    foreach seg_desc $memory_segments {
        lassign $seg_desc seg_path map_key
        assign_slave $addr_space $seg_path $MSR_VCU118_ADDR_MAP($map_key) $MSR_VCU118_RANGE_MAP($map_key)
    }
}

assign_slave /jtag_axi_0/Data /${core_cell}/s_axi_control/Reg $MSR_VCU118_ADDR_MAP(core_control) $MSR_VCU118_RANGE_MAP(core_control)
assign_slave /jtag_axi_0/Data /${bop_cell}/s_axi_control/Reg $MSR_VCU118_ADDR_MAP(bop_control) $MSR_VCU118_RANGE_MAP(bop_control)

validate_bd_design
save_bd_design

make_wrapper -files [get_files [file join $project_dir ${project_name}.srcs sources_1 bd $bd_name ${bd_name}.bd]] -top
add_files -norecurse [file join $project_dir ${project_name}.gen sources_1 bd $bd_name hdl ${bd_name}_wrapper.v]
set_property top ${bd_name}_wrapper [current_fileset]

launch_runs synth_1 -jobs 8
wait_on_run synth_1
launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1

open_run impl_1

set bit_path [file join $output_dir ${project_name}.bit]
set ltx_path [file join $output_dir ${project_name}.ltx]
set xsa_path [file join $output_dir ${project_name}.xsa]

set impl_dir [get_property DIRECTORY [get_runs impl_1]]
set impl_bitstreams [glob -nocomplain [file join $impl_dir *.bit]]
if {[llength $impl_bitstreams] == 0} {
    error "No bitstream file was found in $impl_dir"
}
file copy -force [lindex $impl_bitstreams 0] $bit_path

set debug_probes [glob -nocomplain [file join $impl_dir *.ltx]]
if {[llength $debug_probes] > 0} {
    file copy -force [lindex $debug_probes 0] $ltx_path
}

write_hw_platform -fixed -include_bit -force -file $xsa_path

puts "BITSTREAM_OUTPUT=$bit_path"
puts "XSA_OUTPUT=$xsa_path"
if {[file exists $ltx_path]} {
    puts "LTX_OUTPUT=$ltx_path"
}
puts "CORE_CONTROL_BASE=$MSR_VCU118_ADDR_MAP(core_control)"
puts "BOP_CONTROL_BASE=$MSR_VCU118_ADDR_MAP(bop_control)"
puts "CORE_STATE_BASE=$MSR_VCU118_ADDR_MAP(core_state)"
puts "CORE_PARAMS_BASE=$MSR_VCU118_ADDR_MAP(core_params)"
puts "CORE_BOUNDARY_BASE=$MSR_VCU118_ADDR_MAP(core_boundary)"
puts "BOP_STATE_BASE=$MSR_VCU118_ADDR_MAP(bop_state)"
puts "BOP_PARAMS_BASE=$MSR_VCU118_ADDR_MAP(bop_params)"
puts "BOP_BOUNDARY_BASE=$MSR_VCU118_ADDR_MAP(bop_boundary)"

exit
