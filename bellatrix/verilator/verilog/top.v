// -----------------------------------------------------------------------------
// Copyright (C) 2019 Angel Terrones <angelterrones@gmail.com>
// -----------------------------------------------------------------------------
// Title       : CPU testbench
// Project     : Bellatrix
// Description : Top module for the CPU testbench
// -----------------------------------------------------------------------------

`default_nettype none
`timescale 1 ns / 1 ps

$icache
$dcache

module top (
    input wire clk,
    input wire rst
    );
    //--------------------------------------------------------------------------
    localparam       MEM_SIZE   = 32'h0100_0000;
    localparam [4:0] ADDR_WIDTH = $$clog2(MEM_SIZE);
    localparam       BASE_ADDR  = 32'h8000_0000;

    wire [31:0]  iport__addr;
    wire [31:0]  iport__dat_w;
    wire [3:0]   iport__sel;
    wire         iport__we;
    wire [2:0]   iport__cti;
    wire [1:0]   iport__bte;
    wire         iport__cyc;
    wire         iport__stb;
    wire [31:0]  iport__dat_r;
    wire         iport__ack;

    wire [31:0]  dport__addr;
    wire [31:0]  dport__dat_w;
    wire [3:0]   dport__sel;
    wire         dport__we;
    wire [2:0]   dport__cti;
    wire [1:0]   dport__bte;
    wire         dport__cyc;
    wire         dport__stb;
    wire [31:0]  dport__dat_r;
    wire         dport__ack;
    wire         dport__err;

    wire [31:0]  slave_addr;
    wire [31:0]  slave_dat_w;
    wire [3:0]   slave_sel;
    wire         slave_we;
    wire [2:0]   slave_cti;
    wire [1:0]   slave_bte;
    wire         slave0_cyc;
    wire         slave0_stb;
    wire [31:0]  slave0_dat_r;
    wire         slave0_ack;

    wire         slave1_cyc;
    wire         slave1_stb;
    wire [31:0]  slave1_dat_r;
    wire         slave1_ack;
    wire         slave1_err;
    wire         external_interrupt;
    wire         timer_interrupt;
    wire         software_interrupt;

    wire         unused;

`ifndef ICACHE
    assign iport__cti = 0;
    assign iport__bte = 0;
`endif

`ifndef DCACHE
    assign dport__cti = 0;
    assign dport__bte = 0;
`endif

    bellatrix_core cpu (// Outputs
                        .iport__adr        (iport__addr[31:0]),
                        .iport__dat_w       (iport__dat_w),
                        .iport__sel         (iport__sel),
                        .iport__cyc         (iport__cyc),
                        .iport__stb         (iport__stb),
                        .iport__we          (iport__we),
`ifdef ICACHE
                        .iport__cti         (iport__cti),
                        .iport__bte         (iport__bte),
`endif
                        .dport__adr         (dport__addr[31:0]),
                        .dport__dat_w       (dport__dat_w[31:0]),
                        .dport__sel         (dport__sel[3:0]),
                        .dport__cyc         (dport__cyc),
                        .dport__stb         (dport__stb),
                        .dport__we          (dport__we),
`ifdef DCACHE
                        .dport__cti         (dport__cti),
                        .dport__bte         (dport__bte),
`endif
                        // Inputs
                        .clk                (clk),
                        .rst                (rst),
                        .iport__dat_r       (iport__dat_r[31:0]),
                        .iport__ack         (iport__ack),
                        .iport__err         (0),
                        .dport__dat_r       (dport__dat_r[31:0]),
                        .dport__ack         (dport__ack),
                        .dport__err         (dport__err),
                        .external_interrupt (external_interrupt),
                        .timer_interrupt    (timer_interrupt),
                        .software_interrupt (software_interrupt)
                        );

    mux_switch #(// Parameters
                 .NSLAVES    (2),
                 //            1              0
                 .BASE_ADDR  ({32'h1000_0000, BASE_ADDR}),
                 .ADDR_WIDTH ({5'd8,          ADDR_WIDTH})
                 ) bus0 (// Outputs
                         .master_rdata   (dport__dat_r[31:0]),
                         .master_ack     (dport__ack),
                         .master_err     (dport__err),
                         .slave_addr     (slave_addr[31:0]),
                         .slave_wdata    (slave_dat_w[31:0]),
                         .slave_sel      (slave_sel[3:0]),
                         .slave_we       (slave_we),
                         .slave_cyc      ({slave1_cyc, slave0_cyc}),
                         .slave_stb      ({slave1_stb, slave0_stb}),
                         .slave_cti      (slave_cti),
                         .slave_bte      (slave_bte),
                         // Inputs
                         .master_addr    (dport__addr[31:0]),
                         .master_wdata   (dport__dat_w[31:0]),
                         .master_sel     (dport__sel[3:0]),
                         .master_we      (dport__we),
                         .master_cyc     (dport__cyc),
                         .master_stb     (dport__stb),
                         .master_cti     (dport__cti),
                         .master_bte     (dport__bte),
                         .slave_rdata    ({slave1_dat_r, slave0_dat_r}),
                         .slave_ack      ({slave1_ack,   slave0_ack}),
                         .slave_err      ({slave1_err,   1'b0})
                         );

    // slave 0: @BASE_ADDR
    ram #(// Parameters
          .ADDR_WIDTH (ADDR_WIDTH),
          .BASE_ADDR  (BASE_ADDR)
          ) memory (/*AUTOINST*/
                    // Outputs
                    .iwbs_dat_r        (iport__dat_r[31:0]),
                    .iwbs_ack          (iport__ack),
                    .dwbs_dat_r        (slave0_dat_r[31:0]),
                    .dwbs_ack          (slave0_ack),
                    // Inputs
                    .clk               (clk),
                    .rst               (rst),
                    .iwbs_addr         (iport__addr[31:0]),
                    .iwbs_cyc          (iport__cyc),
                    .iwbs_stb          (iport__stb),
                    .iwbs_cti          (iport__cti),
                    .iwbs_bte          (iport__bte),
                    .dwbs_addr         (slave_addr[31:0]),
                    .dwbs_dat_w        (slave_dat_w[31:0]),
                    .dwbs_sel          (slave_sel[3:0]),
                    .dwbs_cyc          (slave0_cyc),
                    .dwbs_stb          (slave0_stb),
                    .dwbs_cti          (slave_cti),
                    .dwbs_bte          (slave_bte),
                    .dwbs_we           (slave_we)
                    );

    // slave 1: @0x1000_0000
    interrupt int_helper(
                         .clk                (clk),
                         .rst                (rst),
                         .int_addr           (slave_addr),
                         .int_dat_w          (slave_dat_w),
                         .int_sel            (slave_sel),
                         .int_cyc            (slave1_cyc),
                         .int_stb            (slave1_stb),
                         .int_cti            (slave_cti),
                         .int_bte            (slave_bte),
                         .int_we             (slave_we),
                         .int_dat_r          (slave1_dat_r),
                         .int_ack            (slave1_ack),
                         .int_err            (slave1_err),
                         .external_interrupt (external_interrupt),
                         .timer_interrupt    (timer_interrupt),
                         .software_interrupt (software_interrupt)
                         );
    //--------------------------------------------------------------------------
endmodule

// Local Variables:
// verilog-library-directories: ("." "../../../rtl")
// flycheck-verilator-include-path: ("." "../../../rtl")
// End:
