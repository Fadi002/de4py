# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
VM analysis and devirtualization subsystem.

Pipeline: discover -> recover semantics -> extract bytecode -> lift to IR ->
rebuild control flow -> emit Python.
"""

from de4py.engines.onyx.vm.bytecode import PayloadExtractor, safe_loads
from de4py.engines.onyx.vm.discovery import VMDiscovery, find_dispatch_loop
from de4py.engines.onyx.vm.ir import Block, OpcodeSpec, VInstr, VMModel, VOp, VProgram
from de4py.engines.onyx.vm.lifter import build_cfg, decode, lift_program
from de4py.engines.onyx.vm.register_lifter import (
    RegisterPayloadExtractor,
    lift_register_program,
)
from de4py.engines.onyx.vm.table_dispatch import build_table_model, find_handler_table

__all__ = [
    "Block",
    "OpcodeSpec",
    "PayloadExtractor",
    "RegisterPayloadExtractor",
    "VInstr",
    "VMDiscovery",
    "VMModel",
    "VOp",
    "VProgram",
    "build_cfg",
    "build_table_model",
    "decode",
    "find_dispatch_loop",
    "find_handler_table",
    "lift_program",
    "lift_register_program",
    "safe_loads",
]
