proc safe_get_property {prop obj} {
    if {[lsearch -exact [list_property $obj] $prop] >= 0} {
        return [get_property $prop $obj]
    }
    return "N/A"
}

open_hw_manager
connect_hw_server -url localhost:3121

set hw_targets [get_hw_targets *]
if {[llength $hw_targets] == 0} {
    error "No hardware targets were found on localhost:3121"
}

puts "HW_TARGET_COUNT=[llength $hw_targets]"
foreach t $hw_targets {
    puts "TARGET=$t"
}

current_hw_target [lindex $hw_targets 0]
open_hw_target

set hw_devices [get_hw_devices]
if {[llength $hw_devices] == 0} {
    error "No hardware devices were found on the selected target"
}

puts "HW_DEVICE_COUNT=[llength $hw_devices]"
foreach d $hw_devices {
    refresh_hw_device $d
    puts "DEVICE=$d"
    puts "PART=[get_property PART $d]"
    puts "PROGRAM_IS_SUPPORTED=[get_property PROGRAM.IS_SUPPORTED $d]"
    puts "DONE_PIN=[safe_get_property REGISTER.CONFIG_STATUS.BIT00_DONE_PIN $d]"
    puts "DONE_INTERNAL=[safe_get_property REGISTER.CONFIG_STATUS.BIT01_DONE_INTERNAL_SIGNAL_STATUS $d]"
}

close_hw_target
disconnect_hw_server
close_hw_manager
exit
