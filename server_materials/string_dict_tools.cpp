#include <vector>
#include <unordered_map>
#include <string>

#include "string_dict_tools.h"
#include "verilated.h"

std::vector<std::string> split_string(const std::string& input_string, const char* separator) {
    std::vector<std::string> result = {};
    std::string segment = input_string;

    while(true) {
        auto next_sep = segment.find(*separator);
        if(next_sep != std::string::npos) { // At least one segment left
            result.push_back(segment.substr(0, next_sep));
            if(next_sep + 1 < segment.length()) { // There is stuff after segment, so continue loop
                segment = segment.substr(next_sep + 1);
            }
            else { // this was the last segment, followed by a separator with nothing after it
                break;
            }
        }
        else { // No more separators. Just put rest of string in last spot
            result.push_back(segment);
            break;
        }
    }

    return result;
}


std::pair<std::string, std::string> split_at_comma(const std::string& input) {
    auto comma_index = input.find(",");
    return std::pair<std::string, std::string>(input.substr(0, comma_index), input.substr(comma_index + 1));
}


std::unordered_map<std::string, QData> py_string_to_map(const std::string& input) {
    // Converts a Python str() representation of a string:string dict to a map
    // Example input: "{'key_1': 14, 'key_2': 2}"

    std::unordered_map<std::string, QData> output = {};

    // Get rid of the outer curly brackets: "'key_1': 14, 'key_2': 2}"
    auto trimmed_input = input.substr(1, input.length() - 2);

    // Vector of {"'key1': 14", " 'key_2': 2"} 
                              // ^ Note leading spaces after index 0
    auto keyval_strings = split_string(trimmed_input, ",");

    size_t index = 0;

    for(std::string keyval : keyval_strings) {
        if(index > 0) {
            keyval = keyval.substr(1); // Trim leading space
        }

        // Vector of {"'key1'", " 14"}
        std::vector<std::string> split = split_string(keyval, ":");

        std::string key = split[0];
        key = key.substr(1, key.length() - 2); // chop off single quotes
        QData val = stoll(split[1]); // stoi discards whitespace automatically

        output[key] = val;

        index ++;
    }

    return output;
}
