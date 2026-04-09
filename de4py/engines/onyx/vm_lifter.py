# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
engines/vm_lifter.py

Dynamic stack-based VM bytecode lifter.

Instead of hardcoding opcode semantics, this engine:
  1. Detects a VM class in source by finding a class with a __call__ method
     containing a match/case dispatch on an integer opcode variable.
  2. Reads the match/case body to infer what each opcode DOES
     (push, pop, store_local, store_global, binary op, call, return, etc.)
  3. Extracts pickle payloads from VM(...) call sites.
  4. Lifts each payload's bytecode to readable Python using the extracted
     opcode semantics.

This makes the lifter work on ANY stack VM that follows the pattern:
    while cx < len(bytecode):
        opc = bytecode[cx]; opa = bytecode[cx+1]
        match opc:
            case N: <semantics>
        cx += 2
"""

import ast
import pickle
import re
import textwrap
from typing import Any, Dict, List, Optional, Tuple


# ─── Opcode semantic inference ────────────────────────────────────────────────

class _OpcodeInfo:
    """Describes what a single opcode does."""
    def __init__(self, num: int, body_src: List[str]):
        self.num      = num
        self.body_src = body_src        # raw unparsed statements
        self.kind     = self._infer_kind()

    def _infer_kind(self) -> str:
        src = ' '.join(self.body_src)
        if 'return' in src:              return 'RETURN'
        if 'import' in src and '__import__' in src: return 'IMPORT'
        if 'append' in src or 'push' in src:
            if 'consts' in src:          return 'LOAD_CONST'
            if 'locals' in src or 'vlocals' in src:
                if 'names' in src:       return 'LOAD_LOCAL'
            if 'globals' in src or 'vglobals' in src:
                if 'names' in src:       return 'LOAD_GLOBAL'
        if ('pop' in src or 'pop()' in src) and ('=' in src):
            if 'locals' in src or 'vlocals' in src: return 'STORE_LOCAL'
            if 'globals' in src or 'vglobals' in src: return 'STORE_GLOBAL'
            if 'VM(' in src:             return 'MAKE_VM'
        if 'getattr' in src:             return 'LOAD_ATTR'
        if '+' in src and 'pop' in src:  return 'BINARY_ADD'
        if '-' in src and 'pop' in src:  return 'BINARY_SUB'
        if '*' in src and 'pop' in src and '**' not in src: return 'BINARY_MUL'
        if '//' in src and 'pop' in src:  return 'BINARY_FDIV'
        if '/' in src and 'pop' in src:  return 'BINARY_DIV'
        if '%' in src and 'pop' in src:  return 'BINARY_MOD'
        if '**' in src and 'pop' in src: return 'BINARY_POW'
        if '^' in src and 'pop' in src:  return 'BINARY_XOR'
        if '|' in src and 'pop' in src:  return 'BINARY_OR'
        if '&' in src and 'pop' in src:  return 'BINARY_AND'
        if '<<' in src and 'pop' in src: return 'BINARY_LSHIFT'
        if '>>' in src and 'pop' in src: return 'BINARY_RSHIFT'
        if 'function(' in src or 'func(' in src or '(*args)' in src: return 'CALL'
        if 'if not' in src and 'cx' in src: return 'JUMP_IF_FALSE'
        if 'cx =' in src and 'continue' in src: return 'JUMP'
        if 'tuple' in src and 'values' in src: return 'BUILD_TUPLE'
        if 'list' in src or ('values' in src and 'append' in src): return 'BUILD_LIST'
        if 'slice' in src:               return 'BUILD_SLICE'
        if '[' in src and ']' in src and 'pop' in src: return 'SUBSCRIPT'
        if 'match' in src and 'opa' in src: return 'COMPARE'
        if 'and' in src and 'pop' in src: return 'AND_BOOL'
        if 'or' in src and 'pop' in src:  return 'OR_BOOL'
        return f'OPC_{self.num}'


class _VMOpcodeTable:
    """Extracted opcode table from a VM class."""

    def __init__(self):
        self.opcodes: Dict[int, _OpcodeInfo] = {}
        self.stack_var     = 'stack'
        self.const_var     = 'consts'
        self.name_var      = 'names'
        self.local_var     = 'locals'
        self.cx_var        = 'cx'
        self.bytecode_var  = 'bytecode'

    def load_from_class(self, cls_node: ast.ClassDef) -> bool:
        """Parse the VM class and populate the opcode table. Returns True on success."""
        call_method = None
        for item in cls_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == '__call__':
                call_method = item
                break

        if call_method is None:
            return False

        # Infer variable names from assignments in the method
        for stmt in ast.walk(call_method):
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                t = stmt.targets[0]
                v = stmt.value
                if isinstance(t, ast.Name):
                    if isinstance(v, ast.List) and not v.elts:
                        self.stack_var = t.id
                    if (isinstance(v, ast.Attribute)
                            and isinstance(v.value, ast.Name)
                            and v.value.id == 'self'):
                        if 'const' in v.attr.lower():  self.const_var   = t.id
                        if 'name'  in v.attr.lower():  self.name_var    = t.id
                        if 'byte'  in v.attr.lower():  self.bytecode_var = t.id

        # Find the match statement
        for stmt in ast.walk(call_method):
            if isinstance(stmt, ast.Match):
                for case in stmt.cases:
                    pat = case.pattern
                    if (isinstance(pat, ast.MatchValue)
                            and isinstance(pat.value, ast.Constant)
                            and isinstance(pat.value.value, int)):
                        opc_num  = pat.value.value
                        body_src = [ast.unparse(s) for s in case.body]
                        self.opcodes[opc_num] = _OpcodeInfo(opc_num, body_src)
                return True  # found it

        return bool(self.opcodes)


# ─── Stack lifter ─────────────────────────────────────────────────────────────

_BIN_OPS = {
    'BINARY_ADD':'+','BINARY_SUB':'-','BINARY_MUL':'*','BINARY_FDIV':'//', 'BINARY_DIV':'/',
    'BINARY_MOD':'%','BINARY_POW':'**','BINARY_XOR':'^','BINARY_OR':'|',
    'BINARY_AND':'&','BINARY_LSHIFT':'<<','BINARY_RSHIFT':'>>',
}

_CMP_OPS = {1:'==',2:'!=',3:'<',4:'<=',5:'>',6:'>=',
            7:'is',8:'is not',9:'in',10:'not in'}


class _StackLifter:
    def __init__(self, bc: List[int], consts: List[Any], names: List[str],
                 table: _VMOpcodeTable):
        self.bc     = bc
        self.consts = consts
        self.names  = names
        self.table  = table
        self._stack : List[str] = []
        self._locals: Dict[str,str] = {}
        self._globals:Dict[str,str] = {}
        self._lines : List[str] = []

    def _push(self, e): self._stack.append(e)
    def _pop(self):     return self._stack.pop() if self._stack else '_underflow'
    def _emit(self, l): self._lines.append(l)
    def _name(self, i): return self.names[i] if i < len(self.names) else f'names_{i}'
    def _const(self, i):
        if i >= len(self.consts): return f'consts_{i}'
        v = self.consts[i]
        return f'<bytes[{len(v)}]>' if isinstance(v, bytes) else repr(v)

    def lift(self) -> str:
        cx = 0
        while cx < len(self.bc) - 1:
            opc, opa = self.bc[cx], self.bc[cx+1]
            info = self.table.opcodes.get(opc)
            kind = info.kind if info else f'OPC_{opc}'

            if kind == 'LOAD_CONST':
                self._push(self._const(opa))
            elif kind == 'STORE_LOCAL':
                n = self._name(opa); v = self._pop()
                self._locals[n] = v; self._emit(f'{n} = {v}')
            elif kind == 'LOAD_LOCAL':
                n = self._name(opa); self._push(self._locals.get(n, n))
            elif kind == 'STORE_GLOBAL':
                n = self._name(opa); v = self._pop()
                self._globals[n] = v; self._emit(f'{n} = {v}')
            elif kind == 'LOAD_GLOBAL':
                n = self._name(opa); self._push(self._globals.get(n, n))
            elif kind in _BIN_OPS:
                b = self._pop(); a = self._pop()
                self._push(f'({a} {_BIN_OPS[kind]} {b})')
            elif kind == 'CALL':
                args = [self._pop() for _ in range(opa)][::-1]
                func = self._pop()
                self._push(f'{func}({", ".join(args)})')
            elif kind == 'MAKE_VM':
                n = self._name(opa); self._pop()
                self._emit(f'# {n} = VM(<nested>)  — see nested def above')
                self._globals[n] = n
            elif kind == 'RETURN':
                self._emit(f'return {self._pop()}'); break
            elif kind == 'IMPORT':
                n = self._name(opa); self._emit(f'import {n}')
                self._globals[n] = n
            elif kind == 'COMPARE':
                b = self._pop(); a = self._pop()
                op = _CMP_OPS.get(opa, f'cmp_{opa}')
                self._push(f'({a} {op} {b})')
            elif kind == 'JUMP_IF_FALSE':
                cond = self._pop()
                self._emit(f'if not ({cond}):  # jump → [{opa}]')
                self._emit('    pass')
            elif kind == 'JUMP':
                self._emit(f'# jump → [{opa}]')
                if opa <= cx:
                    self._emit('# ↑ loop back')
            elif kind == 'AND_BOOL':
                b = self._pop(); a = self._pop(); self._push(f'({a} and {b})')
            elif kind == 'OR_BOOL':
                b = self._pop(); a = self._pop(); self._push(f'({a} or {b})')
            elif kind == 'LOAD_ATTR':
                attr = self._pop(); obj = self._pop()
                try:
                    attr_name = ast.literal_eval(attr)
                    self._push(f'{obj}.{attr_name}')
                except Exception:
                    self._push(f'getattr({obj}, {attr})')
            elif kind == 'BUILD_TUPLE':
                items = [self._pop() for _ in range(opa)][::-1]
                self._push(f'({", ".join(items)},)')
            elif kind == 'BUILD_LIST':
                items = [self._pop() for _ in range(opa)][::-1]
                self._push(f'[{", ".join(items)}]')
            elif kind == 'BUILD_SLICE':
                step=self._pop(); stop=self._pop(); start=self._pop()
                s = f'{""if start=="None" else start}:{""if stop=="None" else stop}'
                if step != 'None': s += f':{step}'
                self._push(s)
            elif kind == 'SUBSCRIPT':
                idx=self._pop(); obj=self._pop()
                self._push(f'{obj}[{idx}]')
            else:
                self._emit(f'# {kind}  opa={opa}')

            cx += 2

        return '\n'.join(self._lines)


# ─── Main engine ──────────────────────────────────────────────────────────────

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
                        if n >= 6:
                            return True
        return False

    def _extract_vm_class(self, source: str) -> Optional[_VMOpcodeTable]:
        """Parse the VM class from source and return its opcode table."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                table = _VMOpcodeTable()
                if table.load_from_class(node):
                    print(f'[VMLifter] Extracted {len(table.opcodes)} opcodes from {node.name}')
                    return table
        return None

    def _extract_payloads(self, source: str) -> List[Tuple[bytes, str]]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        result = []
        for node in ast.walk(tree):
            # vm = VM(b'...') or VM(b'...')()
            call = None
            var_name = 'vm'
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(node.targets[0], ast.Name):
                    var_name = node.targets[0].id
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                c = node.value
                # VM(b'...')()
                if isinstance(c.func, ast.Call):
                    call = c.func

            if call and isinstance(call.func, ast.Name):
                if call.args and isinstance(call.args[0], ast.Constant):
                    v = call.args[0].value
                    if isinstance(v, bytes) and len(v) > 10:
                        result.append((v, var_name))
        return result

    def _lift_data(self, data: Any, name: str, table: _VMOpcodeTable) -> str:
        if not (isinstance(data, (tuple, list)) and len(data) >= 3):
            return f'# Cannot lift {name}: unexpected format'

        bc     = list(data[0])
        consts = list(data[1])
        names  = list(data[2])

        # Find nested VMs in consts (LOAD_CONST → MAKE_VM pattern)
        nested_name_map: Dict[int, str] = {}
        for i in range(0, len(bc) - 3, 2):
            if bc[i+2] == next((k for k, v in table.opcodes.items()
                                if v.kind == 'MAKE_VM'), None):
                const_idx = bc[i+1]
                name_idx  = bc[i+3]
                if name_idx < len(names):
                    nested_name_map[const_idx] = names[name_idx]

        nested_defs = []
        for ci, fn in nested_name_map.items():
            if ci < len(consts) and isinstance(consts[ci], bytes):
                try:
                    nd = pickle.loads(consts[ci])
                    nested_defs.append(self._lift_data(nd, fn, table))
                except Exception as e:
                    nested_defs.append(f'# Could not lift {fn}: {e}')

        lifter = _StackLifter(bc, consts, names, table)
        body   = lifter.lift()

        # Infer params: LOAD_LOCAL before first STORE_LOCAL
        params, seen = [], set()
        for i in range(0, len(bc)-1, 2):
            opc2, opa2 = bc[i], bc[i+1]
            load_opc  = [k for k,v in table.opcodes.items() if v.kind=='LOAD_LOCAL']
            store_opc = [k for k,v in table.opcodes.items() if v.kind=='STORE_LOCAL']
            if opc2 in store_opc and opa2 < len(names):
                seen.add(names[opa2])
            elif opc2 in load_opc and opa2 < len(names):
                n = names[opa2]
                if n not in seen and n not in params:
                    params.append(n)

        lines = [f'def {name}({", ".join(params)}):']
        if body.strip():
            lines += [f'    {l}' for l in body.splitlines()]
        else:
            lines.append('    pass')

        parts = []
        if nested_defs:
            parts.extend(nested_defs)
            parts.append('')
        parts.append('\n'.join(lines))
        return '\n'.join(parts)

    def deobfuscate(self, source: str) -> str:
        try:
            table    = self._extract_vm_class(source)
            payloads = self._extract_payloads(source)
            if not payloads:
                return source

            header = [
                '# ' + '═'*60,
                '# VM BYTECODE — LIFTED TO PYTHON (dynamic opcode extraction)',
                '# ' + '═'*60,
                '',
            ]
            blocks = []
            for payload_bytes, var_name in payloads:
                try:
                    data = pickle.loads(payload_bytes)
                    blocks.append(self._lift_data(data, var_name, table or _VMOpcodeTable()))
                except Exception as e:
                    blocks.append(f'# Could not lift {var_name!r}: {e}')

            return '\n'.join(header) + '\n\n'.join(blocks)
        except RecursionError:
            return source
        except Exception:
            return source

