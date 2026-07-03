// Derived from Verilator example: https://github.com/verilator/verilator/blob/master/examples/make_tracing_c/sim_main.cpp
// Original file was released under CC0 (public domain) by original author Wilson Snyder

// For std::unique_ptr
#include <memory>
// Output stuff
#include <cstdio>
#include <iostream>
#include <string>
#include <bitset>
#include <sstream>

#include <array>
#include <unordered_map>
#include <vector>

// Include common routines
#include <verilated.h>

// Include model header, generated from Verilating "top.v"
#include "./obj_dir/Vtop.h"

#include "string_dict_tools.h"
#include "port_ref.h"

// Legacy function required only so linking works on Cygwin and MSVC++
// TODO: remove if I decide to only support running in Linux container [pretty likely]
double sc_time_stamp() { return 0; }

void update_inputs(const std::string& input_string, std::unordered_map<std::string, PortReference> ports_map) {
    // Make dict of names to values for all things listed in input
    auto update_dict = py_string_to_map(input_string);

    // Go through update_dict and use the ports map to go from names to
    // references, updating all matching relevant input ports
    for(const auto& [port_name, new_value] : update_dict) {
        if(ports_map.find(port_name) != ports_map.end()) {
            ports_map.at(port_name).set(new_value);
        }
        else {
            std::cout << "Bad key: " << port_name << std::endl;
        }
    }
}

std::string map_to_py_string(std::unordered_map<std::string, int> dict) {
    std::stringstream py_string_stream;

    bool inserted_one = false;
    for(auto i : dict) {
        if(inserted_one) { // Comma before entries after first
            py_string_stream << ", ";
        }
        else {
            inserted_one = true;
        }

        auto key = i.first;
        auto val = i.second;

        std::stringstream key_val_stream;
        key_val_stream << "'" << key << "': " << val;

        py_string_stream << key_val_stream.str();
    }

    return "{" + py_string_stream.str() + "}";
}

int main(int argc, char** argv) {
    // This is a more complicated example, please also see the simpler examples/make_hello_c.

    // Create logs/ directory in case we have traces to put under it
    Verilated::mkdir("logs");

    // Construct a VerilatedContext to hold simulation time, etc.
    // Multiple modules (made later below with Vtop) may share the same
    // context to share time, or modules may have different contexts if
    // they should be independent from each other.

    // Using unique_ptr is similar to
    // "VerilatedContext* contextp = new VerilatedContext" then deleting at end.
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    // Do not instead make Vtop as a file-scope static variable, as the
    // "C++ static initialization order fiasco" may cause a crash

    // Set debug level, 0 is off, 9 is highest presently used
    // May be overridden by commandArgs argument parsing
    contextp->debug(0);

    // Randomization reset policy
    // May be overridden by commandArgs argument parsing
    contextp->randReset(2);

    // Verilator must compute traced signals
    contextp->traceEverOn(false);

    // Pass arguments so Verilated code can see them, e.g. $value$plusargs
    // This needs to be called before you create any model
    contextp->commandArgs(argc, argv);

    // Construct the Verilated model, from Vtop.h generated from Verilating "top.v".
    // Using unique_ptr is similar to "Vtop* top = new Vtop" then deleting at end.
    // "TOP" will be the hierarchical name of the module.
    const std::unique_ptr<Vtop> top{new Vtop{contextp.get(), "TOP"}};

    std::string input;

    auto top_ref = top.get();
    
    // Map of names to input port references
    std::unordered_map<std::string, PortReference> input_ports_map = {
$input_ports
    };


    for(auto i : input_ports_map) {
        // Initialize Vtop's input signals all to 0, including clk
        i.second.set(0);
    }

    // Map of names to output port references

    std::unordered_map<std::string, PortReference> output_ports_map = {
$output_ports
    };


    while (1) {
        getline(std::cin, input);
        
        if(input == "{}" || input.empty()) {
            // Empty string or empty dict sent: do nothing
            // note that the latter doesn't happen under current design
        }
        else {
            update_inputs(input, input_ports_map);
        }
        
        #ifdef HAS_A_CLK
            top->clk = !(top->clk); // Flip clock
        #endif

        contextp->timeInc(1);  // Advance one time unit
        top->eval(); // and run one frame of the model

        std::unordered_map<std::string, int> output_map = {};

        for(auto i : output_ports_map) {
            auto name = i.first;

            output_map[name] = i.second.get();
        }

        std::cout << "secretkey" << map_to_py_string(output_map) << std::endl; // flush necessary for Python subprocess pipe

    }

    // Final model cleanup
    top->final();

    // Final simulation summary
    contextp->statsPrintSummary();

    // Return good completion status
    // Don't use exit() or destructor won't get called
    return 0;
}