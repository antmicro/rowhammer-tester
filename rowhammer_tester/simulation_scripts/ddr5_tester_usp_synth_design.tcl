read_verilog $env(VexRiscvPath)
read_verilog {../../build/ddr5_tester_usp/gateware/antmicro_ddr5_tester_usp.v}
read_xdc ../../build/ddr5_tester_usp/gateware/antmicro_ddr5_tester_usp.xdc
set_property PROCESSING_ORDER EARLY [get_files antmicro_ddr5_tester_usp.xdc]
synth_design -directive default -top antmicro_ddr5_tester_usp -part xcau25p-ffvb676-2-i
write_verilog -mode funcsim -force antmicro_ddr5_tester_usp_synth.v
