# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Structural decoder registry.

Each decoder detects an encoding pattern in the AST and evaluates it.
Unlike text-level regex, structural detectors match exact call shapes,
making them immune to false positives on long lines."""

import ast
import base64
import binascii
import codecs
import zlib


class DecodeMatch:

    __slots__ = ("node", "value", "decoder_name")

    def __init__(self, node, value, decoder_name):
        self.node = node
        self.value = value
        self.decoder_name = decoder_name


class Decoder:

    name = "base"

    def detect(self, node: ast.AST) -> bool:
        raise NotImplementedError

    def decode(self, node: ast.AST) -> str:
        raise NotImplementedError


class B64Decode(Decoder):

    name = "b64"

    def detect(self, node):
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("b64decode", "b85decode")
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, (str, bytes)))

    def decode(self, node):
        raw = node.args[0].value
        if isinstance(raw, str):
            raw = raw.encode()
        fn = node.func.attr
        fn_map = {"b64decode": base64.b64decode, "b85decode": base64.b85decode}
        decoded = fn_map[fn](raw)
        return decoded.decode("utf-8", errors="replace")


class HexDecode(Decoder):

    name = "hex"

    def detect(self, node):
        if isinstance(node, ast.Call) \
                and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "fromhex" \
                and isinstance(node.func.value, ast.Name) \
                and node.func.value.id == "bytes" \
                and len(node.args) == 1 \
                and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            return True
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "unhexlify"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant))

    def decode(self, node):
        raw = node.args[0].value
        if isinstance(raw, str):
            raw = raw.encode()
        try:
            return binascii.unhexlify(raw).decode("utf-8", errors="replace")
        except (binascii.Error, ValueError):
            return None


class ZlibDecompress(Decoder):

    name = "zlib"

    def detect(self, node):
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("decompress", "decompressdata")
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in ("zlib", "bz2", "lzma")
                and len(node.args) >= 1
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, bytes))

    def decode(self, node):
        mod_name = node.func.value.id
        data = node.args[0].value
        import bz2 as _bz2
        import lzma as _lzma
        fns = {"zlib": zlib.decompress, "bz2": _bz2.decompress,
               "lzma": _lzma.decompress}
        result = fns[mod_name](data)
        if isinstance(result, bytes):
            return result.decode("utf-8", errors="replace")
        return result


class ChrChainDecode(Decoder):

    name = "chr_chain"

    def detect(self, node):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
            return False
        return self._count_chr(node) >= 2

    @staticmethod
    def _is_chr_const(n):
        return (isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "chr"
                and len(n.args) == 1
                and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, int))

    def _count_chr(self, node):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self._count_chr(node.left) + self._count_chr(node.right)
        if self._is_chr_const(node):
            return 1
        return 0

    def _collect_chars(self, node, chars):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            self._collect_chars(node.left, chars)
            self._collect_chars(node.right, chars)
        elif self._is_chr_const(node):
            chars.append(chr(node.args[0].value))

    def decode(self, node):
        chars = []
        self._collect_chars(node, chars)
        return "".join(chars)


_REGISTRY: list = [B64Decode(), HexDecode(), ZlibDecompress(),
                   ChrChainDecode()]


def register(decoder: Decoder):
    _REGISTRY.append(decoder)


def scan_tree(tree: ast.Module) -> list:
    """Scan an AST tree for decodable patterns. Returns DecodeMatch list."""
    matches = []
    for node in ast.walk(tree):
        for dec in _REGISTRY:
            try:
                if dec.detect(node):
                    result = dec.decode(node)
                    if result is not None:
                        matches.append(
                            DecodeMatch(node, result, dec.name))
                        break
            except Exception:
                continue
    return matches
