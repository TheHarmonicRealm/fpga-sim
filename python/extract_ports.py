import re
from string import Template
from pathlib import Path
import textwrap

def chop_sp(in_str: str, prefix: str, suffix: str):
    '''chops off a suffix and a prefix'''
    return in_str[in_str.find(prefix):in_str.find(suffix)]

cpp_dict_entry = Template("{\"$name\", PortReference((void*) &(top_ref->$name), $width)}")
cpp_dict_wrapper = Template("std::unordered_map<std::string, PortReference> $name = {\n$entries_str\n};")

def indent_text(in_str: str, depth: int=1):
    '''indents x number of 4-space "tabs"'''
    return textwrap.indent(in_str, (" " * 4) * depth)

def double_quoted(in_str: str):
    '''C++ needs double but repr uses single -_-'''
    return f'"{in_str}"'

def format_cpp_dict_entry(name: str, width: int):
    return cpp_dict_entry.substitute(
        name=name, width=width
    )


def split_line(line: str):
    match = re.fullmatch(r"VL_(OUT|IN)\d*\(&(.*),(\d*),(\d*)\);", line)
    if match is None:
        raise ValueError(f"{line} did not have expected components")
    l_type, l_name, l_top, l_bottom = match.groups()
    l_width = 1 + abs(int(l_top) - int(l_bottom))
    if l_width > 64:
        raise RuntimeError(f"Port {l_name} is too wide")
    return (l_type == "IN"), l_name, l_width



def ports_dicts(header: Path):
    # Name -> width
    input_dict: dict[str, int] = {}
    output_dict: dict[str, int] = {}


    vtop_contents = open(header).read()

    alignas = chop_sp(vtop_contents, "class alignas", "#endif  // guard")

    ports_segment = chop_sp(alignas, "// PORTS", "// CELLS")
    with_one_comment = ports_segment[ports_segment.rfind("//"):]
    comments_gone = with_one_comment[with_one_comment.find("\n") + 1:].strip()


    for line in comments_gone.splitlines():
        l_is_input, l_name, l_width = split_line(line.strip())
        if l_is_input:
            input_dict[l_name] = l_width
        else:
            output_dict[l_name] = l_width

    return input_dict, output_dict

def write_driver(driver_template: Path, driver_output: Path, input_dict: dict[str, int], output_dict: dict[str, int]):

    in_strings = [format_cpp_dict_entry(name, width) for name, width in input_dict.items()]
    out_strings = [format_cpp_dict_entry(name, width) for name, width in output_dict.items()]


    sim_template = Template(driver_template.read_text())

    input_ports_str = indent_text(",\n".join(in_strings), 2)
    output_ports_str = indent_text(",\n".join(out_strings), 2)

    generated_content = sim_template.safe_substitute(
            input_ports=input_ports_str, output_ports=output_ports_str
        )

    driver_output.write_text(generated_content)