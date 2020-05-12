// -----------------------------------------------------------------------------
// Copyright (C) 2019 Angel Terrones <angelterrones@gmail.com>
// -----------------------------------------------------------------------------

`default_nettype none
`timescale 1 ns / 1 ps

module mux_switch #(
                    parameter                  NSLAVES    = 4,
                    parameter [NSLAVES*32-1:0] BASE_ADDR  = 0,
                    parameter [NSLAVES*5-1:0]  ADDR_WIDTH = 0
                    )(
                      input wire [31:0]           master_addr,
                      input wire [31:0]           master_wdata,
                      input wire [3:0]            master_sel,
                      input wire                  master_we,
                      input wire                  master_cyc,
                      input wire                  master_stb,
                      input wire [2:0]            master_cti,
                      input wire [1:0]            master_bte,
                      output wire [31:0]          master_rdata,
                      output wire                 master_ack,
                      output wire                 master_err,
                      //
                      output wire [31:0]          slave_addr,
                      output wire [31:0]          slave_wdata,
                      output wire [3:0]           slave_sel,
                      output wire                 slave_we,
                      output wire [NSLAVES-1:0]   slave_cyc,
                      output wire [NSLAVES-1:0]   slave_stb,
                      output wire [2:0]           slave_cti,
                      output wire [1:0]           slave_bte,
                      input wire [NSLAVES*32-1:0] slave_rdata,
                      input wire [NSLAVES-1:0]    slave_ack,
                      input wire [NSLAVES-1:0]    slave_err
                      );
    // =====================================================================
    localparam NBITSLAVE = clog2(NSLAVES);
    //
    reg [NBITSLAVE-1:0] slave_select;
    wire [NSLAVES-1:0]  match;
    // Get selected slave
    generate
        genvar i;
        for (i = 0; i < NSLAVES; i = i + 1) begin:addr_match
            localparam idx = ADDR_WIDTH[i*5+:5];
            assign match[i] = master_addr[31:idx] == BASE_ADDR[i*32+idx+:32-idx];
        end
    endgenerate

    always @(*) begin
        slave_select = 0;
        begin: slave_match
            integer idx;
            for (idx = 0; idx < NSLAVES; idx = idx + 1) begin : find_slave
                if (match[idx]) slave_select = idx[NBITSLAVE-1:0];
            end
        end
    end

    assign slave_addr   = master_addr;
    assign slave_wdata  = master_wdata;
    assign slave_sel    = master_sel;
    assign slave_we     = master_we;
    assign slave_cyc    = match & {NSLAVES{master_cyc}};
    assign slave_stb    = match & {NSLAVES{master_stb}};
    assign slave_cti    = master_cti;
    assign slave_bte    = master_bte;
    assign master_rdata = slave_rdata[slave_select*32+:32];
    assign master_ack   = slave_ack[slave_select];
    assign master_err   = slave_err[slave_select];

    // I hate ISE c:
    function integer clog2;
        input integer value;
        begin
            value = value - 1;
            for (clog2 = 0; value > 0; clog2 = clog2 + 1)
              value = value >> 1;
        end
    endfunction
    // =====================================================================
endmodule // bus
`default_nettype wire
// EOF
