# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Erebus deobfuscator — consolidated from the original 3-file sub-package.

Provides: Deobfuscator, Result (deobfuscation runner), unwrap (blob extractor).
"""

from ast import NodeTransformer, parse, unparse
from ast import unparse
from functools import reduce
from operator import add
from typing import Any, Dict, List
from typing import Any, Dict, Tuple, Type
from typing import List
import ast
import logging
import string
import zlib


# ── Blob Unwrapper ──────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)


class BlobFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.blobs: List[bytes] = []

    def visit_Constant(self, node: ast.Constant) -> None:
        if type(node.value) is bytes:
            self.blobs.append(node.value)

    def find_blobs(self, node: ast.AST) -> List[bytes]:
        self.visit(node)
        return self.blobs


def unwrap(code: str) -> str:
    """Find the actual code as a blob of obfuscated code"""
    tree = ast.parse(code)
    blobs = BlobFinder().find_blobs(tree)
    blob = reduce(add, blobs)
    logger.info(f"Found blob of length {len(blob)}")
    return zlib.decompress(blob).decode()


# ── AST Transformers ─────────────────────────────────────────────────────────

CONSTANTS = (
    ast.Name,
    ast.Constant,
    ast.Attribute,
    ast.Subscript,
    ast.Tuple,
)

__all__ = (
    "StringSubscriptSimple",
    "GlobalsToVarAccess",
    "InlineConstants",
    "DunderImportRemover",
    "GetattrConstructRemover",
    "BuiltinsAccessRemover",
    "Dehexlify",
    "UselessEval",
    "UselessCompile",
    "ExecTransformer",
    "UselessLambda",
    "LambdaCalls",
    "EmptyIf",
    "RemoveFromBuiltins",
)

constants: Dict[str, Any] = {}
lambdas: List[str] = []


class StringSubscriptSimple(ast.NodeTransformer):
    """Transforms Hyperion specific string slicing into a string literal"""

    def visit_Subscript(self, node: ast.Subscript):
        if (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)) and isinstance(node.slice, ast.Slice):
            code = unparse(node.slice.step)
            if all(s not in code for s in string.ascii_letters):
                s = node.value.value[:: eval(unparse(node.slice.step))]
                return ast.Constant(value=s)
        return super().generic_visit(node)


class GlobalsToVarAccess(ast.NodeTransformer):
    def visit_Subscript(self, node: ast.Subscript) -> Any:
        if (
            (
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id in ("globals", "locals", "vars")
            )
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            return ast.Name(id=node.slice.value, ctx=ast.Load())
        return super().generic_visit(node)


class InlineConstants(ast.NodeTransformer):
    class FindConstants(ast.NodeTransformer):
        def visit_Assign(self, node: ast.Assign) -> Any:
            if isinstance(node.value, CONSTANTS) and isinstance(
                node.targets[0], ast.Name
            ):
                constants[node.targets[0].id] = node.value
                # delete the assignment
                return ast.Module(body=[], type_ignores=[])
            return super().generic_visit(node)

    def visit(self, node: Any) -> Any:
        self.FindConstants().visit(node)
        return super().visit(node)

    def visit_Name(self, node: ast.Name) -> Any:
        """Replace the name with the constant if it's in the constants dict"""
        if node.id in constants:
            return constants[node.id]
        return super().generic_visit(node)


class DunderImportRemover(ast.NodeTransformer):
    """Just transform all __import__ calls to the name of the module being imported"""

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            # node.args[0] should be a Constant(value=str)
            module_name = node.args[0].value if isinstance(node.args[0], ast.Constant) else getattr(node.args[0], 's', '')
            return ast.Name(id=module_name, ctx=ast.Load())
        return super().generic_visit(node)


class GetattrConstructRemover(ast.NodeTransformer):
    """Hyperion has an interesting way of accessing module attributes."""

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name) and node.func.id == "getattr":
            # node.args[1].slice.args[0] should be a Constant
            attr_name = node.args[1].slice.args[0].value if isinstance(node.args[1].slice.args[0], ast.Constant) else node.args[1].slice.args[0].s
            return ast.Attribute(value=node.args[0], attr=attr_name)

        return super().generic_visit(node)


class BuiltinsAccessRemover(ast.NodeTransformer):
    """Instead of accessing builtins, just use the name directly"""

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if isinstance(node.value, ast.Name) and node.value.id == "builtins":
            return ast.Name(id=node.attr, ctx=ast.Load())
        return super().generic_visit(node)


class Dehexlify(ast.NodeTransformer):
    """Transforms a binascii.unhexlify(b'').decode('utf8') into a string"""

    def visit_Call(self, node: ast.Call) -> Any:
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "decode"
            and (
                isinstance(node.func.value, ast.Call)
                and isinstance(node.func.value.func, ast.Attribute)
                and node.func.value.func.attr == "unhexlify"
            )
        ):
            hex_val = node.func.value.args[0].value if isinstance(node.func.value.args[0], ast.Constant) else node.func.value.args[0].s
            return ast.Constant(
                value=bytes.fromhex(hex_val.decode()).decode("utf8")
            )
        return super().generic_visit(node)


