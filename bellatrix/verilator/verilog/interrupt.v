// -----------------------------------------------------------------------------
// Copyright (C) 2019 Angel Terrones <angelterrones@gmail.com>
// -----------------------------------------------------------------------------

`default_nettype none
`timescale 1 ns / 1 ps

module interrupt(
        input wire clk,
        input wire rst,
        // bus
        input wire [31:0] int_addr,
        input wire [31:0] int_dat_w,
        input wire [ 3:0] int_sel,
        input wire        int_cyc,
        input wire        int_stb,
        input wire [2:0]  int_cti,
        input wire [1:0]  int_bte,
        input wire        int_we,
        output reg [31:0] int_dat_r,
        output reg        int_ack,
        output wire       int_err,
        // interrupt
        output wire external_interrupt,
        output wire timer_interrupt,
        output wire software_interrupt
        );
    //--------------------------------------------------------------------------
    reg soft_int; // @BASEADDRESS + 0
    reg timer_int; // @BASEADDRESS + 4
    reg ext_int;  // @BASEADDRESS + 8

    // reg to output
    assign external_interrupt = ext_int;
    assign timer_interrupt    = timer_int;
    assign software_interrupt = soft_int;

    // ACK logic
    always @(posedge clk or posedge rst) begin
        int_ack <= !int_ack && int_cyc && int_stb; // ignore cti and bte
        if (rst) begin
            int_ack <= 0;
        end
    end

    // error logic
    assign int_err = 0;

    // read logic
    always @(posedge clk or posedge rst) begin
        case (int_addr[3:0])
            4'b0000: int_dat_r <= soft_int;
            4'b0100: int_dat_r <= timer_int;
            4'b1000: int_dat_r <= ext_int;
            default: int_dat_r <= 32'bx;
        endcase
    end

    // write logic
    always @(posedge clk or posedge rst) begin
        if (int_ack && (&int_sel)) begin
            // verilator lint_off CASEINCOMPLETE
            case (int_addr[3:0])
                4'b0000:  soft_int  <= int_dat_w;
                4'b0100:  timer_int <= int_dat_w;
                4'b1000:  ext_int   <= int_dat_w;
            endcase
            // verilator lint_on CASEINCOMPLETE
        end
        if (rst) begin
            ext_int   <= 0;
            timer_int <= 0;
            soft_int  <= 0;
        end
    end

    //--------------------------------------------------------------------------
    // unused
    wire _unused = |{int_stb, int_cti, int_addr[31:4]};
    //--------------------------------------------------------------------------
endmodule
