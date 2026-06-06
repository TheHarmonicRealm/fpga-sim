# Derived from Verilator example: https://github.com/verilator/verilator/blob/master/examples/make_tracing_c/Makefile
# Original file was released under CC0 (public domain) by original author Wilson Snyder

# Check for sanity to avoid later confusion

ifneq ($(words $(CURDIR)),1)
  $(error Unsupported: GNU Make cannot build in directories containing spaces, build elsewhere: '$(CURDIR)')
endif

######################################################################
# Set up variables

# If $VERILATOR_ROOT isn't in the environment, we assume it is part of a
# package install, and verilator is in your path. Otherwise find the
# binary relative to $VERILATOR_ROOT (such as when inside the git sources).
ifeq ($(VERILATOR_ROOT),)
  VERILATOR = verilator
  VERILATOR_COVERAGE = verilator_coverage
else
  export VERILATOR_ROOT
  VERILATOR = $(VERILATOR_ROOT)/bin/verilator
  VERILATOR_COVERAGE = $(VERILATOR_ROOT)/bin/verilator_coverage
endif

# prevent situation where a module has a trailing comma, raising NULLPORT, but
# 	build still tries to happen and PINMISSING errors are also printed, based
# 	on the assumption that the nullport was intentional happen.
# TODO: probably there is a better way to avoid *some* inconsistent errors
#	without needing to terminate linting/elaboration completely
lint_flags = --lint-only -Werror-NULLPORT -I./user_inputs

# Generate C++ in executable form
VERILATOR_FLAGS += -cc --exe
# Generate makefile dependencies (not shown as complicates the Makefile)
VERILATOR_FLAGS += -MMD
# Optimize
VERILATOR_FLAGS += -x-assign fast
# Warn abount lint issues; may not want this on less solid designs
VERILATOR_FLAGS += -Wall
# Check SystemVerilog assertions
VERILATOR_FLAGS += --assert
# Generate coverage analysis
VERILATOR_FLAGS += --coverage
# Build it
VERILATOR_FLAGS += --build
# Make it look in ./user_inputs
VERILATOR_FLAGS += -I./user_inputs

# Input files for Verilator
VERILATOR_INPUT = $(COMPILE_FILES) string_dict_tools.cpp port_ref.cpp simulator_driver.cpp

######################################################################
default: build

build:
	@echo
	@echo "-- Verilator live sim build"
	@echo
	@echo "-- LINT ----------------"
	$(VERILATOR) $(lint_flags) $(VERILATOR_INPUT)
	@echo "-- VERILATE ----------------"
	$(VERILATOR) $(VERILATOR_FLAGS) $(VERILATOR_INPUT)

	@echo
	@echo "-- BUILD -------------------"
	$(MAKE) -j -C obj_dir -f ../Makefile_obj

	@echo
	@echo "-- DONE --------------------"
	@echo

######################################################################
# Other targets

show-config:
	$(VERILATOR) -V

maintainer-copy::
clean mostlyclean distclean maintainer-clean::
	-rm -rf obj_dir logs *.log *.dmp *.vpd coverage.dat core