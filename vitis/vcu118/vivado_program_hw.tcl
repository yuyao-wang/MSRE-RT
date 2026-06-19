proc safe_get_property {prop obj} {
    if {[lsearch -exact [list_property $obj] $prop] >= 0} {
        return [get_property $prop $obj]
    }
    return "N/A"
}

if {$argc < 1 || $argc > 2} {
    error "Usage: vivado -mode batch -source vivado_program_hw.tcl -tclargs <bitfile> ?<ltxfile>?"
}

set bitfile [file normalize [lindex $argv 0]]
if {![file exists $bitfile]} {
    error "Bitstream file does not exist: $bitfile"
}

set ltxfile ""
if {$argc == 2} {
    set ltxfile [file normalize [lindex $argv 1]]
    if {![file exists $ltxfile]} {
        error "Probe file does not exist: $ltxfile"
    }
}

open_hw_manager
connect_hw_server -url localhost:3121

set hw_targets [get_hw_targets *]
if {[llength $hw_targets] == 0} {
    error "No hardware targets were found on localhost:3121"
}

current_hw_target [lindex $hw_targets 0]
open_hw_target

set hw_devices [get_hw_devices xcvu9p*]
if {[llength $hw_devices] == 0} {
    set hw_devices [get_hw_devices]
}
if {[llength $hw_devices] == 0} {
    error "No hardware devices were found on the selected target"
}

set hw_device [lindex $hw_devices 0]
refresh_hw_device $hw_device

puts "PROGRAM_TARGET=[current_hw_target]"
puts "PROGRAM_DEVICE=$hw_device"
puts "PROGRAM_PART=[get_property PART $hw_device]"
puts "PROGRAM_BITFILE=$bitfile"
if {$ltxfile ne ""} {
    puts "PROGRAM_LTXFILE=$ltxfile"
}

set_property PROGRAM.FILE $bitfile $hw_device
if {$ltxfile ne ""} {
    set_property PROBES.FILE $ltxfile $hw_device
    set_property FULL_PROBES.FILE $ltxfile $hw_device
}

program_hw_devices $hw_device
refresh_hw_device $hw_device

puts "POST_PROGRAM_DONE_PIN=[safe_get_property REGISTER.CONFIG_STATUS.BIT00_DONE_PIN $hw_device]"
puts "POST_PROGRAM_DONE_INTERNAL=[safe_get_property REGISTER.CONFIG_STATUS.BIT01_DONE_INTERNAL_SIGNAL_STATUS $hw_device]"

close_hw_target
disconnect_hw_server
close_hw_manager
exit
