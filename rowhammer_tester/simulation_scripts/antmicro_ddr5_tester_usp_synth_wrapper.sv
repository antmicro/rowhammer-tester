module antmicro_ddr5_tester_usp_synth_wrapper (
    output reg           serial_tx,
    input  wire          serial_rx,
    (* keep = "true" *)
    input  wire          clk100_p,
    input  wire          clk100_n,
    output wire          user_led0,
    output wire          user_led1,
    output wire          user_led2,
    output wire          user_led3,
    output wire          user_led4,
    output wire          ddr5_ck_t,
    output wire          ddr5_ck_c,
    output reg     [6:0] ddr5_A_ca,
    output reg     [6:0] ddr5_B_ca,
    output reg     [1:0] ddr5_A_cs_n,
    output reg     [1:0] ddr5_B_cs_n,
    output wire          ddr5_A_par,
    output wire          ddr5_B_par,
    input  wire          ddr5_alert_n,
    output wire          ddr5_reset_n,
    input  wire          ddr5_pgood,
    inout  wire   [31:0] ddr5_A_dq,
    inout  wire    [7:0] ddr5_A_dqs_t,
    inout  wire    [7:0] ddr5_A_dqs_c,
    input  wire    [7:0] ddr5_A_cb,
    input  wire    [1:0] ddr5_A_dqsb_t,
    input  wire    [1:0] ddr5_A_dqsb_c,
    inout  wire   [31:0] ddr5_B_dq,
    inout  wire    [7:0] ddr5_B_dqs_t,
    inout  wire    [7:0] ddr5_B_dqs_c,
    input  wire    [7:0] ddr5_B_cb,
    input  wire    [1:0] ddr5_B_dqsb_t,
    input  wire    [1:0] ddr5_B_dqsb_c,
    input  wire          ddr5_dlbdq,
    input  wire          ddr5_dlbdqs,
    (* keep = "true" *)
    input  wire          eth_clocks_rx,
    output wire          eth_clocks_tx,
    output wire          eth_rst_n,
    inout  wire          eth_mdio,
    output wire          eth_mdc,
    input  wire          eth_rx_ctl,
    input  wire    [3:0] eth_rx_data,
    output wire          eth_tx_ctl,
    output wire    [3:0] eth_tx_data,
    inout  wire          i2c_sda,
    inout  wire          i2c_scl,
    output wire          vin_bulk_en,
    output wire          vin_mgmt_en
);
    wire finish;
    antmicro_ddr5_tester_usp device(.*);
    always@(*) begin
        if (finish === 1) $finish;
    end
endmodule
