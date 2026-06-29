`timescale 100ms / 10ms

module top(
    input clk,
    /* verilator lint_off UNUSEDSIGNAL */
    input                UB,
    input                DB,
    input                LB,
    input                RB,
    input                CB,
    input [15:0]         switches,
    /* verilator lint_on UNUSEDSIGNAL */

    output reg [6:0]         segment,
    output reg               dp,
    output reg [3:0]         anode,	
    output reg [15:0]        lights);

// Expected behavior:
// * LEDs match corresponding switches if CB is pressed. Otherwise, all off.
// * Number display shows 8888 any of the buttons aside from CB are pressed.
// * When display is on, dot should be on.

always @(posedge clk) begin
    if(CB) begin
        lights <= switches;
    end
    else begin
        lights <= 16'b0;
    end
    if(!(UB | DB | LB | RB)) begin
        anode <= 4'b1111;
    end
    else begin
        anode <= 4'b0000;
    end
    segment <= 7'b0_000_000;
    dp <= 0;
end

    
endmodule
