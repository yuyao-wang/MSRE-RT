module msr_vcu118_clock_divider (
    (* X_INTERFACE_INFO = "xilinx.com:interface:diff_clock_rtl:1.0 CLK_IN1 CLK_P" *)
    input  wire clk_in_p,
    (* X_INTERFACE_INFO = "xilinx.com:interface:diff_clock_rtl:1.0 CLK_IN1 CLK_N" *)
    input  wire clk_in_n,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 RESET RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_HIGH" *)
    input  wire reset,
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 CLK_OUT1 CLK" *)
    (* X_INTERFACE_PARAMETER = "FREQ_HZ 50000000, PHASE 0.0, CLK_DOMAIN msr_vcu118_clock_divider_clk_out1, ASSOCIATED_RESET reset" *)
    output wire clk_out1
);
    wire clk_in_ibufds;

    IBUFDS #(
        .DIFF_TERM("TRUE"),
        .IBUF_LOW_PWR("FALSE")
    ) ibufds_inst (
        .I(clk_in_p),
        .IB(clk_in_n),
        .O(clk_in_ibufds)
    );

    BUFGCE_DIV #(
        .BUFGCE_DIVIDE(5),
        .IS_CE_INVERTED(1'b0),
        .IS_CLR_INVERTED(1'b0),
        .IS_I_INVERTED(1'b0),
        .SIM_DEVICE("ULTRASCALE")
    ) bufdiv_inst (
        .I(clk_in_ibufds),
        .CE(1'b1),
        .CLR(reset),
        .O(clk_out1)
    );
endmodule
