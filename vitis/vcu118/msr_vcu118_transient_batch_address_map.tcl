array set MSR_VCU118_TB_ADDR_MAP {
    tb_control                0x44A00000
    tb_states                 0x40000000
    tb_delays                 0x40010000
    tb_params                 0x40020000
    tb_rod_positions          0x40040000
    tb_external_reactivities  0x40050000
    tb_final_diagnostics      0x40060000
}

array set MSR_VCU118_TB_RANGE_MAP {
    tb_control                64K
    tb_states                 64K
    tb_delays                 8K
    tb_params                 128K
    tb_rod_positions          8K
    tb_external_reactivities  8K
    tb_final_diagnostics      4K
}

array set MSR_VCU118_TB_WORD_DEPTH_MAP {
    tb_states                 8192
    tb_delays                 1024
    tb_params                 16384
    tb_rod_positions          1024
    tb_external_reactivities  1024
    tb_final_diagnostics      64
}
