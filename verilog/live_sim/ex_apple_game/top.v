module top(
input clk,
input left,
input right,
input restart,

output [1:0] apple_spawn_row,
output [2:0] apple_left_col,
output [2:0] apple_center_col,
output [2:0] apple_right_col,
output [2:0] basket,
output [2:0] oof,

output [1:0] score_select,
output [14:0] score_pattern,
output [1:0] high_select,
output [14:0] high_pattern);


endmodule
