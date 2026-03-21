# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

#useless prototype shit (updated version soon since this one is hardcodded)

import ast
import pickle
import textwrap
from typing import Any, Dict, List, Optional, Tuple


OPS: Dict[int, str] = {
    1:"LOAD_CONST", 2:"STORE_LOCAL", 3:"LOAD_LOCAL",
    4:"STORE_GLOBAL", 5:"LOAD_GLOBAL",
    6:"ADD", 7:"SUB", 8:"MUL", 9:"DIV", 10:"FDIV", 11:"MOD",
    12:"POW", 13:"LSHIFT", 14:"RSHIFT", 15:"OR", 16:"XOR", 17:"AND", 18:"MATMUL",
    19:"CALL", 20:"MAKE_VM", 21:"RETURN", 22:"IMPORT",
    23:"COMPARE", 24:"JUMP_IF_FALSE", 25:"JUMP",
    26:"AND_BOOL", 27:"OR_BOOL", 28:"LOAD_ATTR",
    29:"BUILD_TUPLE", 30:"BUILD_LIST", 31:"BUILD_SLICE", 32:"SUBSCRIPT",
}

CMP_OPS = {1:"==",2:"!=",3:"<",4:"<=",5:">",6:">=",7:"is",8:"is not",9:"in",10:"not in"}
BIN_OPS = {6:"+",7:"-",8:"*",9:"/",10:"//",11:"%",12:"**",13:"<<",14:">>",15:"|",16:"^",17:"&",18:"@"}


class _StackLifter:
    def __init__(self, bytecode, consts, names):
        self.bc     = list(bytecode)
        self.consts = list(consts)
        self.names  = list(names)
        self._stack: List[str] = []
        self._locals: Dict[str,str] = {}
        self._globals: Dict[str,str] = {}
        self._lines: List[str] = []
        self._nested_payloads: List[Tuple[int, str]] = []  # (const_idx, name)

    def _push(self, e: str): self._stack.append(e)
    def _pop(self) -> str: return self._stack.pop() if self._stack else "_underflow"
    def _emit(self, line: str): self._lines.append(line)

    def _fmt(self, val: Any) -> str:
        if isinstance(val, bytes): return f"<bytes[{len(val)}]>"
        return repr(val)

    def lift(self) -> str:
        bc = self.bc
        cx = 0
        while cx < len(bc) - 1:
            opc, opa = bc[cx], bc[cx+1]

            if opc == 1:
                val = self.consts[opa] if opa < len(self.consts) else None
                self._push(self._fmt(val) if not isinstance(val, bytes) else f"<payload_{opa}>")

            elif opc == 2:
                name = self.names[opa] if opa < len(self.names) else f"local_{opa}"
                val  = self._pop()
                self._locals[name] = val
                self._emit(f"{name} = {val}")

            elif opc == 3:
                name = self.names[opa] if opa < len(self.names) else f"local_{opa}"
                self._push(self._locals.get(name, name))

            elif opc == 4:
                name = self.names[opa] if opa < len(self.names) else f"global_{opa}"
                val  = self._pop()
                self._globals[name] = val
                self._emit(f"{name} = {val}")

            elif opc == 5:
                name = self.names[opa] if opa < len(self.names) else f"global_{opa}"
                self._push(self._globals.get(name, name))

            elif opc in BIN_OPS:
                b = self._pop(); a = self._pop()
                self._push(f"({a} {BIN_OPS[opc]} {b})")

            elif opc == 19:
                args = [self._pop() for _ in range(opa)][::-1]
                func = self._pop()
                self._push(f"{func}({', '.join(args)})")

            elif opc == 20:
                name = self.names[opa] if opa < len(self.names) else f"vm_{opa}"
                self._pop()  # discard bytes placeholder
                self._nested_payloads.append((opa, name))
                self._emit(f"# {name} = VM(<nested payload>)  — see lifted definition above")
                self._globals[name] = name

            elif opc == 21:
                val = self._pop()
                self._emit(f"return {val}")
                break

            elif opc == 22:
                name = self.names[opa] if opa < len(self.names) else f"mod_{opa}"
                self._emit(f"import {name}")
                self._globals[name] = name

            elif opc == 23:
                b = self._pop(); a = self._pop()
                op = CMP_OPS.get(opa, f"cmp_{opa}")
                self._push(f"({a} {op} {b})")

            elif opc == 24:
                cond   = self._pop()
                target = opa
                self._emit(f"if not ({cond}):  # else jump to [{target}]")
                self._emit(f"    pass")

            elif opc == 25:
                target = opa
                if target <= cx:
                    self._emit(f"# ↑ loop back to [{target}]")
                else:
                    self._emit(f"# → jump to [{target}]")

            elif opc == 26:
                b = self._pop(); a = self._pop()
                self._push(f"({a} and {b})")

            elif opc == 27:
                b = self._pop(); a = self._pop()
                self._push(f"({a} or {b})")

            elif opc == 28:
                attr_str = self._pop()
                obj      = self._pop()
                try:
                    attr = ast.literal_eval(attr_str)
                    self._push(f"{obj}.{attr}")
                except Exception:
                    self._push(f"getattr({obj}, {attr_str})")

            elif opc == 29:
                items = [self._pop() for _ in range(opa)][::-1]
                self._push(f"({', '.join(items)},)")

            elif opc == 30:
                items = [self._pop() for _ in range(opa)][::-1]
                self._push(f"[{', '.join(items)}]")

            elif opc == 31:
                step  = self._pop()
                stop  = self._pop()
                start = self._pop()
                s = f"{'' if start=='None' else start}:{'' if stop=='None' else stop}"
                if step != 'None': s += f":{step}"
                self._push(s)

            elif opc == 32:
                idx = self._pop(); obj = self._pop()
                self._push(f"{obj}[{idx}]")

            else:
                self._emit(f"# UNKNOWN_OPC {opc} {opa}")

            cx += 2

        return "\n".join(self._lines)


