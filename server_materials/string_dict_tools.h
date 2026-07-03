#include <vector>
#include <unordered_map>
#include <string>

#include "verilated.h"
std::vector<std::string> split_string(const std::string& input_string, const char* separator);
std::pair<std::string, std::string> split_at_comma(const std::string& input);
std::unordered_map<std::string, QData> py_string_to_map(const std::string& input);