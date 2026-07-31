from pathlib import Path

top_folder = Path(__file__).resolve().parent.parent  # i.e. fpga-sim/
python_folder = top_folder.joinpath("python")
waveforms_folder = top_folder.joinpath("waveforms")  # fpga-sim/waveforms/
verilog_folder = top_folder.joinpath("verilog")  # fpga-sim/verilog/
live_sim_folder = verilog_folder.joinpath("live_sim")
testbench_folder = verilog_folder.joinpath("testbench")
settings_filepath = python_folder.joinpath("waveform_viewer_choice.txt")
docker_tag_filepath = python_folder.joinpath("docker_tag.txt")
board_data = python_folder.joinpath("board_data.toml")
user_board_data = python_folder.joinpath("board_data_user.toml")