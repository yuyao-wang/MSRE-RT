proc msr_require_argc {argc_expected_min argc_expected_max} {
    if {$::argc < $argc_expected_min || $::argc > $argc_expected_max} {
        error "Usage: vivado -mode batch -source vivado_jtag_axi_host.tcl -tclargs <plan.tcl>"
    }
}

proc msr_load_plan {} {
    msr_require_argc 1 1
    set plan_file [file normalize [lindex $::argv 0]]
    if {![file exists $plan_file]} {
        error "Plan file does not exist: $plan_file"
    }
    unset -nocomplain ::MSR_VCU118_HOST_PLAN
    set ::MSR_VCU118_HOST_STEPS {}
    uplevel #0 [list source $plan_file]
    if {![info exists ::MSR_VCU118_HOST_PLAN(chunk_words)]} {
        set ::MSR_VCU118_HOST_PLAN(chunk_words) 64
    }
    if {![info exists ::MSR_VCU118_HOST_PLAN(write_chunk_words)]} {
        set ::MSR_VCU118_HOST_PLAN(write_chunk_words) $::MSR_VCU118_HOST_PLAN(chunk_words)
    }
    if {![info exists ::MSR_VCU118_HOST_PLAN(read_chunk_words)]} {
        set ::MSR_VCU118_HOST_PLAN(read_chunk_words) 1
    }
    if {![info exists ::MSR_VCU118_HOST_PLAN(poll_interval_ms)]} {
        set ::MSR_VCU118_HOST_PLAN(poll_interval_ms) 10
    }
    if {![info exists ::MSR_VCU118_HOST_PLAN(default_timeout_ms)]} {
        set ::MSR_VCU118_HOST_PLAN(default_timeout_ms) 10000
    }
    if {![info exists ::MSR_VCU118_HOST_PLAN(hw_server_url)]} {
        set ::MSR_VCU118_HOST_PLAN(hw_server_url) localhost:3121
    }
    if {![info exists ::MSR_VCU118_HOST_PLAN(device_pattern)]} {
        set ::MSR_VCU118_HOST_PLAN(device_pattern) xcvu9p*
    }
    if {![info exists ::MSR_VCU118_HOST_PLAN(after_program_delay_ms)]} {
        set ::MSR_VCU118_HOST_PLAN(after_program_delay_ms) 2000
    }
    if {[info exists ::env(MSR_HOST_POLL_INTERVAL_MS)] && $::env(MSR_HOST_POLL_INTERVAL_MS) ne ""} {
        set ::MSR_VCU118_HOST_PLAN(poll_interval_ms) $::env(MSR_HOST_POLL_INTERVAL_MS)
    }
}

proc msr_now_us {} {
    return [clock microseconds]
}

proc msr_format_ms {delta_us} {
    return [format %.3f [expr {$delta_us / 1000.0}]]
}

proc msr_hw_open {} {
    set hw_open_start_us [msr_now_us]
    open_hw_manager
    connect_hw_server -url $::MSR_VCU118_HOST_PLAN(hw_server_url)

    set hw_targets [get_hw_targets *]
    if {[llength $hw_targets] == 0} {
        error "No hardware targets were found on $::MSR_VCU118_HOST_PLAN(hw_server_url)"
    }

    current_hw_target [lindex $hw_targets 0]
    open_hw_target

    set hw_devices [get_hw_devices $::MSR_VCU118_HOST_PLAN(device_pattern)]
    if {[llength $hw_devices] == 0} {
        set hw_devices [get_hw_devices]
    }
    if {[llength $hw_devices] == 0} {
        error "No hardware devices were found on the selected target"
    }

    set ::msr_hw_device [lindex $hw_devices 0]
    refresh_hw_device $::msr_hw_device

    if {[info exists ::MSR_VCU118_HOST_PLAN(program_bitfile)] && $::MSR_VCU118_HOST_PLAN(program_bitfile) ne ""} {
        set bitfile [file normalize $::MSR_VCU118_HOST_PLAN(program_bitfile)]
        if {![file exists $bitfile]} {
            error "Bitstream file does not exist: $bitfile"
        }
        puts "PROGRAM_BITFILE=$bitfile"
        set_property PROGRAM.FILE $bitfile $::msr_hw_device
        if {[info exists ::MSR_VCU118_HOST_PLAN(program_ltxfile)] && $::MSR_VCU118_HOST_PLAN(program_ltxfile) ne ""} {
            set ltxfile [file normalize $::MSR_VCU118_HOST_PLAN(program_ltxfile)]
            if {![file exists $ltxfile]} {
                error "Probe file does not exist: $ltxfile"
            }
            set_property PROBES.FILE $ltxfile $::msr_hw_device
            set_property FULL_PROBES.FILE $ltxfile $::msr_hw_device
            puts "PROGRAM_LTXFILE=$ltxfile"
        }
        set program_start_us [msr_now_us]
        program_hw_devices $::msr_hw_device
        set program_end_us [msr_now_us]
        puts "PROGRAM_TIMING DURATION_MS=[msr_format_ms [expr {$program_end_us - $program_start_us}]]"
        refresh_hw_device $::msr_hw_device
        if {$::MSR_VCU118_HOST_PLAN(after_program_delay_ms) > 0} {
            after $::MSR_VCU118_HOST_PLAN(after_program_delay_ms)
            refresh_hw_device $::msr_hw_device
        }
    }

    set hw_axis [get_hw_axis *]
    if {[llength $hw_axis] == 0} {
        error "No hw_axi objects were found. Check that the programmed design contains jtag_axi."
    }
    set ::msr_hw_axi [lindex $hw_axis 0]

    puts "HW_TARGET=[current_hw_target]"
    puts "HW_DEVICE=$::msr_hw_device"
    puts "HW_AXI=$::msr_hw_axi"
    set hw_open_end_us [msr_now_us]
    puts "HW_OPEN_TIMING DURATION_MS=[msr_format_ms [expr {$hw_open_end_us - $hw_open_start_us}]]"
}

