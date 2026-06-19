proc require_args {} {
    if {$::argc != 2} {
        error "Usage: vivado -mode batch -source vivado_write_force_reset_release_bitstream.tcl -tclargs <checkpoint.dcp> <output.bit>"
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
    set pin [require_pin $pin_path]
    set nets [get_nets -quiet -of_objects $pin]
    if {[llength $nets] > 0} {
        disconnect_net -net [lindex $nets 0] -pinlist $pin
    }
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
]
set vcc_targets [list \
    msr_split_vcu118_bd_i/proc_sys_reset_0/dcm_locked \
]

foreach pin_path $gnd_targets {
    disconnect_target_pin $pin_path
    connect_net -hierarchical -net eco_gnd_net -objects [require_pin $pin_path]
    puts "FORCED_GND=$pin_path"
}

foreach pin_path $vcc_targets {
    disconnect_target_pin $pin_path
    connect_net -hierarchical -net eco_vcc_net -objects [require_pin $pin_path]
    puts "FORCED_VCC=$pin_path"
}

route_design -nets [concat [get_nets eco_vcc_net] [get_nets eco_gnd_net]]

file mkdir [file dirname $output_bit]
write_bitstream -force $output_bit

puts "BITSTREAM_OUTPUT=$output_bit"

close_design
exit
