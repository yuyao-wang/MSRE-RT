source [file join [file normalize [file dirname [info script]]] msr_vcu118_transient_batch_address_map.tcl]

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

proc maybe_set_property {prop value sink_path} {
    set sink_pin [get_bd_pins -quiet $sink_path]
    if {[llength $sink_pin] > 0} {
        catch {set_property $prop $value $sink_pin}
    }
}

proc log_stage {message} {
    puts "STAGE: $message"
    flush stdout
}

proc env_or_default_int {name default_value} {
    if {[info exists ::env($name)] && $::env($name) ne ""} {
        return [expr {int($::env($name))}]
    }
    return $default_value
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
set build_root_default [file normalize [file join $vitis_dir b]]
set clock_divider_rtl [file join $script_dir msr_vcu118_clock_divider.v]
set clock_constraints_xdc [file join $script_dir msr_vcu118_default_250mhz_clk1.xdc]
set top_rtl [file join $script_dir msr_transient_batch_vcu118_top.v]
if {[info exists ::env(MSR_VCU118_BUILD_ROOT)] && $::env(MSR_VCU118_BUILD_ROOT) ne ""} {
    set build_root [file normalize $::env(MSR_VCU118_BUILD_ROOT)]
} else {
    set build_root $build_root_default
}
set bd_name tb
set project_name tbv
set project_dir [file normalize [file join $build_root $project_name]]
set output_dir [file normalize [file join $build_root outputs]]
set vivado_jobs [env_or_default_int MSR_VIVADO_JOBS 8]
set vivado_max_threads [env_or_default_int MSR_VIVADO_MAX_THREADS 0]

set batch_ip_repo [file join $export_root transient_batch_bench_600x1_10ns_sharedfp solution1 impl ip]
require_dir $batch_ip_repo "Exported transient-batch IP repository"
require_file $clock_divider_rtl "VCU118 clock-divider RTL"
require_file $clock_constraints_xdc "VCU118 clock constraints"
require_file $top_rtl "VCU118 transient-batch top RTL"

file mkdir $build_root
file mkdir $output_dir

create_project $project_name $project_dir -part xcvu9p-flga2104-2L-e -force
if {$vivado_max_threads > 0} {
    set_param general.maxThreads $vivado_max_threads
    log_stage max_threads_$vivado_max_threads
}
set_property board_part xilinx.com:vcu118:part0:2.4 [current_project]
set_property ip_repo_paths [list $batch_ip_repo] [current_project]
update_ip_catalog -rebuild
log_stage project_created

set batch_vlnv [get_first_ipdef *:msr_transient_batch_bench_kernel:* msr_transient_batch_bench_kernel]
set batch_cell batch_0

create_bd_design $bd_name
log_stage bd_created

create_bd_port -dir I -type clk -freq_hz 50000000 kernel_clk
log_stage kernel_clk_port_created

create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant xlconstant_0
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {0}] [get_bd_cells xlconstant_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant xlconstant_1
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] [get_bd_cells xlconstant_1]
log_stage clock_ports_connected

create_bd_cell -type ip -vlnv xilinx.com:ip:jtag_axi jtag_axi_0
create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect smartconnect_0
set_property -dict [list CONFIG.NUM_SI {7} CONFIG.NUM_MI {7}] [get_bd_cells smartconnect_0]

create_bd_cell -type ip -vlnv $batch_vlnv $batch_cell

set clk_pin [get_bd_ports kernel_clk]
set kernel_clk_domain [get_property CONFIG.CLK_DOMAIN [get_bd_ports kernel_clk]]
set peripheral_resetn_pin [get_bd_pins xlconstant_1/dout]
set interconnect_resetn_pin [get_bd_pins xlconstant_1/dout]