class UselessEval(ast.NodeTransformer):
    """Eval can just be replaced with the string"""

    def visit_Call(self, node: ast.Call) -> Any:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "eval"
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
        ):
            return ast.parse(node.args[0].value).body[0].value
        return super().generic_visit(node)


class UselessCompile(ast.NodeTransformer):
    """An call to compile() in Hyperion is usually useless"""

    def visit_Call(self, node: ast.Call) -> Any:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "compile"
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
        ):
            return node.args[0]
        return super().generic_visit(node)


class ExecTransformer(ast.NodeTransformer):
    """Exec can be just transformed into bare code"""

    def visit_Call(self, node: ast.Call) -> Any:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "exec"
            and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
        ):
            try:
                if result := ast.parse(node.args[0].value).body:
                    return result[0]
            except SyntaxError:
                pass
        return super().generic_visit(node)


class UselessLambda(ast.NodeTransformer):
    # x = lambda: y() -> x = y
    def visit_Assign(self, node: ast.Assign) -> Any:
        if (
            isinstance(node.value, ast.Lambda)
            and isinstance(node.value.body, ast.Call)
            and not node.value.body.args  # make sure both call and lambda have no argument
            and not node.value.args
        ):

            return ast.Assign(
                targets=node.targets,
                value=node.value.body.func,
                lineno=node.lineno,
                col_offset=node.col_offset,
            )

        return super().generic_visit(node)


class LambdaSingleArgs(ast.NodeTransformer):
    """Find all lambdas that lambda a: b()"""

    def visit_Assign(self, node: ast.Assign) -> Any:
        if (
            isinstance(node.value, ast.Lambda)
            and isinstance(node.value.body, ast.Call)
            and not node.value.body.args
            and len(node.value.args.args) == 1
        ):
            lambdas.append(node.targets[0].id)
            constants[node.targets[0].id] = node.value.body.func
            return ast.Module(body=[], type_ignores=[])


class LambdaCalls(ast.NodeTransformer):
    """Transforms calls to an assigned lambda into the lambda itself"""

    def visit(self, node: Any) -> Any:
        LambdaSingleArgs().visit(node)
        return super().visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name) and node.func.id in lambdas:

            return ast.Call(
                func=constants[node.func.id],
                args=[],
                keywords=[],
            )

        return super().generic_visit(node)


class EmptyIf(ast.NodeTransformer):
    """Remove useless if statements"""

    def visit_If(self, node: ast.If) -> Any:
        if type(node.test) is ast.Constant and not bool(node.test.value):
            return ast.Module(body=[], type_ignores=[])
        return super().generic_visit(node)


class RemoveFromBuiltins(ast.NodeTransformer):
    """Remove all from builtins import *"""

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.module == "builtins":
            return ast.Module(body=[], type_ignores=[])
        return super().generic_visit(node)


# ── Deobfuscator ─────────────────────────────────────────────────────────────

class Result:
    def __init__(self, code: str, passes: int, variables: Dict[str, Any]) -> None:
        self.code = code
        self.passes = passes
        self.variables = variables

    def add_variables(self) -> None:
        code = "\n".join(
            [f"{name} = {unparse(value)}" for name, value in self.variables.items()]
        )
        self.code = f"{code}\n{self.code}"


class Deobfuscator:
    TRANSFORMERS: Tuple[Type[NodeTransformer], ...] = (
        StringSubscriptSimple,
        GlobalsToVarAccess,
        InlineConstants,
        DunderImportRemover,
        GetattrConstructRemover,
        BuiltinsAccessRemover,
        Dehexlify,
        UselessCompile,
        UselessEval,
        ExecTransformer,
        UselessLambda,
        RemoveFromBuiltins,
    )

    AFTER_TRANSFORMERS: Tuple[Type[NodeTransformer], ...] = (
        LambdaCalls,
        EmptyIf,
    )

    def __init__(self, code: str) -> None:
        self.code = code
        self.tree = parse(code)

    def deobfuscate(self) -> Result:
        passes = 0
        code = self.code
        while True:
            for transformer in self.TRANSFORMERS:
                try:
                    self.tree = transformer().visit(self.tree)
                except Exception as e:
                    transformer_name = transformer.__name__
                    logging.warning(f"Transformer {transformer_name} failed with {e}")
            # If nothing changed after a full pass, we're done
            if (result := unparse(self.tree)) == code:
                for transformer in self.AFTER_TRANSFORMERS:
                    try:
                        self.tree = transformer().visit(self.tree)
                    except Exception as e:
                        transformer_name = transformer.__name__
                        logging.warning(
                            f"Transformer {transformer_name} failed with {e}"
                        )
                    code = unparse(self.tree)
                break
            code = result
            passes += 1
        return Result(code, passes, constants)
