module top(
    input [15:0] switches,
    output reg [15:0] lights
);

assign lights = switches;

endmodule
