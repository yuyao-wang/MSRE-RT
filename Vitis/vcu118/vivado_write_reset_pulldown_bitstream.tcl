proc require_args {} {
    if {$::argc != 2} {
        error "Usage: vivado -mode batch -source vivado_write_reset_pulldown_bitstream.tcl -tclargs <checkpoint.dcp> <output.bit>"
    }
    set checkpoint [file normalize [lindex $::argv 0]]
    set output_bit [file normalize [lindex $::argv 1]]
    if {![file exists $checkpoint]} {
        error "Checkpoint does not exist: $checkpoint"
    }
    return [list $checkpoint $output_bit]
}

lassign [require_args] checkpoint output_bit
open_checkpoint $checkpoint

set reset_port [get_ports -quiet reset]
if {[llength $reset_port] == 0} {
    error "No top-level reset port was found in $checkpoint"
}

puts "CHECKPOINT=$checkpoint"
puts "RESET_PORT=$reset_port"
puts "RESET_NETS=[get_nets -quiet -of_objects $reset_port]"
puts "RESET_PACKAGE_PIN=[get_property PACKAGE_PIN $reset_port]"

set_property PULLDOWN true $reset_port
set_property PULLUP false $reset_port

file mkdir [file dirname $output_bit]
write_bitstream -force $output_bit

puts "BITSTREAM_OUTPUT=$output_bit"
puts "PULLDOWN=[get_property PULLDOWN $reset_port]"
puts "PULLUP=[get_property PULLUP $reset_port]"

close_design
exit
