# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Pipeline-facing adapter for the VM devirtualization subsystem.

The analysis lives in ``de4py.engines.onyx.vm``; this module keeps the small
surface the pipeline uses (``has_vm_class`` / ``deobfuscate``) and is responsible
for deciding whether a lift is good enough to replace the input.
"""

import ast
import logging
from typing import List, Optional, Tuple

from de4py.engines.onyx.safe_eval import safe_eval
from de4py.engines.onyx.vm import (
    PayloadExtractor,
    RegisterPayloadExtractor,
    VMDiscovery,
    VMModel,
    VOp,
    build_table_model,
    find_dispatch_loop,
    find_handler_table,
    lift_program,
    lift_register_program,
)
from de4py.engines.onyx.vm.register_lifter import _init_args
from de4py.engines.onyx.vm.table_dispatch import constructor_fields

logger = logging.getLogger(__name__)

#: Below this share of understood opcodes the lift is reported but not trusted
#: to replace the original source.
MIN_COVERAGE = 0.5


class VMLifter:

    def has_vm_class(self, source: str) -> bool:
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError, RecursionError):
            return False
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            # A switch dispatcher is checked first so the existing path is
            # untouched; a handler-table dispatcher has no branch to find.
            if find_dispatch_loop(node) or find_handler_table(node):
                return True
        return False

    def analyze(self, source: str):
        """Return (models, tree) without emitting anything. Used by diagnostics."""
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError, RecursionError):
            return [], None
        return VMDiscovery().discover(tree), tree

    def deobfuscate(self, source: str) -> str:
        try:
            models, tree = self.analyze(source)
        except RecursionError:
            return source
        if tree is None:
            return source

        blocks: List[str] = []
        header: List[str] = []
        lifted_any = False

        for rendered in self._lift_tables(tree):
            header.extend(rendered[0])
            blocks.append(rendered[1])
            lifted_any = True

        for model in models:
            extractor = PayloadExtractor(model)
            payloads = extractor.find_payloads(tree)
            if not payloads:
                continue

            header.extend(self._describe(model))

            for payload, name, arity in payloads:
                program = extractor.build(payload, name, arity)
                if program is None:
                    blocks.append(f"# {name}: payload could not be decoded")
                    continue
                try:
                    blocks.append(lift_program(program, model))
                    lifted_any = True
                except RecursionError:
                    blocks.append(f"# {name}: control flow too deep to structure")
                except Exception as exc:            # keep partial results usable
                    blocks.append(f"# {name}: lift failed ({type(exc).__name__}: {exc})")

        if not lifted_any:
            return source

        entry = self._entry_calls(tree, models)
        rendered = "\n".join(header + [""] + ["\n\n".join(blocks)] + entry)
        try:
            ast.parse(rendered)
        except SyntaxError as exc:
            logger.warning("[VMLifter] emitted source did not parse: %s", exc)
            return "\n".join(header + ["# lift produced unparsable output; "
                                       "original preserved below", ""]) + "\n" + source
        return rendered

    def _lift_tables(self, tree: ast.Module) -> List[Tuple[List[str], str]]:
        """
        Devirtualize every handler-table interpreter in the module.

        A table dispatcher indexes a tuple of lambdas with the opcode, so the
        opcode's meaning is its position rather than a branch. Everything the
        emitter needs — rotation, width, register file, pools — is recovered
        from the sample itself.
        """
        out: List[Tuple[List[str], str]] = []
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            if find_dispatch_loop(cls):
                continue
            try:
                built = build_table_model(cls)
            except Exception as exc:
                logger.debug("[VMLifter] table discovery failed: %s", exc)
                continue
            if built is None:
                continue
            model, _table, site = built
            if model.coverage() < MIN_COVERAGE:
                continue

            payload, params = self._table_payload(tree, cls)
            if payload is None:
                continue

            extractor = RegisterPayloadExtractor(
                model, cls, constructor_fields(cls), site.code_attr,
                self._nested_field(params, payload),
            )
            try:
                program = extractor.build(payload, f"{cls.name}_main")
            except Exception as exc:
                logger.debug("[VMLifter] table payload build failed: %s", exc)
                continue
            if program is None or not program.instructions:
                continue

            try:
                out.append((self._describe(model), lift_register_program(program, model)))
            except RecursionError:
                continue
            except Exception as exc:
                logger.debug("[VMLifter] table lift failed: %s", exc)
        return out

    def _table_payload(self, tree: ast.Module,
                       cls: ast.ClassDef) -> Tuple[Optional[List], List[str]]:
        """Fold the arguments the interpreter is constructed with."""
        params = [a.arg for a in _init_args(cls)]
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == cls.name and node.args):
                continue
            first = node.args[0]
            elements = (first.value.elts
                        if isinstance(first, ast.Starred)
                        and isinstance(first.value, (ast.Tuple, ast.List))
                        else node.args)
            values = []
            for element in elements:
                ok, value = safe_eval(element, {})
                if not ok:
                    values = []
                    break
                values.append(value)
            if values:
                return values, params
        return None, params

    def _nested_field(self, params: List[str], payload: List) -> Optional[str]:
        """
        Payload slot holding sub-programs.

        A nested table is a sequence whose entries are themselves payload-shaped
        sequences, which distinguishes it from a pool of scalars.
        """
        for name, value in zip(params, payload):
            if (isinstance(value, (list, tuple)) and value
                    and all(isinstance(v, (list, tuple)) for v in value)):
                return name
        return None

    def _describe(self, model: VMModel) -> List[str]:
        """A short report so an analyst can audit what was inferred."""
        known = sorted(
            (number, spec) for number, spec in model.opcodes.items()
            if spec.op is not VOp.UNKNOWN
        )
        unknown = sorted(model.by_op(VOp.UNKNOWN))
        lines = [
            "# " + "=" * 66,
            f"# Devirtualized: {model.class_name}",
            f"# instruction width {model.instruction_width} bytes, "
            f"{model.operand_count} operand(s), "
            f"{len(model.opcodes)} opcodes, {model.coverage():.0%} recovered",
            "# " + "=" * 66,
            "# opcode map:",
        ]
        for number, spec in known:
            detail = spec.symbol or spec.operand_role
            suffix = f" [{detail}]" if detail and detail != "none" else ""
            lines.append(f"#   {number:>3} -> {spec.op.value}{suffix}")
        if unknown:
            lines.append(f"#   unrecovered opcodes: {unknown}")
        return lines

    def _entry_calls(self, tree: ast.Module, models: List[VMModel]) -> List[str]:
        """Preserve the call that starts the program, e.g. a trailing ``vm()``."""
        class_names = {m.class_name for m in models}
        out: List[str] = []
        for node in tree.body:
            if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
                continue
            call = node.value
            if isinstance(call.func, ast.Name) and call.func.id not in class_names:
                out.append(f"{call.func.id}()")
        return ["", *out] if out else []
