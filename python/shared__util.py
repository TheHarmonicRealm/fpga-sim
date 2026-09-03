'''Accessed from both the client and server programs'''
from __future__ import annotations

import ast
import dataclasses as dc
import os
import socket
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import textwrap
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    TextIO,
    get_args,
    get_origin,
    get_type_hints,
)

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

def is_dc_type(input: Any):
    return dc.is_dataclass(input) and isinstance(input, type)

def is_dc_instance(input: Any):
    return dc.is_dataclass(input) and not isinstance(input, type)

def serialize_dataclass(input: DataclassInstance) -> str:
    '''Turns a dataclass into a string representation of a dict.

    See `deserialize_dataclass()` for acceptable types list (dataclasses and
    Python literal structures).'''
    if is_dc_instance(input): # TODO: recursively check that fields are all appropriate and throw type error otherwise
        return str(dc.asdict(input))
    else:
        raise TypeError(f"{input} is not a dataclass")

def deserialize_dataclass[T: DataclassInstance](input: str, dc_type: type[T]) -> T:
    '''Attempts to turn the string input into a dict then recursively into
    an instance of the given dataclass type, also handling fields that are
    lists of dataclasses.

    CAUTION: For safety, uses `ast.literal_eval()`, so it only works properly
    if every field is one of:
    * dataclass subtype
    * list[dataclass subtype] <--- would be nice if this generally handled any
                literal containing a dataclass subtype
    * Python literal structure, meaning, according to docstring:
        * string
        * bytes
        * number
        * tuple
        * list
        * dict
        * set
        * boolean
        * None
    '''
    if is_dc_type(dc_type):
        # evaluate string to dict. like eval() but safer
        input_dict: dict = ast.literal_eval(input)
        dc_out = dc_type(**input_dict)
        for field in dc.fields(dc_type):
            field_type: type = field.type # pyright: ignore[reportAssignmentType]
            if is_dc_type(field_type): # if dataclass, recurse
                dict_str = str(getattr(dc_out, field.name)) # must convert back to string for literal_eval
                setattr(dc_out, field.name, deserialize_dataclass(dict_str, field_type))
            else: # check for list[dataclass]
                hints = get_type_hints(dc_type)
                field_type = hints[field.name]
                if get_origin(field_type) == list:
                    if is_dc_type(inner_type := get_args(field_type)[0]):
                        for i, item in enumerate(field_list := getattr(dc_out, field.name)):
                            field_list[i] = deserialize_dataclass(str(item), inner_type)
        return dc_out
    else:
        raise TypeError

@dataclass
class NamedFile:
    '''A way to read and transmit, or receive and write, a **text** file.
    Binary file types (such as FST) will crash this!'''
    name: str
    content: str

    def to_disk(self, directory: Path = Path(".")):
        with open(Path.joinpath(directory.joinpath(self.name)), "w") as fp:
            fp.write(self.content)

    @classmethod
    def from_fp(cls, fp: TextIO, *, close_after: bool):
        output = NamedFile(os.path.basename(fp.name), fp.read())
        if close_after:
            fp.close()
        return output

@dataclass
class BuildLiveCommand:
    files: list[NamedFile]
    expected_inputs: dict[str, int]
    expected_outputs: dict[str, int]

    CODE: ClassVar[str] = "BL"

@dataclass
class StartLiveCommand:

    CODE: ClassVar[str] = "SL"

@dataclass
class WaveformSimCommand:
    file_type: str # VCD or FST
    files: list[NamedFile]

    CODE: ClassVar[str] = "WS"

@dataclass
class ErrorMessage:
    body: str

    CODE: ClassVar[str] = "ER"

@dataclass
class AckMessage:

    CODE: ClassVar[str] = "AK"

AnyCommand = BuildLiveCommand | StartLiveCommand |WaveformSimCommand

class UnexpectedTermination(Exception):
    pass
class NormalTermination(Exception):
    pass
class BadHeader(Exception):
    pass

# Credit https://stackoverflow.com/a/17668009/
def big_receive(sock: socket.socket):
    '''Safely receives up to 10 GB after a
    a 10-byte ASCII number header.'''
    length_bytes = sock.recv(10)
    if not length_bytes: # disconnected, returned empty array
        raise NormalTermination
    try:
        expected_length = int(length_bytes.decode())
    except ValueError:
        raise BadHeader(f"{length_bytes}")
    data = bytearray() # mutable equivalent of bytes type
    while len(data) < expected_length:
        packet = sock.recv(expected_length - len(data))
        if not packet:
            raise UnexpectedTermination
        data.extend(packet)
    return data

def send_message(message: str | bytes, sock: socket.socket):
    # With non-ASCII strings, length(str) < length(str.encode())
    if isinstance(message, str):
        message = message.encode()
    header = f"{len(message):010}".encode()
    sock.send(header)
    sock.send(message)

def header_to_dc(header: str):
    match header:
        case BuildLiveCommand.CODE:
            return BuildLiveCommand
        case StartLiveCommand.CODE:
            return StartLiveCommand
        case WaveformSimCommand.CODE:
            return WaveformSimCommand
        case _:
            raise ValueError(header)

def receive_error_or_ack(sock: socket.socket):
    header = sock.recv(2)
    if header == b'': #TODO: maybe raise exception instead?
        print("Connection disconnected")
        return ErrorMessage
    else:
        match header.decode():
            case ErrorMessage.CODE:
                dc_type = ErrorMessage
            case AckMessage.CODE:
                dc_type = AckMessage
            case _:
                raise ValueError(header)
        message = big_receive(sock).decode()
        return deserialize_dataclass(message, dc_type)
    
def bool_list_to_int(bl: list[bool]):
    return sum(int(b) << i for i, b in enumerate(reversed(bl)))

def int_to_bool_list(num: int, width: int, *, invert: bool = False):
    partial_list = [bool(int(c)) for c in bin(num)[2:]]
    false_prefix = [False] * (width - len(partial_list))
    if not invert:
        return false_prefix + partial_list
    else:
        return [not x for x in (false_prefix + partial_list)]

def dict_diff(new: dict, old: dict):
    '''Assumes: new and old have all the same keys. Returns a dict with only
    the changed key-vals. Sadly: cannot require old and new to have the same
    exact type — just matches their supertypes — so type-checker will not get
    mad if this is passed a dict and a TypedDict.'''
    if difference := new.items() - old.items():
        return dict(difference)
    else:
        return {}
    
def indent_text(in_str: str, depth: int=1):
    '''indents x number of 4-space "tabs"'''
    return textwrap.indent(in_str, (" " * 4) * depth)

def first_matching[T](li: list[T], fn: Callable[[Any], bool]) -> T:
    for i in li:
        if fn(i):
            return i
    raise RuntimeError("first_matching() had unexpected error: Element not found in list!")