array set MSR_VCU118_ADDR_MAP {
    core_control   0x44A00000
    bop_control    0x44A10000
    core_state     0x40000000
    core_params    0x40020000
    core_boundary  0x40040000
    bop_state      0x40050000
    bop_params     0x40060000
    bop_boundary   0x40080000
}

array set MSR_VCU118_RANGE_MAP {
    core_control   64K
    bop_control    64K
    core_state     64K
    core_params    128K
    core_boundary  4K
    bop_state      32K
    bop_params     128K
    bop_boundary   4K
}

array set MSR_VCU118_WORD_DEPTH_MAP {
    core_state     8192
    core_params    16384
    core_boundary  64
    bop_state      4096
    bop_params     16384
    bop_boundary   64
}
