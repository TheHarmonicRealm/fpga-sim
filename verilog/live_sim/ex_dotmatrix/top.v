`timescale 100ms / 10ms

module top(
    /* verilator lint_off UNUSEDSIGNAL */
    input clk,
    /* verilator lint_on UNUSEDSIGNAL */
    input [15:0]         switches,
    input                UB,
    input                DB,
    input                LB,
    input                RB,
    input                CB,
    output reg [3:0]         select,
    output reg [20:0]        matrix);

// Expected behavior:
// * Holding up, down, left, or right turns on each digit, left to right
// * For digits that are on:
//   * Holding center turns on the top row
//   * The leftmost switch turns on the bottom row
//   * All 15 other pixels are controlled by the switches, from the second-leftmost on

assign select [3] = UB;
assign select [2] = DB;
assign select [1] = RB;
assign select [0] = LB;

assign matrix[20:18] = {3{CB}};
assign matrix[17:3] = switches[14:0];
assign matrix[2:0] = {3{switches[15]}};

endmodule