proc msr_hw_close {} {
    if {[info exists ::msr_hw_device]} {
        catch {close_hw_target}
    }
    catch {disconnect_hw_server}
    catch {close_hw_manager}
}

proc msr_hex32_normalize {word} {
    set trimmed [string trim $word]
    if {$trimmed eq ""} {
        return ""
    }
    if {[string match "0x*" $trimmed] || [string match "0X*" $trimmed]} {
        set trimmed [string range $trimmed 2 end]
    }
    scan $trimmed %x value
    return [format %08X $value]
}

proc msr_hex32_file_read {path} {
    set normalized [file normalize $path]
    if {![file exists $normalized]} {
        error "Hex32 file does not exist: $normalized"
    }
    set handle [open $normalized r]
    set words {}
    while {[gets $handle line] >= 0} {
        set word [msr_hex32_normalize $line]
        if {$word ne ""} {
            lappend words $word
        }
    }
    close $handle
    return $words
}

proc msr_hex32_file_write {path words} {
    set normalized [file normalize $path]
    file mkdir [file dirname $normalized]
    set handle [open $normalized w]
    foreach word $words {
        puts $handle [msr_hex32_normalize $word]
    }
    close $handle
}

proc msr_axi_run_write {address words} {
    if {[llength $words] == 0} {
        return
    }
    set txn_name [format "msr_wr_%08X_%d" $address [clock clicks]]
    set txn [create_hw_axi_txn $txn_name $::msr_hw_axi -type write -address [format 0x%08X $address] -len [llength $words] -data $words]
    run_hw_axi $txn
    delete_hw_axi_txn $txn
}

proc msr_axi_run_read {address word_count} {
    set txn_name [format "msr_rd_%08X_%d" $address [clock clicks]]
    set txn [create_hw_axi_txn $txn_name $::msr_hw_axi -type read -address [format 0x%08X $address] -len $word_count]
    run_hw_axi $txn
    set raw_data [get_property DATA $txn]
    delete_hw_axi_txn $txn
    set words {}
    foreach item $raw_data {
        set word [msr_hex32_normalize $item]
        if {$word ne ""} {
            lappend words $word
        }
    }
    return $words
}

proc msr_axi_write_words {base_address words} {
    set chunk_words $::MSR_VCU118_HOST_PLAN(write_chunk_words)
    set total_words [llength $words]
    puts "WRITE_BASE=[format 0x%08X $base_address] WRITE_WORDS=$total_words"
    set write_start_us [msr_now_us]
    for {set idx 0} {$idx < $total_words} {incr idx $chunk_words} {
        set chunk [lrange $words $idx [expr {$idx + $chunk_words - 1}]]
        msr_axi_run_write [expr {$base_address + $idx * 4}] $chunk
    }
    set write_end_us [msr_now_us]
    puts "WRITE_TIMING BASE=[format 0x%08X $base_address] WORDS=$total_words DURATION_MS=[msr_format_ms [expr {$write_end_us - $write_start_us}]]"
}

proc msr_axi_read_words {base_address word_count} {
    set chunk_words $::MSR_VCU118_HOST_PLAN(read_chunk_words)
    set all_words {}
    puts "READ_BASE=[format 0x%08X $base_address] READ_WORDS=$word_count"
    set read_start_us [msr_now_us]
    for {set idx 0} {$idx < $word_count} {incr idx $chunk_words} {
        set this_count [expr {$word_count - $idx}]
        if {$this_count > $chunk_words} {
            set this_count $chunk_words
        }
        set chunk [msr_axi_run_read [expr {$base_address + $idx * 4}] $this_count]
        set all_words [concat $all_words $chunk]
    }
    set read_end_us [msr_now_us]
    puts "READ_TIMING BASE=[format 0x%08X $base_address] WORDS=$word_count DURATION_MS=[msr_format_ms [expr {$read_end_us - $read_start_us}]]"
    return $all_words
}

