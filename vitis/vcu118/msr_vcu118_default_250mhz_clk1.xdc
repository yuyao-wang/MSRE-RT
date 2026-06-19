set_property PACKAGE_PIN E12 [get_ports default_250mhz_clk1_p]
set_property PACKAGE_PIN D12 [get_ports default_250mhz_clk1_n]
set_property IOSTANDARD DIFF_SSTL12 [get_ports {default_250mhz_clk1_p default_250mhz_clk1_n}]

create_clock -name default_250mhz_clk1 -period 4.000 [get_ports default_250mhz_clk1_p]
