proc require_checkpoint_arg {} {
    if {$::argc != 1} {
        error "Usage: vivado -mode batch -source vivado_query_reset_checkpoint.tcl -tclargs <checkpoint.dcp>"
    }
    set checkpoint [file normalize [lindex $::argv 0]]
    if {![file exists $checkpoint]} {
        error "Checkpoint does not exist: $checkpoint"
    }
    return $checkpoint
}

proc print_matches {label objects} {
    puts "=== $label ==="
    if {[llength $objects] == 0} {
        puts "NONE"
        return
    }
    foreach obj $objects {
        puts $obj
    }
}

proc print_net_for_pin {pin_path} {
    set pin [get_pins -quiet $pin_path]
    if {[llength $pin] == 0} {
        puts "PIN_NOT_FOUND $pin_path"
        return
    }
    set nets [get_nets -quiet -of_objects $pin]
    puts "PIN=$pin_path"
    if {[llength $nets] == 0} {
        puts "  NET=NONE"
    } else {
        foreach net $nets {
            puts "  NET=$net"
        }
    }
}

set checkpoint [require_checkpoint_arg]
open_checkpoint $checkpoint

puts "CHECKPOINT=$checkpoint"
puts "TOP=[current_design]"

print_matches "PORTS_MATCHING_RESET" [lsort [get_ports -quiet *reset*]]
print_matches "PINS_MATCHING_PROC_SYS_RESET" [lsort [get_pins -hier -quiet *proc_sys_reset*]]
print_matches "NETS_MATCHING_RESET" [lsort [get_nets -hier -quiet *reset*]]

foreach pin_path [list \
    msr_split_vcu118_bd_i/proc_sys_reset_0/ext_reset_in \
    msr_split_vcu118_bd_i/proc_sys_reset_0/aux_reset_in \
    msr_split_vcu118_bd_i/proc_sys_reset_0/mb_debug_sys_rst \
    msr_split_vcu118_bd_i/proc_sys_reset_0/peripheral_aresetn \
    msr_split_vcu118_bd_i/proc_sys_reset_0/interconnect_aresetn \
    msr_split_vcu118_bd_i/clk_wiz_0/locked \
] {
    print_net_for_pin $pin_path
}

foreach port [get_ports -quiet *reset*] {
    puts "PORT=$port DIRECTION=[get_property DIRECTION $port]"
    foreach prop [list PACKAGE_PIN IOSTANDARD PULLTYPE PULLDOWN PULLUP] {
        set value [get_property -quiet $prop $port]
        if {$value ne ""} {
            puts "  $prop=$value"
        }
    }
    set port_nets [get_nets -quiet -of_objects $port]
    if {[llength $port_nets] == 0} {
        puts "  NET=NONE"
    } else {
        foreach net $port_nets {
            puts "  NET=$net"
        }
    }
}

close_design
exit
