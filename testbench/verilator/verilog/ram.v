// -----------------------------------------------------------------------------
// Copyright (C) 2019 Angel Terrones <angelterrones@gmail.com>
// -----------------------------------------------------------------------------
// Title       : RAM
// Project     : Bellatrix
// Description : Dualport wishbone memory
// -----------------------------------------------------------------------------

`default_nettype none
`timescale 1 ns / 1 ps

// from https://github.com/openrisc/orpsoc-cores/blob/master/cores/wb_common/wb_common.v
function is_last;
    input [2:0] cti;
    begin
        case (cti)
            3'b000: is_last = 1;  // classic
            3'b001: is_last = 0;  // constant
            3'b010: is_last = 0;  // increment
            3'b111: is_last = 1;  // end
            default: $display("RAM: illegal Wishbone B4 cycle type (%b)", cti);
        endcase
    end
endfunction

// from https://github.com/openrisc/orpsoc-cores/blob/master/cores/wb_common/wb_common.v
function [31:0] wb_next_addr;
    input [31:0] addr_i;
    input [2:0]  cti_i;
    input [1:0]  bte_i;
    input integer dw;

    reg [31:0] addr;
    integer shift;

    begin
        shift = $clog2(dw/8);
        addr = addr_i >> shift;
        if (cti_i == 3'b010) begin
            case (bte_i)
                2'b00: addr = addr + 1;  // linear
                2'b01: addr = {addr[31:2], addr[1:0] + 2'd1}; // wrap4
                2'b10: addr = {addr[31:3], addr[2:0] + 3'd1}; // wrap8
                2'b11: addr = {addr[31:4], addr[3:0] + 4'd1}; // wrap16
            endcase
        end
        wb_next_addr = addr << shift;
    end
endfunction

