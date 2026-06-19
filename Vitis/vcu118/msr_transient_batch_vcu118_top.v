module msr_transient_batch_vcu118_top (
    input  wire default_250mhz_clk1_p,
    input  wire default_250mhz_clk1_n
);
    wire kernel_clk;

    msr_vcu118_clock_divider clock_divider_0 (
        .clk_in_p(default_250mhz_clk1_p),
        .clk_in_n(default_250mhz_clk1_n),
        .reset(1'b0),
        .clk_out1(kernel_clk)
    );

    tb_wrapper bd_wrapper_0 (
        .kernel_clk(kernel_clk)
    );
endmodule