class VMLifter:

    def _has_vm_class_source(self, source: str) -> bool:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Match):
                        n = sum(
                            1 for c in child.cases
                            if isinstance(c.pattern, ast.MatchValue)
                            and isinstance(c.pattern.value, ast.Constant)
                            and isinstance(c.pattern.value.value, int)
                        )
                        if n >= 8:
                            return True
        return False

    def _extract_payloads(self, source: str) -> List[Tuple[bytes, str]]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        result = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "VM"
                    and node.value.args
                    and isinstance(node.value.args[0], ast.Constant)
                    and isinstance(node.value.args[0].value, bytes)):
                name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else "vm"
                result.append((node.value.args[0].value, name))
        return result

    def _lift_data(self, data: Any, name: str) -> str:
        if not (isinstance(data, (tuple, list)) and len(data) >= 3):
            return f"# Cannot lift {name}: unexpected format"

        raw_bc, consts, raw_names = data[0], data[1], data[2]
        bc     = list(raw_bc)
        consts = list(consts)
        names  = list(raw_names)

        # Recursively lift nested VM payloads found in consts
        nested_defs: List[str] = []
        nested_name_map: Dict[int, str] = {}

        # Build const_idx → nested_func_name from MAKE_VM opcodes
        for i in range(0, len(bc) - 3, 2):
            if bc[i] == 1 and bc[i+2] == 20:
                const_idx = bc[i+1]
                name_idx  = bc[i+3]
                if name_idx < len(names):
                    nested_name_map[const_idx] = names[name_idx]

        for const_idx, nested_func_name in nested_name_map.items():
            if const_idx < len(consts) and isinstance(consts[const_idx], bytes):
                try:
                    nested_data = pickle.loads(consts[const_idx])
                    nested_defs.append(self._lift_data(nested_data, nested_func_name))
                except Exception as e:
                    nested_defs.append(f"# Could not lift {nested_func_name}: {e}")

        # Lift this function's bytecode
        lifter = _StackLifter(bc, consts, names)
        body   = lifter.lift()

        # Determine parameter names (first few names typically are params)
        # Use names that appear in LOAD_LOCAL before any STORE_LOCAL
        param_names: List[str] = []
        seen_stores: set = set()
        for i in range(0, len(bc) - 1, 2):
            opc2, opa2 = bc[i], bc[i+1]
            if opc2 == 2 and opa2 < len(names):
                seen_stores.add(names[opa2])
            elif opc2 == 3 and opa2 < len(names):
                n = names[opa2]
                if n not in seen_stores and n not in param_names:
                    param_names.append(n)

        params = ", ".join(param_names)
        func_src  = [f"def {name}({params}):"]
        for line in body.splitlines():
            func_src.append(f"    {line}")
        if not body.strip():
            func_src.append("    pass")

        parts = []
        if nested_defs:
            parts.extend(nested_defs)
            parts.append("")
        parts.append("\n".join(func_src))
        return "\n".join(parts)

    def deobfuscate(self, source: str) -> str:
        payloads = self._extract_payloads(source)
        if not payloads:
            return source

        header = [
            "# " + "═" * 60,
            "# VM BYTECODE — LIFTED TO PYTHON",
            "# The following reconstructs the embedded stack-VM programs.",
            "# " + "═" * 60,
            "",
        ]

        lifted_blocks: List[str] = []
        for payload_bytes, var_name in payloads:
            try:
                data = pickle.loads(payload_bytes)
                lifted_blocks.append(self._lift_data(data, var_name))
            except Exception as e:
                lifted_blocks.append(f"# Could not lift {var_name!r}: {e}")

        return "\n".join(header) + "\n\n".join(lifted_blocks)
