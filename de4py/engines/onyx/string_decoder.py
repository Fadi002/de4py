# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Multi-pass string encoding reversal for Python deobfuscation.
"""

import ast
import base64
import re
import codecs
import bz2
import zlib
import lzma
from typing import Optional


class StringDecoder:

    MAX_PASSES = 10

    def decode_all(self, source: str) -> str:
        try:
            for _ in range(self.MAX_PASSES):
                decoded = self._single_pass(source)
                if decoded == source:
                    break
                source = decoded
        except RecursionError:
            pass  # return whatever we have so far
        except Exception:
            pass  # return whatever we have so far
        return source

    def _single_pass(self, source: str) -> str:
        source = self._resolve_import_aliases_for_decoding(source)
        source = self._unwrap_eval_exec(source)
        source = self._decode_base64_calls(source)
        source = self._decode_base64_dynamic_import(source)
        source = self._decode_base32_calls(source)
        source = self._decode_base85_calls(source)
        source = self._decode_base16_calls(source)
        source = self._decode_hex_escape_strings(source)
        source = self._decode_bytes_fromhex(source)
        source = self._decode_bytearray_literals(source)
        source = self._decode_chr_chains(source)
        source = self._decode_join_chr_list(source)
        source = self._decode_join_chr_map(source)
        source = self._decode_xor_zip(source)           # NEW: ''.join(chr(x^y) for x,y in zip([...],[...]))
        source = self._decode_xor_byte_arrays(source)
        source = self._decode_xor_comprehension(source)
        source = self._decode_zlib(source)
        source = self._decode_lzma(source)
        source = self._decode_bz2(source)
        source = self._decode_rot13(source)
        source = self._decode_unicode_escapes(source)
        source = self._decode_codecs_hex(source)
        source = self._decode_reversed_string(source)
        source = self._decode_int_hex_literal(source)
        source = self._fold_adjacent_string_literals(source)
        source = self._decode_chained_compress_b64(source)
        source = self._fold_repr_and_builtins(source)
        source = self._fold_chr_arithmetic_lists(source)
        source = self._decode_named_string_ops(source)
        source = self._decode_encode_decode_roundtrip(source)
        return source

    # ── Import alias pre-resolution ──────────────────────────────────────────

    def _resolve_import_aliases_for_decoding(self, source: str) -> str:
        """
        Resolve common import aliases so that base64/zlib/codecs decode patterns
        are recognized regardless of the alias used.
        E.g.: import base64 as _b  →  replace _b with base64 in the source.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        alias_map = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname and alias.name in ('base64', 'zlib', 'bz2', 'lzma', 'codecs', 'binascii'):
                        alias_map[alias.asname] = alias.name
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.asname:
                        alias_map[alias.asname] = alias.name

        if not alias_map:
            return source

        # Simple token-level replacement: only replace whole-word matches
        import re as _re
        for old, new in alias_map.items():
            source = _re.sub(r'\b' + _re.escape(old) + r'\b', new, source)
        return source

    # ── eval / exec unwrapping ────────────────────────────────────────────────

    def _unwrap_eval_exec(self, source: str) -> str:
        # Pattern 1: eval/exec("literal string")
        pattern = re.compile(
            r'(?:eval|exec)\s*\(\s*'
            r'(?:'
            r'  (b?"""[\s\S]*?""")'
            r"| (b?'''[\s\S]*?''')"
            r'| (b?"(?:[^"\\]|\\.)*")'
            r"| (b?'(?:[^'\\]|\\.)*')"
            r')\s*\)',
            re.VERBOSE,
        )
        def replace_match(m):
            raw = next(g for g in m.groups() if g is not None)
            try:
                val = ast.literal_eval(raw)
                if isinstance(val, (str, bytes)):
                    return val if isinstance(val, str) else val.decode('utf-8', errors='replace')
            except Exception:
                pass
            return m.group(0)
        source = pattern.sub(replace_match, source)

        # Pattern 2: eval(compile("literal", ...)) or exec(compile("literal", ...))
        pattern2 = re.compile(
            r'(?:eval|exec)\s*\(\s*compile\s*\(\s*'
            r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
            r'\s*,\s*[^)]+\)\s*\)'
        )
        def replace_compile(m):
            try:
                val = ast.literal_eval(m.group(1))
                if isinstance(val, str):
                    return val
            except Exception:
                pass
            return m.group(0)
        source = pattern2.sub(replace_compile, source)
        return source

    # ── Base64 ───────────────────────────────────────────────────────────────

    def _decode_base64_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b64decode\s*\(\s*b?(["\'])([A-Za-z0-9+/=\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def decode_b64(m):
            try:
                raw = m.group(2).replace('\n','').replace(' ','')
                return repr(base64.b64decode(raw).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(decode_b64, source)

    def _decode_base64_dynamic_import(self, source: str) -> str:
        pattern = re.compile(
            r'__import__\s*\(\s*[\'"]base64[\'"]\s*\)'
            r'\.b64decode\s*\(\s*b?["\']([A-Za-z0-9+/=]+)["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def decode_dyn(m):
            try:
                return repr(base64.b64decode(m.group(1)).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(decode_dyn, source)

    def _decode_base32_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b32decode\s*\(\s*b?(["\'])([A-Z2-7=\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d(m):
            try:
                return repr(base64.b32decode(m.group(2).replace('\n','').replace(' ','')).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_base85_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b85decode\s*\(\s*b?(["\'])([!-u\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d(m):
            try:
                return repr(base64.b85decode(m.group(2).replace('\n','').replace(' ','').encode()).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_base16_calls(self, source: str) -> str:
        pattern = re.compile(
            r'base64\.b16decode\s*\(\s*b?(["\'])([A-F0-9\s]+)\1\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d(m):
            try:
                return repr(base64.b16decode(m.group(2).replace('\n','').replace(' ','')).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    # ── Hex / bytes ───────────────────────────────────────────────────────────

    def _decode_hex_escape_strings(self, source: str) -> str:
        """Convert '\\x68\\x65' inside STRING literals to ASCII. Skips bytes literals."""
        # (?<!b) prevents matching inside b'\\x..' byte literals
        pattern = re.compile(
            r'(?<!\\)(?<!b)"((?:\\x[0-9a-fA-F]{2})+)"'
            r'|'
            r"(?<!\\)(?<!b)'((?:\\x[0-9a-fA-F]{2})+)'"
        )

        def decode_hex(m: re.Match) -> str:
            content = m.group(1) or m.group(2)
            try:
                hex_bytes = bytes.fromhex(content.replace('\\x', ''))
                decoded = hex_bytes.decode('utf-8', errors='replace')
                # Only inline if result is clean ASCII — never put non-ASCII into source
                if '\ufffd' not in decoded and decoded.isascii():
                    return repr(decoded)
            except Exception:
                pass
            return m.group(0)

        return pattern.sub(decode_hex, source)

    def _decode_bytes_fromhex(self, source: str) -> str:
        p1 = re.compile(
            r'bytes\.fromhex\s*\(\s*["\']([0-9a-fA-F\s]+)["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d1(m):
            try:
                return repr(bytes.fromhex(m.group(1).replace(' ','').replace('\n','')).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        source = p1.sub(d1, source)
        p2 = re.compile(
            r'codecs\.decode\s*\(\s*b?["\']([0-9a-fA-F]+)["\']\s*,\s*["\']hex(?:_codec)?["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d2(m):
            try:
                return repr(bytes.fromhex(m.group(1)).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return p2.sub(d2, source)

    def _decode_bytearray_literals(self, source: str) -> str:
        p1 = re.compile(r'bytearray\s*\(\s*(b"[^"]*"|b\'[^\']*\')\s*\)(?:\.decode\s*\([^)]*\))?')
        def d1(m):
            try:
                return repr(ast.literal_eval(m.group(1)).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        source = p1.sub(d1, source)
        p2 = re.compile(r'bytearray\s*\(\s*\[([0-9,\s]+)\]\s*\)(?:\.decode\s*\([^)]*\))?')
        def d2(m):
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                if all(32 <= n <= 126 or n in (9,10,13) for n in nums):
                    return repr(bytearray(nums).decode('utf-8', errors='replace'))
            except Exception:
                pass
            return m.group(0)
        return p2.sub(d2, source)

    # ── chr / join patterns ───────────────────────────────────────────────────

    def _decode_chr_chains(self, source: str) -> str:
        pattern = re.compile(r'(?:chr\s*\(\s*\d{1,3}\s*\)\s*\+\s*)*chr\s*\(\s*\d{1,3}\s*\)')
        def d(m):
            try:
                result = eval(m.group(0), {'__builtins__':{}}, {'chr':chr})
                if isinstance(result, str) and result.isprintable():
                    return repr(result)
            except Exception:
                pass
            return m.group(0)
        return pattern.sub(d, source)

    def _decode_join_chr_list(self, source: str) -> str:
        p1 = re.compile(r'["\']["\']\.join\s*\(\s*\[?\s*chr\s*\(\s*\w+\s*\)\s+for\s+\w+\s+in\s+\[([0-9,\s]+)\]\s*\]?\s*\)')
        def d1(m):
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                r = ''.join(chr(n) for n in nums)
                return repr(r) if r.isprintable() else m.group(0)
            except Exception:
                return m.group(0)
        source = p1.sub(d1, source)
        p2 = re.compile(r'["\']["\']\.join\s*\(\s*map\s*\(\s*chr\s*,\s*\[([0-9,\s]+)\]\s*\)\s*\)')
        def d2(m):
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                r = ''.join(chr(n) for n in nums)
                return repr(r) if r.isprintable() else m.group(0)
            except Exception:
                return m.group(0)
        source = p2.sub(d2, source)
        p3 = re.compile(r'["\']["\']\.join\s*\(\s*\[\s*((?:chr\s*\(\s*\d{1,3}\s*\)\s*,?\s*)+)\]\s*\)')
        def d3(m):
            try:
                nums = [int(x) for x in re.findall(r'chr\s*\(\s*(\d{1,3})\s*\)', m.group(1))]
                r = ''.join(chr(n) for n in nums)
                return repr(r) if r.isprintable() else m.group(0)
            except Exception:
                return m.group(0)
        return p3.sub(d3, source)

    def _decode_join_chr_map(self, source: str) -> str:
        pattern = re.compile(
            r'["\']["\']\.join\s*\(\s*map\s*\(\s*chr\s*,\s*range\s*\(\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d+))?\s*\)\s*\)\s*\)'
        )
        def d(m):
            try:
                start, stop = int(m.group(1)), int(m.group(2))
                step = int(m.group(3)) if m.group(3) else 1
                r = ''.join(chr(n) for n in range(start, stop, step))
                return repr(r) if r.isprintable() else m.group(0)
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    # ── NEW: XOR zip decode ───────────────────────────────────────────────────

    def _decode_xor_zip(self, source: str) -> str:
        """
        Decode patterns like:
          ''.join(chr(x ^ y) for x, y in zip([0xde, 0xf9, ...], [0x8d] * 11))
          ''.join(chr(x ^ y) for x, y in zip([N, ...], [K] * M))
          ''.join(chr(x ^ K) for x in [N, N, N])
        """
        # Pattern 1: zip([...], [K] * M) or zip([...], [K, K, K, ...])
        p1 = re.compile(
            r"[\"'][\"']\.join\s*\(\s*(?:chr\s*\(\s*\w+\s*\^\s*\w+\s*\)\s*for\s+\w+\s*,\s*\w+\s+in|"
            r"\(chr\s*\(\s*\w+\s*\^\s*\w+\s*\)\s*for\s+\w+\s*,\s*\w+\s+in)\s+zip\s*\("
            r"\s*\[([0-9,\s0xXa-fA-F]+)\]\s*,\s*"
            r"\[([0-9,\s0xXa-fA-F]+)\]\s*(?:\*\s*\d+)?\s*\)\s*\)\s*\)"
        )

        def d1(m):
            try:
                def parse_list(s):
                    # Handle hex literals like 0xde
                    return [int(x.strip(), 0) for x in s.split(',') if x.strip()]
                arr1 = parse_list(m.group(1))
                arr2_raw = m.group(2)
                arr2 = parse_list(arr2_raw)
                # If arr2 has one element, it's a repeated key
                if len(arr2) == 1:
                    key = arr2[0]
                    result = ''.join(chr(x ^ key) for x in arr1)
                else:
                    result = ''.join(chr(x ^ y) for x, y in zip(arr1, arr2))
                return repr(result) if result.isprintable() else m.group(0)
            except Exception:
                return m.group(0)

        source = p1.sub(d1, source)

        # Pattern 2: Use safe eval for remaining zip patterns
        p2 = re.compile(
            r"[\"'][\"']\.join\s*\([^)]{0,500}\bzip\b[^)]{0,300}\)\s*\)"
        )

        def d2(m):
            expr = m.group(0)
            try:
                result = eval(expr, {'__builtins__': {'chr': chr, 'zip': zip, 'range': range}})
                if isinstance(result, str) and result.isprintable() and len(result) > 0:
                    return repr(result)
            except Exception:
                pass
            return m.group(0)

        source = p2.sub(d2, source)
        return source

    # ── XOR byte arrays ───────────────────────────────────────────────────────

    def _decode_xor_byte_arrays(self, source: str) -> str:
        p1 = re.compile(
            r'bytes\s*\(\s*\[\s*\w+\s*\^\s*(\d+)\s+for\s+\w+\s+in\s+\[([0-9,\s]+)\]\s*\]\s*\)'
        )
        def d1(m):
            try:
                key = int(m.group(1))
                nums = [int(x.strip()) for x in m.group(2).split(',') if x.strip()]
                return repr(bytes([n^key for n in nums]).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        source = p1.sub(d1, source)
        p2 = re.compile(r'bytes\s*\(\s*\[([0-9,\s]+)\]\s*\)')
        def d2(m):
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',') if x.strip()]
                if all(32<=n<=126 or n in (9,10,13) for n in nums):
                    return repr(bytes(nums).decode('utf-8', errors='replace'))
            except Exception:
                pass
            return m.group(0)
        return p2.sub(d2, source)

    def _decode_xor_comprehension(self, source: str) -> str:
        pattern = re.compile(
            r'bytes\s*\(\s*\[?\s*\w+\s*\^\s*(\d+)\s+for\s+\w+\s+in\s+(b"[^"]*"|b\'[^\']*\')\s*\]?\s*\)'
        )
        def d(m):
            try:
                key = int(m.group(1))
                raw = ast.literal_eval(m.group(2))
                return repr(bytes(b^key for b in raw).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    # ── Compression ──────────────────────────────────────────────────────────

    def _decode_zlib(self, source): return self._decode_compression(source,'zlib',zlib.decompress)
    def _decode_lzma(self, source): return self._decode_compression(source,'lzma',lzma.decompress)
    def _decode_bz2(self,  source): return self._decode_compression(source,'bz2', bz2.decompress)

    def _decode_compression(self, source, name, fn):
        pattern = re.compile(
            rf'{re.escape(name)}\.decompress\s*\(\s*(b"[^"]*"|b\'[^\']*\')\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d(m):
            try:
                return repr(fn(ast.literal_eval(m.group(1))).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    # ── Text transforms ───────────────────────────────────────────────────────

    def _decode_rot13(self, source: str) -> str:
        pattern = re.compile(r'codecs\.decode\s*\(\s*(["\'][^"\']+["\'])\s*,\s*["\']rot.?13["\']\s*\)')
        def d(m):
            try:
                return repr(codecs.decode(ast.literal_eval(m.group(1)), 'rot_13'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_unicode_escapes(self, source: str) -> str:
        pattern = re.compile(r'"((?:\\u[0-9a-fA-F]{4})+)"|\'((?:\\u[0-9a-fA-F]{4})+)\'')
        def d(m):
            try:
                return repr((m.group(1) or m.group(2)).encode('utf-8').decode('unicode_escape'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_codecs_hex(self, source: str) -> str:
        pattern = re.compile(
            r'codecs\.decode\s*\(\s*(b["\'][0-9a-fA-F]+["\'])\s*,\s*["\']hex_codec["\']\s*\)'
            r'(?:\.decode\s*\([^)]*\))?'
        )
        def d(m):
            try:
                raw = ast.literal_eval(m.group(1))
                return repr(bytes.fromhex(raw.decode('ascii')).decode('utf-8', errors='replace'))
            except Exception:
                return m.group(0)
        return pattern.sub(d, source)

    def _decode_reversed_string(self, source: str) -> str:
        p1 = re.compile(r'["\']["\']\.join\s*\(\s*reversed\s*\(\s*(["\'][^"\']+["\'])\s*\)\s*\)')
        def d1(m):
            try:
                return repr(ast.literal_eval(m.group(1))[::-1])
            except Exception:
                return m.group(0)
        source = p1.sub(d1, source)
        p2 = re.compile(r'(["\'][^"\']{2,}["\'])\[::-1\]')
        def d2(m):
            try:
                return repr(ast.literal_eval(m.group(1))[::-1])
            except Exception:
                return m.group(0)
        return p2.sub(d2, source)

    def _decode_int_hex_literal(self, source: str) -> str:
        pattern = re.compile(r'\bint\s*\(\s*(["\'][0-9a-fA-FxXbBoO]+["\'])\s*,\s*(\d+)\s*\)')
        def d(m):
            try:
                s = ast.literal_eval(m.group(1))
                base = int(m.group(2))
                if base in (2,8,10,16):
                    return str(int(s, base))
            except Exception:
                pass
            return m.group(0)
        return pattern.sub(d, source)

    def _decode_chained_compress_b64(self, source: str) -> str:
        """
        Handle chained patterns like:
          exec(zlib.decompress(base64.b64decode(b"...")))
          exec(zlib.decompress(base64.b64decode(payload)))
        where payload is assigned a bytes literal nearby.
        Decodes the payload and replaces the exec with the decoded source.
        """
        import zlib as _zlib, base64 as _b64
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        # Collect known bytes variable assignments
        bytes_vars: dict = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, bytes)):
                bytes_vars[node.targets[0].id] = node.value.value

        def try_get_bytes(arg_node) -> bytes:
            """Extract bytes from a node: literal or known variable."""
            if isinstance(arg_node, ast.Constant) and isinstance(arg_node.value, bytes):
                return arg_node.value
            if isinstance(arg_node, ast.Name) and arg_node.id in bytes_vars:
                return bytes_vars[arg_node.id]
            return None

        def try_decode_chain(arg_node):
            """Try to decode a possibly chained base64+compress call to a string."""
            # zlib.decompress(inner) or bz2.decompress(inner) or lzma.decompress(inner)
            if (isinstance(arg_node, ast.Call)
                    and isinstance(arg_node.func, ast.Attribute)
                    and arg_node.func.attr == 'decompress'
                    and len(arg_node.args) == 1):
                inner = arg_node.args[0]
                # The inner might be base64.b64decode(...)
                inner_bytes = try_decode_inner(inner)
                if inner_bytes is not None:
                    mod_name = None
                    if isinstance(arg_node.func.value, ast.Name):
                        mod_name = arg_node.func.value.id
                    try:
                        if mod_name in ('zlib', None):
                            return _zlib.decompress(inner_bytes).decode('utf-8', errors='replace')
                        elif mod_name == 'bz2':
                            import bz2 as _bz2
                            return _bz2.decompress(inner_bytes).decode('utf-8', errors='replace')
                    except Exception:
                        pass
            return None

        def try_decode_inner(arg_node) -> bytes:
            """Try to get bytes from a b64decode call or literal."""
            raw = try_get_bytes(arg_node)
            if raw is not None:
                return raw
            # base64.b64decode(...)
            if (isinstance(arg_node, ast.Call)
                    and isinstance(arg_node.func, ast.Attribute)
                    and arg_node.func.attr == 'b64decode'
                    and len(arg_node.args) == 1):
                inner = try_get_bytes(arg_node.args[0])
                if inner is not None:
                    try:
                        return _b64.b64decode(inner)
                    except Exception:
                        pass
            return None

        class ChainedDecoder(ast.NodeTransformer):
            def visit_Expr(self, node):
                self.generic_visit(node)
                # exec(chain) or eval(chain)
                if (isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)
                        and node.value.func.id in ('exec', 'eval')
                        and len(node.value.args) == 1):
                    decoded = try_decode_chain(node.value.args[0])
                    if decoded and decoded.strip():
                        # Replace exec(chain) with the decoded source text
                        return ast.parse(decoded).body if decoded.strip() else node
                return node

        try:
            new_tree = ChainedDecoder().visit(tree)
            ast.fix_missing_locations(new_tree)
            return ast.unparse(new_tree)
        except Exception:
            return source

    def _fold_repr_and_builtins(self, source: str) -> str:
        """
        Fold:
          repr("literal")        -> "\'literal\'"
          str(constant)          -> "string_of_constant"
          len("literal")         -> N
          bool(0) / bool(1)      -> False / True
        These are pure-constant calls safe to evaluate statically.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        SAFE_ZERO_ENV = {
            '__builtins__': {},
            'repr': repr, 'str': str, 'len': len, 'bool': bool,
            'int': int, 'float': float, 'abs': abs, 'hex': hex,
            'oct': oct, 'bin': bin, 'chr': chr, 'ord': ord,
        }
        FOLDABLE_FUNCS = {'repr', 'str', 'len', 'bool', 'int', 'float',
                          'abs', 'hex', 'oct', 'bin', 'chr', 'ord'}

        class ReprFolder(ast.NodeTransformer):
            def visit_Call(self, node):
                self.generic_visit(node)
                if (isinstance(node.func, ast.Name)
                        and node.func.id in FOLDABLE_FUNCS
                        and len(node.args) == 1
                        and not node.keywords):
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant):
                        try:
                            result = eval(
                                compile(ast.Expression(body=node), '<fold>', 'eval'),
                                SAFE_ZERO_ENV
                            )
                            if isinstance(result, (str, int, float, bool, type(None))):
                                return ast.Constant(value=result)
                        except Exception:
                            pass
                return node

        tree = ReprFolder().visit(tree)
        ast.fix_missing_locations(tree)
        try:
            return ast.unparse(tree)
        except Exception:
            return source

    def _fold_chr_arithmetic_lists(self, source: str) -> str:
        """
        Fold chr/int arithmetic inside list literals so that:
          [0x51 ^ 17, 0x60 ^ 4, ...]  ->  [64, 92, ...]  (already done by ASTCleaner)
          ''.join(chr(x) for x in [64, 92, ...])  ->  '@\\'...  (done by FlowDeobf)
        This pass handles the case where constants haven't been folded yet by
        evaluating arithmetic expressions inside list/tuple literals.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        SAFE_OPS = (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod,
                    ast.BitXor, ast.BitAnd, ast.BitOr, ast.LShift, ast.RShift)

        class ArithFolder(ast.NodeTransformer):
            def visit_BinOp(self, node):
                self.generic_visit(node)
                if (isinstance(node.op, SAFE_OPS)
                        and isinstance(node.left, ast.Constant)
                        and isinstance(node.right, ast.Constant)
                        and isinstance(node.left.value, (int, float))
                        and isinstance(node.right.value, (int, float))):
                    try:
                        result = eval(compile(ast.Expression(body=node), '<arith>', 'eval'),
                                      {'__builtins__': {}})
                        return ast.Constant(value=result)
                    except Exception:
                        pass
                return node

        tree = ArithFolder().visit(tree)
        ast.fix_missing_locations(tree)
        try:
            return ast.unparse(tree)
        except Exception:
            return source

    def _decode_named_string_ops(self, source: str) -> str:
        """Fold simple string method calls on literals using AST: 'hi'.upper() -> 'HI'."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        SAFE_METHODS = {'upper', 'lower', 'strip', 'lstrip', 'rstrip', 'title', 'capitalize', 'swapcase'}

        class StringMethodFolder(ast.NodeTransformer):
            def visit_Call(self, node):
                self.generic_visit(node)
                if (isinstance(node.func, ast.Attribute)
                        and node.func.attr in SAFE_METHODS
                        and isinstance(node.func.value, ast.Constant)
                        and isinstance(node.func.value.value, str)
                        and not node.args and not node.keywords):
                    try:
                        return ast.Constant(value=getattr(node.func.value.value, node.func.attr)())
                    except Exception:
                        pass
                if (isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'replace'
                        and isinstance(node.func.value, ast.Constant)
                        and isinstance(node.func.value.value, str)
                        and len(node.args) == 2
                        and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args)
                        and not node.keywords):
                    try:
                        return ast.Constant(value=node.func.value.value.replace(node.args[0].value, node.args[1].value))
                    except Exception:
                        pass
                return node

        tree = StringMethodFolder().visit(tree)
        ast.fix_missing_locations(tree)
        try:
            return ast.unparse(tree)
        except Exception:
            return source


    def _fold_adjacent_string_literals(self, source: str) -> str:
        """
        Use AST to fold only genuinely-constant adjacent BinOp Add of string literals.
        Avoids regex that incorrectly merges strings across + operators.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        class ImplicitStrFolder(ast.NodeTransformer):
            def visit_BinOp(self, node):
                self.generic_visit(node)
                if (isinstance(node.op, ast.Add)
                        and isinstance(node.left, ast.Constant)
                        and isinstance(node.left.value, str)
                        and isinstance(node.right, ast.Constant)
                        and isinstance(node.right.value, str)):
                    return ast.Constant(value=node.left.value + node.right.value)
                return node

        changed = True
        while changed:
            before = ast.unparse(tree)
            tree = ImplicitStrFolder().visit(tree)
            ast.fix_missing_locations(tree)
            try:
                if ast.unparse(tree) == before:
                    changed = False
            except Exception:
                break

        try:
            return ast.unparse(tree)
        except Exception:
            return source


    def _decode_encode_decode_roundtrip(self, source: str) -> str:
        pattern = re.compile(
            r'(["\'][^"\'\\]*(?:\\.[^"\'\\]*)*["\'])'
            r'\.encode\s*\([^)]*\)'
            r'\.decode\s*\([^)]*\)'
        )
        def d(m):
            try:
                s = ast.literal_eval(m.group(1))
                if isinstance(s, str):
                    return repr(s)
            except Exception:
                pass
            return m.group(0)
        return pattern.sub(d, source)
