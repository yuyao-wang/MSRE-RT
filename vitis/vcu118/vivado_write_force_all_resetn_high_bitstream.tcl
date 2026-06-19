proc require_args {} {
    if {$::argc != 2} {
        error "Usage: vivado -mode batch -source vivado_write_force_all_resetn_high_bitstream.tcl -tclargs <checkpoint.dcp> <output.bit>"
    }
    set checkpoint [file normalize [lindex $::argv 0]]
    set output_bit [file normalize [lindex $::argv 1]]
    if {![file exists $checkpoint]} {
        error "Checkpoint does not exist: $checkpoint"
    }
    return [list $checkpoint $output_bit]
}

proc require_pin {path} {
    set pin [get_pins -quiet $path]
    if {[llength $pin] == 0} {
        error "Pin not found: $path"
    }
    return $pin
}

proc disconnect_target_pin {pin_path} {
    set pin [get_pins -quiet $pin_path]
    if {[llength $pin] == 0} {
        return
    }
    set nets [get_nets -quiet -of_objects $pin]
    if {[llength $nets] > 0} {
        disconnect_net -net [lindex $nets 0] -pinlist $pin
    }
}

proc connect_constant_pin {pin_path net_name} {
    set pin [get_pins -quiet $pin_path]
    if {[llength $pin] == 0} {
        puts "SKIP_PIN=$pin_path"
        return
    }
    disconnect_target_pin $pin_path
    connect_net -hierarchical -net $net_name -objects $pin
    puts "FORCED_[string toupper $net_name]=$pin_path"
}

lassign [require_args] checkpoint output_bit
open_checkpoint $checkpoint

create_cell -reference VCC eco_vcc
create_cell -reference GND eco_gnd
create_net eco_vcc_net
create_net eco_gnd_net
connect_net -net eco_vcc_net -objects [get_pins eco_vcc/P]
connect_net -net eco_gnd_net -objects [get_pins eco_gnd/G]

set gnd_targets [list \
    msr_split_vcu118_bd_i/clk_wiz_0/reset \
    msr_split_vcu118_bd_i/proc_sys_reset_0/ext_reset_in \
    msr_split_vcu118_bd_i/proc_sys_reset_0/aux_reset_in \
    msr_split_vcu118_bd_i/proc_sys_reset_0/mb_debug_sys_rst \
]

set vcc_targets [list \
    msr_split_vcu118_bd_i/proc_sys_reset_0/dcm_locked \
    msr_split_vcu118_bd_i/jtag_axi_0/aresetn \
    msr_split_vcu118_bd_i/smartconnect_0/aresetn \
    msr_split_vcu118_bd_i/core_0/ap_rst_n \
    msr_split_vcu118_bd_i/core_0/s_axi_control_aresetn \
    msr_split_vcu118_bd_i/core_0/m_axi_gmem0_aresetn \
    msr_split_vcu118_bd_i/core_0/m_axi_gmem1_aresetn \
    msr_split_vcu118_bd_i/core_0/m_axi_gmem2_aresetn \
    msr_split_vcu118_bd_i/bop_0/ap_rst_n \
    msr_split_vcu118_bd_i/bop_0/s_axi_control_aresetn \
    msr_split_vcu118_bd_i/bop_0/m_axi_gmem0_aresetn \
    msr_split_vcu118_bd_i/bop_0/m_axi_gmem1_aresetn \
    msr_split_vcu118_bd_i/bop_0/m_axi_gmem2_aresetn \
    msr_split_vcu118_bd_i/core_state_ctrl/s_axi_aresetn \
    msr_split_vcu118_bd_i/core_params_ctrl/s_axi_aresetn \
    msr_split_vcu118_bd_i/core_boundary_ctrl/s_axi_aresetn \
    msr_split_vcu118_bd_i/bop_state_ctrl/s_axi_aresetn \
    msr_split_vcu118_bd_i/bop_params_ctrl/s_axi_aresetn \
    msr_split_vcu118_bd_i/bop_boundary_ctrl/s_axi_aresetn \
]

foreach pin_path $gnd_targets {
    connect_constant_pin $pin_path eco_gnd_net
}

foreach pin_path $vcc_targets {
    connect_constant_pin $pin_path eco_vcc_net
}

route_design -nets [concat [get_nets eco_vcc_net] [get_nets eco_gnd_net]]

file mkdir [file dirname $output_bit]
write_bitstream -force $output_bit

puts "BITSTREAM_OUTPUT=$output_bit"

close_design
exit