proc msr_reg_write32 {control_base offset value32} {
    msr_axi_run_write [expr {$control_base + $offset}] [list [msr_hex32_normalize $value32]]
}

proc msr_reg_read32 {control_base offset} {
    set words [msr_axi_run_read [expr {$control_base + $offset}] 1]
    if {[llength $words] != 1} {
        error "Expected a single 32-bit control word at [format 0x%08X [expr {$control_base + $offset}]]"
    }
    scan [lindex $words 0] %x value
    return $value
}

proc msr_reg_write_words {control_base entries} {
    foreach entry $entries {
        lassign $entry offset words
        msr_axi_write_words [expr {$control_base + $offset}] $words
    }
}

proc msr_poll_done {label control_base timeout_ms} {
    set wait_start_us [msr_now_us]
    set deadline [expr {[clock milliseconds] + $timeout_ms}]
    set polls 0
    while {1} {
        incr polls
        set ap_ctrl [msr_reg_read32 $control_base 0x00]
        if {($ap_ctrl & 0x2) != 0} {
            set wait_end_us [msr_now_us]
            puts "KERNEL_DONE=$label AP_CTRL=[format 0x%08X $ap_ctrl] POLLS=$polls WAIT_MS=[msr_format_ms [expr {$wait_end_us - $wait_start_us}]]"
            return [list $ap_ctrl $polls $wait_start_us $wait_end_us]
        }
        if {[clock milliseconds] > $deadline} {
            error "Timed out waiting for $label to complete. Last AP_CTRL=[format 0x%08X $ap_ctrl]"
        }
        after $::MSR_VCU118_HOST_PLAN(poll_interval_ms)
    }
}

proc msr_execute_step {step} {
    set kind [lindex $step 0]
    switch -- $kind {
        write_region {
            lassign $step _ label base_address hex32_file
            puts "STEP=write_region LABEL=$label FILE=[file normalize $hex32_file]"
            msr_axi_write_words $base_address [msr_hex32_file_read $hex32_file]
        }
        read_region {
            lassign $step _ label base_address word_count output_file
            puts "STEP=read_region LABEL=$label FILE=[file normalize $output_file]"
            set words [msr_axi_read_words $base_address $word_count]
            msr_hex32_file_write $output_file $words
        }
        run_kernel {
            lassign $step _ label control_base register_entries timeout_ms
            if {$timeout_ms eq ""} {
                set timeout_ms $::MSR_VCU118_HOST_PLAN(default_timeout_ms)
            }
            puts "STEP=run_kernel LABEL=$label CONTROL_BASE=[format 0x%08X $control_base] TIMEOUT_MS=$timeout_ms"
            set kernel_total_start_us [msr_now_us]
            set register_write_start_us [msr_now_us]
            msr_reg_write_words $control_base $register_entries
            set register_write_end_us [msr_now_us]
            set ap_start_write_start_us [msr_now_us]
            msr_reg_write32 $control_base 0x00 0x00000001
            set ap_start_write_end_us [msr_now_us]
            lassign [msr_poll_done $label $control_base $timeout_ms] ap_ctrl polls wait_start_us wait_end_us
            set kernel_total_end_us [msr_now_us]
            puts "KERNEL_TIMING LABEL=$label REG_WRITE_MS=[msr_format_ms [expr {$register_write_end_us - $register_write_start_us}]] AP_START_WRITE_MS=[msr_format_ms [expr {$ap_start_write_end_us - $ap_start_write_start_us}]] EXEC_WAIT_MS=[msr_format_ms [expr {$wait_end_us - $wait_start_us}]] TOTAL_MS=[msr_format_ms [expr {$kernel_total_end_us - $kernel_total_start_us}]] POLLS=$polls FINAL_AP_CTRL=[format 0x%08X $ap_ctrl]"
        }
        default {
            error "Unknown host-plan step type: $kind"
        }
    }
}

proc msr_execute_plan {} {
    set plan_start_us [msr_now_us]
    msr_load_plan
    msr_hw_open
    set rc 0
    set message ""
    if {[catch {
        foreach step $::MSR_VCU118_HOST_STEPS {
            msr_execute_step $step
        }
    } err]} {
        set rc 1
        set message $err
    }
    msr_hw_close
    if {$rc != 0} {
        error $message
    }
    set plan_end_us [msr_now_us]
    puts "PLAN_TIMING DURATION_MS=[msr_format_ms [expr {$plan_end_us - $plan_start_us}]]"
}

msr_execute_plan
exit
