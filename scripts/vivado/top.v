`timescale 1 ns / 1 ps

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
        output reg [31:0] iwbs_dat_o,
        output reg        iwbs_ack_o,
        // Data
        input wire [31:0] dwbs_addr_i,
        input wire [31:0] dwbs_dat_i,
        input wire [ 3:0] dwbs_sel_i,
        input wire        dwbs_cyc_i,
        input wire        dwbs_stb_i,
        input wire        dwbs_we_i,
        output reg [31:0] dwbs_dat_o,
        output reg        dwbs_ack_o
);

    localparam WORDS = 2**(ADDR_WIDTH - 2);
    //
    reg  [31:0]                 mem[0:WORDS - 1];
    wire [ADDR_WIDTH - 1 - 2:0] i_addr;
    wire [ADDR_WIDTH - 1 - 2:0] d_addr;
    wire                    i_access;
    wire                    d_access;
    // read instructions
    assign i_addr = {iwbs_addr_i[ADDR_WIDTH - 1:2]};

    always @(posedge clk) begin
        iwbs_dat_o <= mem[i_addr];
    end
    always @(posedge clk or posedge rst) begin
        iwbs_ack_o <= iwbs_cyc_i && iwbs_stb_i && !iwbs_ack_o;
        if (rst)
            iwbs_ack_o <= 0;
    end

    // read/write data
    assign d_addr   = {dwbs_addr_i[ADDR_WIDTH - 1:2]};
    always @(posedge clk) begin
        dwbs_dat_o <= mem[d_addr];
    end
    always @(posedge clk) begin
        if (dwbs_we_i && dwbs_ack_o) begin
            if (dwbs_sel_i[0]) mem[d_addr][0+:8]  <= dwbs_dat_i[0+:8];
            if (dwbs_sel_i[1]) mem[d_addr][8+:8]  <= dwbs_dat_i[8+:8];
            if (dwbs_sel_i[2]) mem[d_addr][16+:8] <= dwbs_dat_i[16+:8];
            if (dwbs_sel_i[3]) mem[d_addr][24+:8] <= dwbs_dat_i[24+:8];
        end
    end
    always @(posedge clk or posedge rst) begin
        dwbs_ack_o <= dwbs_cyc_i && dwbs_stb_i  && !dwbs_ack_o;
        if (rst)
            dwbs_ack_o <= 0;
    end

endmodule


module top(
    input wire clk,
    input wire rst,
    input wire external_interrupt,
    input wire timer_interrupt,
    input wire software_interrupt,
    output wire a,
    output wire b
    );
    //--------------------------------------------------------------------------
    localparam MEM_SIZE   = 32'h0001_0000;
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

    wire                iport__ack;
    wire [31:0]         iport__addr;
    wire                iport__cyc;
    wire [31:0]         iport__dat_r;
    wire [31:0]         iport__dat_w;
    wire [3:0]          iport__sel;
    wire                iport__stb;
    wire                iport__we;

    assign a = |iport__addr[10:0];
    assign b = |dport__addr[10:0];

    bellatrix_core cpu (// Outputs
                        .iport__addr        (iport__addr[31:0]),
                        .iport__dat_w       (iport__dat_w),
                        .iport__sel         (iport__sel),
                        .iport__cyc         (iport__cyc),
                        .iport__stb         (iport__stb),
                        .iport__we          (iport__we),
                        .dport__addr        (dport__addr[31:0]),
                        .dport__dat_w       (dport__dat_w[31:0]),
                        .dport__sel         (dport__sel[3:0]),
                        .dport__cyc         (dport__cyc),
                        .dport__stb         (dport__stb),
                        .dport__we          (dport__we),
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
                    .dwbs_addr_i       (dport__addr[31:0]),
                    .dwbs_dat_i        (dport__dat_w[31:0]),
                    .dwbs_sel_i        (dport__sel[3:0]),
                    .dwbs_cyc_i        (dport__cyc),
                    .dwbs_stb_i        (dport__stb),
                    .dwbs_we_i         (dport__we));
    //--------------------------------------------------------------------------
endmodule
