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
#include "Vtop.h"

#include "string_dict_tools.h"
#include "port_ref.h"

// Legacy function required only so linking works on Cygwin and MSVC++
// TODO: remove if I decide to only support running in Linux container [pretty likely]
double sc_time_stamp() { return 0; }

//Communication protocol: strings of name,state
//State is 16 ASCII 1/0
//Name is variable length matching these names:

    /* ports
        input                UB
        input                DB
        input                LB
        input                RB
        input                CB
        input [15:0]         switches

        output [6:0]         segment
        output               dp
        output [3:0]         anode
        output [15:0]        lights
    */

/*
    Each loop, each outputitem's update function is called.
    If it returns a value, that means the output it wraps has changed,
    and the new state should be sent to client (i.e. printed to stdout)
*/
class OutputItem {
    private:
        unsigned int* read_source;
        int width;

        unsigned int value;
        int mask;
    public:
        std::string name;
        // Returns boolean for if the state has changed, and an int of current state
        std::pair<bool, int> poll() {
            unsigned int new_value = *(this->read_source) & mask;
            bool anything_new = (value != new_value);
            value = new_value;
            return std::pair<bool, int>(anything_new, value);
        }

        OutputItem(unsigned int* read_source, const std::string& name, int width) {
            this->read_source = read_source;
            this->width = width;
            this->mask = 0;
            
            for(int i = 0; i < this->width; i++) {
                this->mask <<= 1;
            	this->mask |= 1;
            }
            
            this->name = name;

            this->value = 1300;
        }
};

void update_inputs(const std::string& input_string, std::unordered_map<std::string, PortReference> ports_map) {
    // Make dict of names to values for all things listed in input
    auto update_dict = py_string_to_map(input_string);

    // Go through update_dict and use the ports map to go from names to
    // references, updating all matching relevant input ports
    for(auto i : update_dict) {
        auto key = i.first;
        auto val = i.second;

        if(ports_map.find(key) != ports_map.end()) {
            ports_map.at(key).set(val);
        }
        else {
            std::cout << "Bad key: " << key << std::endl;
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

    // Initialize Vtop's input signals all to 0
    top->clk = 0;

    top->UB = 0;
    top->DB = 0;
    top->LB = 0;
    top->RB = 0;
    top->CB = 0;
    
    top->switches = 0;

    std::string input;

    // TODO: use PortReferences for outputs, too
    std::array<OutputItem, 4> outputs_array = {
        OutputItem ((unsigned int*) &(top->segment), "Segment", 7),
        OutputItem ((unsigned int*) &(top->dp), "DP", 1),
        OutputItem ((unsigned int*) &(top->anode), "Anode", 4),
        OutputItem ((unsigned int*) &(top->lights), "Lights", 16)
    };

    auto top_ref = top.get();
    
    // Map of names to input port references
    std::unordered_map<std::string, PortReference> input_ports_map = {
        {"UB", PortReference((void*) &(top_ref->UB), 1)},
        {"DB", PortReference((void*) &(top_ref->DB), 1)},
        {"LB", PortReference((void*) &(top_ref->LB), 1)},
        {"RB", PortReference((void*) &(top_ref->RB), 1)},
        {"CB", PortReference((void*) &(top_ref->CB), 1)},
        {"Switches", PortReference((void*) &(top_ref->switches), 16)},
    };


    while (1) {
        getline(std::cin, input);

        if(input.find("exit") != std::string::npos) {
            break;
        }
        else if(input.empty()) {
            // No new input sent
        }
        else {
            update_inputs(input, input_ports_map);
        }

        top->clk = !(top->clk); // Flip clock

        contextp->timeInc(1);  // Advance one time unit
        top->eval(); // and run one frame of the model

        bool need_to_send = false;

        std::unordered_map<std::string, int> output_map = {};

        for(auto &i : outputs_array) {
            auto [anything_new, state] = i.poll();
            need_to_send |= anything_new;
            
            output_map[i.name] = state;
        }

        if(need_to_send) {
            std::cout << "secretkey" << map_to_py_string(output_map) << std::endl; // flush necessary for Python subprocess pipe
        }
        else {
           std::cout << "secretkey" << std::endl;
        }

    }

    // Final model cleanup
    top->final();

    // Final simulation summary
    contextp->statsPrintSummary();

    // Return good completion status
    // Don't use exit() or destructor won't get called
    return 0;
}