connect_bd_net $clk_pin [get_bd_pins jtag_axi_0/aclk]
set_property CONFIG.FREQ_HZ 50000000 [get_bd_pins jtag_axi_0/aclk]
set_property CONFIG.CLK_DOMAIN $kernel_clk_domain [get_bd_pins jtag_axi_0/aclk]
connect_bd_net $peripheral_resetn_pin [get_bd_pins jtag_axi_0/aresetn]
connect_bd_net $clk_pin [get_bd_pins smartconnect_0/aclk]
set_property CONFIG.FREQ_HZ 50000000 [get_bd_pins smartconnect_0/aclk]
set_property CONFIG.CLK_DOMAIN $kernel_clk_domain [get_bd_pins smartconnect_0/aclk]
connect_bd_net $interconnect_resetn_pin [get_bd_pins smartconnect_0/aresetn]

foreach pin_name [list \
    ap_clk ap_rst_n \
    s_axi_control_aclk s_axi_control_aresetn \
    m_axi_gmem0_aclk m_axi_gmem0_aresetn \
    m_axi_gmem1_aclk m_axi_gmem1_aresetn \
    m_axi_gmem2_aclk m_axi_gmem2_aresetn \
    m_axi_gmem3_aclk m_axi_gmem3_aresetn \
    m_axi_gmem4_aclk m_axi_gmem4_aresetn \
    m_axi_gmem5_aclk m_axi_gmem5_aresetn \
] {
    if {[string match "*aclk" $pin_name]} {
        maybe_connect_net $clk_pin ${batch_cell}/$pin_name
        maybe_set_property CONFIG.FREQ_HZ 50000000 ${batch_cell}/$pin_name
        maybe_set_property CONFIG.CLK_DOMAIN $kernel_clk_domain ${batch_cell}/$pin_name
    } elseif {[string match "*rst_n" $pin_name] || [string match "*aresetn" $pin_name]} {
        maybe_connect_net $peripheral_resetn_pin ${batch_cell}/$pin_name
    } else {
        maybe_connect_net $clk_pin ${batch_cell}/$pin_name
        maybe_set_property CONFIG.FREQ_HZ 50000000 ${batch_cell}/$pin_name
        maybe_set_property CONFIG.CLK_DOMAIN $kernel_clk_domain ${batch_cell}/$pin_name
    }
}

connect_bd_intf_net [get_bd_intf_pins jtag_axi_0/M_AXI] [get_bd_intf_pins smartconnect_0/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins ${batch_cell}/m_axi_gmem0] [get_bd_intf_pins smartconnect_0/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins ${batch_cell}/m_axi_gmem1] [get_bd_intf_pins smartconnect_0/S02_AXI]
connect_bd_intf_net [get_bd_intf_pins ${batch_cell}/m_axi_gmem2] [get_bd_intf_pins smartconnect_0/S03_AXI]
connect_bd_intf_net [get_bd_intf_pins ${batch_cell}/m_axi_gmem3] [get_bd_intf_pins smartconnect_0/S04_AXI]
connect_bd_intf_net [get_bd_intf_pins ${batch_cell}/m_axi_gmem4] [get_bd_intf_pins smartconnect_0/S05_AXI]
connect_bd_intf_net [get_bd_intf_pins ${batch_cell}/m_axi_gmem5] [get_bd_intf_pins smartconnect_0/S06_AXI]

set states_ctrl [create_axi_bram_pair s $MSR_VCU118_TB_WORD_DEPTH_MAP(tb_states) $clk_pin $peripheral_resetn_pin 64]
set delays_ctrl [create_axi_bram_pair d $MSR_VCU118_TB_WORD_DEPTH_MAP(tb_delays) $clk_pin $peripheral_resetn_pin 64]
set params_ctrl [create_axi_bram_pair p $MSR_VCU118_TB_WORD_DEPTH_MAP(tb_params) $clk_pin $peripheral_resetn_pin 64]
set rod_ctrl [create_axi_bram_pair r $MSR_VCU118_TB_WORD_DEPTH_MAP(tb_rod_positions) $clk_pin $peripheral_resetn_pin 64]
set rho_ctrl [create_axi_bram_pair x $MSR_VCU118_TB_WORD_DEPTH_MAP(tb_external_reactivities) $clk_pin $peripheral_resetn_pin 64]
set diag_ctrl [create_axi_bram_pair f $MSR_VCU118_TB_WORD_DEPTH_MAP(tb_final_diagnostics) $clk_pin $peripheral_resetn_pin 512]

connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M00_AXI] [get_bd_intf_pins ${batch_cell}/s_axi_control]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M01_AXI] [get_bd_intf_pins ${states_ctrl}/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M02_AXI] [get_bd_intf_pins ${delays_ctrl}/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M03_AXI] [get_bd_intf_pins ${params_ctrl}/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M04_AXI] [get_bd_intf_pins ${rod_ctrl}/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M05_AXI] [get_bd_intf_pins ${rho_ctrl}/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M06_AXI] [get_bd_intf_pins ${diag_ctrl}/S_AXI]

assign_bd_address

set all_master_spaces [list \
    /jtag_axi_0/Data \
    /${batch_cell}/Data_m_axi_gmem0 \
    /${batch_cell}/Data_m_axi_gmem1 \
    /${batch_cell}/Data_m_axi_gmem2 \
    /${batch_cell}/Data_m_axi_gmem3 \
    /${batch_cell}/Data_m_axi_gmem4 \
    /${batch_cell}/Data_m_axi_gmem5 \
]

set memory_segments [list \
    [list /${states_ctrl}/S_AXI/Mem0 tb_states] \
    [list /${delays_ctrl}/S_AXI/Mem0 tb_delays] \
    [list /${params_ctrl}/S_AXI/Mem0 tb_params] \
    [list /${rod_ctrl}/S_AXI/Mem0 tb_rod_positions] \
    [list /${rho_ctrl}/S_AXI/Mem0 tb_external_reactivities] \
    [list /${diag_ctrl}/S_AXI/Mem0 tb_final_diagnostics] \
]

foreach addr_space $all_master_spaces {
    foreach seg_desc $memory_segments {
        lassign $seg_desc seg_path map_key
        assign_slave $addr_space $seg_path $MSR_VCU118_TB_ADDR_MAP($map_key) $MSR_VCU118_TB_RANGE_MAP($map_key)
    }
}

assign_slave /jtag_axi_0/Data /${batch_cell}/s_axi_control/Reg $MSR_VCU118_TB_ADDR_MAP(tb_control) $MSR_VCU118_TB_RANGE_MAP(tb_control)
log_stage bd_populated

report_property [get_bd_ports kernel_clk]
report_property [get_bd_pins ${batch_cell}/ap_clk]

validate_bd_design
log_stage bd_validated
save_bd_design
log_stage bd_saved

log_stage make_wrapper_begin
make_wrapper -files [get_files [file join $project_dir ${project_name}.srcs sources_1 bd $bd_name ${bd_name}.bd]] -top
log_stage make_wrapper_done
add_files -norecurse [file join $project_dir ${project_name}.gen sources_1 bd $bd_name hdl ${bd_name}_wrapper.v]
add_files -norecurse $clock_divider_rtl
add_files -norecurse $top_rtl
add_files -fileset constrs_1 -norecurse $clock_constraints_xdc
update_compile_order -fileset sources_1
set_property top msr_transient_batch_vcu118_top [current_fileset]
log_stage top_set

log_stage launch_synth
launch_runs synth_1 -jobs $vivado_jobs
wait_on_run synth_1
log_stage synth_done
launch_runs impl_1 -to_step write_bitstream -jobs $vivado_jobs
wait_on_run impl_1
log_stage impl_done

open_run impl_1
log_stage impl_opened

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
puts "TB_CONTROL_BASE=$MSR_VCU118_TB_ADDR_MAP(tb_control)"
puts "TB_STATES_BASE=$MSR_VCU118_TB_ADDR_MAP(tb_states)"
puts "TB_DELAYS_BASE=$MSR_VCU118_TB_ADDR_MAP(tb_delays)"
puts "TB_PARAMS_BASE=$MSR_VCU118_TB_ADDR_MAP(tb_params)"
puts "TB_ROD_POSITIONS_BASE=$MSR_VCU118_TB_ADDR_MAP(tb_rod_positions)"
puts "TB_EXTERNAL_REACTIVITIES_BASE=$MSR_VCU118_TB_ADDR_MAP(tb_external_reactivities)"
puts "TB_FINAL_DIAGNOSTICS_BASE=$MSR_VCU118_TB_ADDR_MAP(tb_final_diagnostics)"
