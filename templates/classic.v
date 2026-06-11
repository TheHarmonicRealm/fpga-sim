`timescale 100ms / 10ms
module top(
    input clk,
    input                UB,
    input                DB,
    input                LB,
    input                RB,
    input                CB,
    input [15:0]         switches,
    output reg [6:0]         segment,
    output reg               DP,
    output reg [3:0]         anode,
    output reg [15:0]        lights);

endmodule