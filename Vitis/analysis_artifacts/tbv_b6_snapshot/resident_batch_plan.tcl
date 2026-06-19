array set MSR_VCU118_HOST_PLAN {
    chunk_words 64
    write_chunk_words 64
    read_chunk_words 1
    poll_interval_ms 20
    default_timeout_ms 120000
    hw_server_url localhost:3121
    device_pattern xcvu9p*
    after_program_delay_ms 2000
    program_bitfile {C:/Users/yuyao/w/b6/outputs/tbv.bit}
    program_ltxfile {C:/Users/yuyao/w/b6/outputs/tbv.ltx}
}

set MSR_VCU118_HOST_STEPS {
    {write_region tb_states 0x40000000 {C:/Users/yuyao/w/tbv_b6_snapshot/tb_states.hex32}}
    {write_region tb_delays 0x40010000 {C:/Users/yuyao/w/tbv_b6_snapshot/tb_delays.hex32}}
    {write_region tb_params 0x40020000 {C:/Users/yuyao/w/tbv_b6_snapshot/tb_params.hex32}}
    {write_region tb_rod_positions 0x40040000 {C:/Users/yuyao/w/tbv_b6_snapshot/tb_rod_positions.hex32}}
    {write_region tb_external_reactivities 0x40050000 {C:/Users/yuyao/w/tbv_b6_snapshot/tb_external_reactivities.hex32}}
    {write_region tb_final_diagnostics 0x40060000 {C:/Users/yuyao/w/tbv_b6_snapshot/tb_final_diagnostics.hex32}}
    {run_kernel transient_batch 0x44A00000 {{0x10 {40000000 00000000}} {0x1C {40010000 00000000}} {0x28 {40020000 00000000}} {0x34 {40040000 00000000}} {0x40 {40050000 00000000}} {0x4C {40060000 00000000}}} 120000}
    {read_region tb_final_diagnostics 0x40060000 24 {C:/Users/yuyao/w/tbv_b6_snapshot/tb_final_diagnostics_out.hex32}}
}
