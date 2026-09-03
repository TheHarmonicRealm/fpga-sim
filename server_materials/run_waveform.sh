set -e # Quit if step 1 fails
# see Makefile lint_flags definition for some explanation
verilator --lint-only --timing -Werror-NULLPORT -I./user_inputs $COMPILE_FILES
verilator --binary --timing --trace-$1 -I./user_inputs $COMPILE_FILES # $1 is either vcd or fst
./obj_dir/Vtb