add_force {/antmicro_ddr5_tester_usp_synth_wrapper/clk100_p} -radix hex {1 0ns} {0 5000ps} -repeat_every 10000ps
add_force {/antmicro_ddr5_tester_usp_synth_wrapper/clk100_n} -radix hex {0 0ns} {1 5000ps} -repeat_every 10000ps
add_force {/antmicro_ddr5_tester_usp_synth_wrapper/i2c_sda} -radix hex {1 0ns}
add_force {/antmicro_ddr5_tester_usp_synth_wrapper/i2c_scl} -radix hex {1 0ns}
add_force {/antmicro_ddr5_tester_usp_synth_wrapper/eth_mdio} -radix hex {1 0ns}
add_force {/antmicro_ddr5_tester_usp_synth_wrapper/eth_rx_ctl} -radix hex {1 0ns}
add_force {/antmicro_ddr5_tester_usp_synth_wrapper/eth_rx_data} -radix hex {1 0ns}
add_force {/antmicro_ddr5_tester_usp_synth_wrapper/eth_clocks_rx} -radix hex {1 0ns} {0 4000ps} -repeat_every 8000ps
add_force {/antmicro_ddr5_tester_usp_synth_wrapper/serial_rx} -radix hex {1 0ns}
add_force {/antmicro_ddr5_tester_usp_synth_wrapper/ddr5_alert_n} -radix hex {1 0ns}
add_force {/antmicro_ddr5_tester_usp_synth_wrapper/ddr5_pgood} -radix hex {1 0ns}
open_vcd
log_vcd
run all
close_vcd
exit
