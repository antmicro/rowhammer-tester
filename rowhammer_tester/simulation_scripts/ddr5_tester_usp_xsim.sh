cp ../../build/ddr5_tester_usp/gateware/antmicro_ddr5_tester_usp_mem.init .
cp ../../build/ddr5_tester_usp/gateware/antmicro_ddr5_tester_usp_rom.init .
cp ../../build/ddr5_tester_usp/gateware/antmicro_ddr5_tester_usp_sram.init .
export VexRiscvPath=$(pip show pythondata-cpu-vexriscv | grep -e "Location" | sed 's|.* /|/|g')/pythondata_cpu_vexriscv/verilog/VexRiscv_Lite.v
vivado -mode batch -script ddr5_tester_usp_synth_design.tcl -nolog
xvlog -work simulation=../../build/ddr5_tester_usp/simulation -sv antmicro_ddr5_tester_usp_synth.v $XILINX_VIVADO/data/verilog/src/glbl.v antmicro_ddr5_tester_usp_synth_wrapper.sv --nolog
xelab -incr --debug typical --relax --mt auto -L xil_defaultlib -L unisims_ver -L unimacro_ver -L secureip -L simulation=../../build/ddr5_tester_usp/simulation simulation.antmicro_ddr5_tester_usp_synth_wrapper simulation.glbl --nolog --snapshot antmicro_ddr5_tester_usp
xsim --nolog antmicro_ddr5_tester_usp --t ddr5_tester_usp_xsim.tcl --onfinish stop