module ram #(
             parameter ADDR_WIDTH = 22,
             parameter BASE_ADDR  = 32'h0000_0000
             )(
               input wire        clk,
               input wire        rst,
               // Instruction
               input wire [31:0] iwbs_addr_i,
               input wire        iwbs_cyc_i,
               input wire        iwbs_stb_i,
               input wire [2:0]  iwbs_cti,
               input wire [1:0]  iwbs_bte,
               output reg [31:0] iwbs_dat_o,
               output reg        iwbs_ack_o,
               // Data
               input wire [31:0] dwbs_addr_i,
               input wire [31:0] dwbs_dat_i,
               input wire [ 3:0] dwbs_sel_i,
               input wire        dwbs_cyc_i,
               input wire        dwbs_stb_i,
               input wire [2:0]  dwbs_cti,
               input wire [1:0]  dwbs_bte,
               input wire        dwbs_we_i,
               output reg [31:0] dwbs_dat_o,
               output reg        dwbs_ack_o
               );
    //--------------------------------------------------------------------------
    localparam BYTES = 2**ADDR_WIDTH;
    //
    byte                    mem[0:BYTES - 1]; // FFS, this MUST BE BYTE, FOR DPI.
    wire [31:0] i_addr;
    wire [31:0] d_addr;
    wire        i_valid;
    wire        d_valid;
    reg         i_valid_r;
    reg         d_valid_r;
    wire        i_last;
    wire        d_last;
    wire [31:0] i_nxt_addr;
    wire [31:0] d_nxt_addr;
    wire [31:0] _i_addr;
    wire [31:0] _d_addr;

    // read instructions
    assign _i_addr    = {{(32 - ADDR_WIDTH){1'b0}}, iwbs_addr_i[ADDR_WIDTH - 1:2], 2'b0};
    assign i_last     = is_last(iwbs_cti);
    assign i_nxt_addr = wb_next_addr(_i_addr, iwbs_cti, iwbs_bte, 32);
    assign i_addr     = ((i_valid & !i_valid_r) | i_last) ? _i_addr : i_nxt_addr;
    assign i_valid    = iwbs_cyc_i && iwbs_stb_i && (iwbs_addr_i[31:ADDR_WIDTH] == BASE_ADDR[31:ADDR_WIDTH]);

    always @(posedge clk) begin
        iwbs_dat_o <= 32'hx;
        if (i_valid) begin
            iwbs_dat_o[7:0]    <= mem[i_addr + 0];
            iwbs_dat_o[15:8]   <= mem[i_addr + 1];
            iwbs_dat_o[23:16]  <= mem[i_addr + 2];
            iwbs_dat_o[31:24]  <= mem[i_addr + 3];
        end
    end
    always @(posedge clk or posedge rst) begin
        iwbs_ack_o <= i_valid && (!((iwbs_cti == 3'b000) | (iwbs_cti == 3'b111)) | !iwbs_ack_o);

        i_valid_r <= i_valid;
        if (rst) begin
            iwbs_ack_o <= 0;
            i_valid_r  <= 0;
        end
    end

    // read/write data
    assign _d_addr    = {{(32 - ADDR_WIDTH){1'b0}}, dwbs_addr_i[ADDR_WIDTH - 1:2], 2'b0};
    assign d_last     = is_last(dwbs_cti);
    assign d_nxt_addr = wb_next_addr(_d_addr, dwbs_cti, dwbs_bte, 32);
    assign d_addr     = ((d_valid & !d_valid_r) | d_last) ? _d_addr : d_nxt_addr;
    assign d_valid    = dwbs_cyc_i && dwbs_stb_i && (dwbs_addr_i[31:ADDR_WIDTH] == BASE_ADDR[31:ADDR_WIDTH]);

    always @(posedge clk) begin
        dwbs_dat_o <= 32'hx;
        if (dwbs_we_i && d_valid && dwbs_ack_o) begin
            if (dwbs_sel_i[0]) mem[d_addr + 0] <= dwbs_dat_i[0+:8];
            if (dwbs_sel_i[1]) mem[d_addr + 1] <= dwbs_dat_i[8+:8];
            if (dwbs_sel_i[2]) mem[d_addr + 2] <= dwbs_dat_i[16+:8];
            if (dwbs_sel_i[3]) mem[d_addr + 3] <= dwbs_dat_i[24+:8];
        end else begin
            dwbs_dat_o[7:0]    <= mem[d_addr + 0];
            dwbs_dat_o[15:8]   <= mem[d_addr + 1];
            dwbs_dat_o[23:16]  <= mem[d_addr + 2];
            dwbs_dat_o[31:24]  <= mem[d_addr + 3];
        end
    end
    always @(posedge clk or posedge rst) begin
        dwbs_ack_o <= d_valid && (!((dwbs_cti == 3'b000) | (dwbs_cti == 3'b111)) | !dwbs_ack_o);

        d_valid_r <= d_valid;
        if (rst) begin
            dwbs_ack_o <= 0;
            d_valid_r  <= 0;
        end
    end
    //--------------------------------------------------------------------------
    // SystemVerilog DPI functions
    export "DPI-C" function ram_v_dpi_read_word;
    export "DPI-C" function ram_v_dpi_read_byte;
    export "DPI-C" function ram_v_dpi_write_word;
    export "DPI-C" function ram_v_dpi_write_byte;
    export "DPI-C" function ram_v_dpi_load;
    import "DPI-C" function void ram_c_dpi_load(input byte mem[], input string filename);
    //
    function int ram_v_dpi_read_word(int address);
        if (address[31:ADDR_WIDTH] != BASE_ADDR[31:ADDR_WIDTH]) begin
            $display("[RAM read word] Bad address: %h. Abort.\n", address);
            $finish;
        end
        return {mem[address[ADDR_WIDTH-1:0] + 3],
                mem[address[ADDR_WIDTH-1:0] + 2],
                mem[address[ADDR_WIDTH-1:0] + 1],
                mem[address[ADDR_WIDTH-1:0] + 0]};
    endfunction
    //
    function byte ram_v_dpi_read_byte(int address);
        if (address[31:ADDR_WIDTH] != BASE_ADDR[31:ADDR_WIDTH]) begin
            $display("[RAM read byte] Bad address: %h. Abort.\n", address);
            $finish;
        end
        return mem[address[ADDR_WIDTH-1:0]];
    endfunction
    //
    function void ram_v_dpi_write_word(int address, int data);
        if (address[31:ADDR_WIDTH] != BASE_ADDR[31:ADDR_WIDTH]) begin
            $display("[RAM write word] Bad address: %h. Abort.\n", address);
            $finish;
        end
        mem[address[ADDR_WIDTH-1:0] + 0] = data[7:0];
        mem[address[ADDR_WIDTH-1:0] + 1] = data[15:8];
        mem[address[ADDR_WIDTH-1:0] + 2] = data[23:16];
        mem[address[ADDR_WIDTH-1:0] + 3] = data[31:24];
    endfunction
    //
    function void ram_v_dpi_write_byte(int address, byte data);
        if (address[31:ADDR_WIDTH] != BASE_ADDR[31:ADDR_WIDTH]) begin
            $display("[RAM write word] Bad address: %h. Abort.\n", address);
            $finish;
        end
        mem[address[ADDR_WIDTH-1:0]] = data;
    endfunction
    //
    function void ram_v_dpi_load(string filename);
        ram_c_dpi_load(mem, filename);
    endfunction
    //--------------------------------------------------------------------------
    // unused signals: remove verilator warnings about unused signal
    wire _unused = |{iwbs_addr_i[1:0], dwbs_addr_i[1:0]};
    //--------------------------------------------------------------------------
endmodule
