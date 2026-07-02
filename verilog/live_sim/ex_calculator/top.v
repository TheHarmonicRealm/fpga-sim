`timescale 100ms / 10ms

module top(
    input clk,
    // number buttons
    input b0,
    input b1,
    input b2,
    input b3,
    input b4,
    input b5,
    input b6,
    input b7,
    input b8,
    input b9,
    // operator buttons
    input divide,
    input multiply,
    input subtract,
    input add,
    // = and c buttons
    input equals,
    input clear,
    // display
    output reg [3:0]         select,
    output reg [14:0]        matrix);

endmodule
