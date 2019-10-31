// -----------------------------------------------------------------------------
// Copyright (C) 2019 Angel Terrones <angelterrones@gmail.com>
// -----------------------------------------------------------------------------
// Title       : CPU testbench
// Project     : Bellartrix
// Description : Top module for the CPU testbench
// -----------------------------------------------------------------------------

`default_nettype none
`timescale 1 ns / 1 ps

module top (
    input wire clk,
    input wire rst,
    input wire external_interrupt,
    input wire timer_interrupt,
    input wire software_interrupt
    );
    //--------------------------------------------------------------------------
    localparam MEM_SIZE   = 32'h0100_0000;
    localparam ADDR_WIDTH = $clog2(MEM_SIZE);
    localparam BASE_ADDR  = 32'h8000_0000; // TODO: make this variable with the core...

    wire                dport__ack;
    wire [31:0]         dport__addr;
    wire                dport__cyc;
    wire [31:0]         dport__dat_r;
    wire [31:0]         dport__dat_w;
    wire [3:0]          dport__sel;
    wire                dport__stb;
    wire                dport__we;
    wire [2:0]          dport__cti;
    wire [1:0]          dport__bte;

    wire                iport__ack;
    wire [31:0]         iport__addr;
    wire                iport__cyc;
    wire [31:0]         iport__dat_r;
    wire [31:0]         iport__dat_w;
    wire [3:0]          iport__sel;
    wire                iport__stb;
    wire                iport__we;
    wire [2:0]          iport__cti;
    wire [1:0]          iport__bte;

    bellatrix_core cpu (// Outputs
                        .iport__addr        (iport__addr[31:0]),
                        .iport__dat_w       (iport__dat_w),
                        .iport__sel         (iport__sel),
                        .iport__cyc         (iport__cyc),
                        .iport__stb         (iport__stb),
                        .iport__we          (iport__we),
                        .iport__cti         (iport__cti),
                        .iport__bte         (iport__bte),
                        .dport__addr        (dport__addr[31:0]),
                        .dport__dat_w       (dport__dat_w[31:0]),
                        .dport__sel         (dport__sel[3:0]),
                        .dport__cyc         (dport__cyc),
                        .dport__stb         (dport__stb),
                        .dport__we          (dport__we),
                        .dport__cti         (dport__cti),
                        .dport__bte         (dport__bte),
                        // Inputs
                        .clk                (clk),
                        .rst                (rst),
                        .iport__dat_r       (iport__dat_r[31:0]),
                        .iport__ack         (iport__ack),
                        .iport__err         (0),
                        .dport__dat_r       (dport__dat_r[31:0]),
                        .dport__ack         (dport__ack),
                        .dport__err         (0),
                        .external_interrupt (external_interrupt),
                        .timer_interrupt    (timer_interrupt),
                        .software_interrupt (software_interrupt));


    ram #(// Parameters
          .ADDR_WIDTH (ADDR_WIDTH),
          .BASE_ADDR  (BASE_ADDR)
          ) memory (/*AUTOINST*/
                    // Outputs
                    .iwbs_dat_o        (iport__dat_r[31:0]),
                    .iwbs_ack_o        (iport__ack),
                    .dwbs_dat_o        (dport__dat_r[31:0]),
                    .dwbs_ack_o        (dport__ack),
                    // Inputs
                    .clk               (clk),
                    .rst               (rst),
                    .iwbs_addr_i       (iport__addr[31:0]),
                    .iwbs_cyc_i        (iport__cyc),
                    .iwbs_stb_i        (iport__stb),
                    .iwbs_cti          (iport__cti),
                    .iwbs_bte          (iport__bte),
                    .dwbs_addr_i       (dport__addr[31:0]),
                    .dwbs_dat_i        (dport__dat_w[31:0]),
                    .dwbs_sel_i        (dport__sel[3:0]),
                    .dwbs_cyc_i        (dport__cyc),
                    .dwbs_stb_i        (dport__stb),
                    .dwbs_cti          (dport__cti),
                    .dwbs_bte          (dport__bte),
                    .dwbs_we_i         (dport__we));
    //--------------------------------------------------------------------------
endmodule

// Local Variables:
// verilog-library-directories: ("." "../../../rtl")
// flycheck-verilator-include-path: ("." "../../../rtl")
// End:
