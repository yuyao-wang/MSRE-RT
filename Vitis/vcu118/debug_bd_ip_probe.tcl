proc log_stage {message} {
    puts "PROBE: $message"
    flush stdout
}

set project_dir [file normalize "X:/bd_ip_probe"]
file mkdir $project_dir

create_project bd_ip_probe $project_dir -part xcvu9p-flga2104-2L-e -force
set_property board_part xilinx.com:vcu118:part0:2.4 [current_project]
log_stage project_created

create_bd_design probe_bd
log_stage bd_created

create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant xlconstant_0
log_stage xlconstant_created

create_bd_cell -type ip -vlnv xilinx.com:ip:jtag_axi jtag_axi_0
log_stage jtag_axi_created

create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect smartconnect_0
log_stage smartconnect_created

create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz clk_wiz_0
log_stage clk_wiz_created

exit
