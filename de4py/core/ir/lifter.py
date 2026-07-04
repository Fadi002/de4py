# de4py - Onyx Engine
# Python AST to IR Lifter

import ast
from typing import List, Union, Optional
from .graph import CFG, BasicBlock
from .instructions import (
    Assign, BinaryOp, UnaryOp, Compare, BoolOp, Call,
    GetItem, SetItem, BuildSlice, BuildTuple, BuildList, OpaqueExpr,
    Jump, Branch, ForIter, Return, Raise, Assert,
    Import, ImportFrom, LoadAttr, StoreAttr, FuncDef, Instruction
)
from .values import Constant, Variable, Temporary

_BINOP_MAP = {
    ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
    ast.FloorDiv: "//", ast.Mod: "%", ast.Pow: "**",
    ast.BitXor: "^", ast.BitAnd: "&", ast.BitOr: "|",
    ast.LShift: "<<", ast.RShift: ">>", ast.MatMult: "@",
}
_UNOP_MAP = {ast.USub: "-", ast.UAdd: "+", ast.Not: "not", ast.Invert: "~"}
_CMP_MAP = {
    ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
    ast.Gt: ">", ast.GtE: ">=", ast.Is: "is", ast.IsNot: "is not",
    ast.In: "in", ast.NotIn: "not in",
}


class IR_Lifter(ast.NodeVisitor):
    def __init__(self):
        self.cfg = CFG()
        self.current_block = self.cfg.create_block()
        self._temp_count = 0
        self._loop_stack: List[dict] = []

    def _get_temp(self) -> Temporary:
        t = Temporary(self._temp_count)
        self._temp_count += 1
        return t

    def lift(self, tree: ast.AST) -> CFG:
        self.visit(tree)
        return self.cfg

    def _emit(self, instr: Instruction):
        self.current_block.add_instruction(instr)

    def _is_terminated(self) -> bool:
        return any(isinstance(i, (Jump, Return, Raise))
                   for i in self.current_block.instructions)

    # ── Expressions ────────────────────────────────────────────────

    def visit_Constant(self, node: ast.Constant):
        return Constant(node.value)

    def visit_Name(self, node: ast.Name):
        return Variable(node.id)

    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        op = _BINOP_MAP.get(type(node.op), "?")
        t = self._get_temp()
        self._emit(BinaryOp(t, left, op, right))
        return t

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operand = self.visit(node.operand)
        op = _UNOP_MAP.get(type(node.op), "?")
        t = self._get_temp()
        self._emit(UnaryOp(t, op, operand))
        return t

    def visit_Compare(self, node: ast.Compare):
        left = self.visit(node.left)
        # Handle chained comparisons by ANDing sub-comparisons
        results = []
        prev = left
        for op_node, comp in zip(node.ops, node.comparators):
            right = self.visit(comp)
            op = _CMP_MAP.get(type(op_node), "?")
            t = self._get_temp()
            self._emit(Compare(t, prev, op, right))
            results.append(t)
            prev = right
        if len(results) == 1:
            return results[0]
        t = self._get_temp()
        self._emit(BoolOp(t, "and", results))
        return t

    def visit_BoolOp(self, node: ast.BoolOp):
        op = "and" if isinstance(node.op, ast.And) else "or"
        values = [self.visit(v) for v in node.values]
        t = self._get_temp()
        self._emit(BoolOp(t, op, values))
        return t

    def visit_Call(self, node: ast.Call):
        func = self.visit(node.func)
        args = [self.visit(a) for a in node.args]
        kwargs = {kw.arg: self.visit(kw.value) for kw in node.keywords if kw.arg}
        t = self._get_temp()
        self._emit(Call(t, func, args, kwargs))
        return t

    def visit_Attribute(self, node: ast.Attribute):
        obj = self.visit(node.value)
        t = self._get_temp()
        self._emit(LoadAttr(t, obj, node.attr))
        return t

    def visit_Subscript(self, node: ast.Subscript):
        obj = self.visit(node.value)
        if isinstance(node.slice, ast.Slice):
            lo = self.visit(node.slice.lower) if node.slice.lower else Constant(None)
            hi = self.visit(node.slice.upper) if node.slice.upper else Constant(None)
            st = self.visit(node.slice.step) if node.slice.step else Constant(None)
            key = self._get_temp()
            self._emit(BuildSlice(key, lo, hi, st))
        else:
            key = self.visit(node.slice)
        t = self._get_temp()
        self._emit(GetItem(t, obj, key))
        return t

    def visit_Tuple(self, node: ast.Tuple):
        if isinstance(node.ctx, ast.Store):
            return node  # handled by _assign_target
        elts = [self.visit(e) for e in node.elts]
        t = self._get_temp()
        self._emit(BuildTuple(t, elts))
        return t

    def visit_List(self, node: ast.List):
        if isinstance(node.ctx, ast.Store):
            return node
        elts = [self.visit(e) for e in node.elts]
        t = self._get_temp()
        self._emit(BuildList(t, elts))
        return t

    def visit_ListComp(self, node: ast.ListComp):
        # Emit as opaque; constant_eval pass will have already simplified if possible
        src = ast.unparse(node)
        t = self._get_temp()
        self._emit(OpaqueExpr(t, src))
        return t

    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        src = ast.unparse(node)
        t = self._get_temp()
        self._emit(OpaqueExpr(t, src))
        return t

    def visit_DictComp(self, node: ast.DictComp):
        src = ast.unparse(node)
        t = self._get_temp()
        self._emit(OpaqueExpr(t, src))
        return t

    def visit_SetComp(self, node: ast.SetComp):
        src = ast.unparse(node)
        t = self._get_temp()
        self._emit(OpaqueExpr(t, src))
        return t

    def visit_Dict(self, node: ast.Dict):
        src = ast.unparse(node)
        t = self._get_temp()
        self._emit(OpaqueExpr(t, src))
        return t

    def visit_Set(self, node: ast.Set):
        src = ast.unparse(node)
        t = self._get_temp()
        self._emit(OpaqueExpr(t, src))
        return t

    def visit_JoinedStr(self, node: ast.JoinedStr):
        src = ast.unparse(node)
        t = self._get_temp()
        self._emit(OpaqueExpr(t, src))
        return t

    def visit_IfExp(self, node: ast.IfExp):
        src = ast.unparse(node)
        t = self._get_temp()
        self._emit(OpaqueExpr(t, src))
        return t

    def visit_Lambda(self, node: ast.Lambda):
        src = ast.unparse(node)
        t = self._get_temp()
        self._emit(OpaqueExpr(t, src))
        return t

    def visit_Starred(self, node: ast.Starred):
        return self.visit(node.value)

    # ── Assignment helpers ──────────────────────────────────────────

    def _assign_target(self, target: ast.AST, value):
        """Emit assignment for a (possibly nested) target."""
        if isinstance(target, ast.Name):
            self._emit(Assign(Variable(target.id), value))
        elif isinstance(target, (ast.Tuple, ast.List)):
            for i, elt in enumerate(target.elts):
                elem = self._get_temp()
                self._emit(GetItem(elem, value, Constant(i)))
                self._assign_target(elt, elem)
        elif isinstance(target, ast.Subscript):
            obj = self.visit(target.value)
            if isinstance(target.slice, ast.Slice):
                lo = self.visit(target.slice.lower) if target.slice.lower else Constant(None)
                hi = self.visit(target.slice.upper) if target.slice.upper else Constant(None)
                st = self.visit(target.slice.step) if target.slice.step else Constant(None)
                key = self._get_temp()
                self._emit(BuildSlice(key, lo, hi, st))
            else:
                key = self.visit(target.slice)
            self._emit(SetItem(obj, key, value))
        elif isinstance(target, ast.Attribute):
            obj = self.visit(target.value)
            self._emit(StoreAttr(obj, target.attr, value))

    # ── Statements ─────────────────────────────────────────────────

    def visit_Assign(self, node: ast.Assign):
        value = self.visit(node.value)
        for target in node.targets:
            self._assign_target(target, value)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value:
            value = self.visit(node.value)
            self._assign_target(node.target, value)

    def visit_AugAssign(self, node: ast.AugAssign):
        op = _BINOP_MAP.get(type(node.op), "?")
        rhs = self.visit(node.value)

        if isinstance(node.target, ast.Name):
            var = Variable(node.target.id)
            t = self._get_temp()
            self._emit(BinaryOp(t, var, op, rhs))
            self._emit(Assign(var, t))
        elif isinstance(node.target, ast.Subscript):
            obj = self.visit(node.target.value)
            if isinstance(node.target.slice, ast.Slice):
                lo = self.visit(node.target.slice.lower) if node.target.slice.lower else Constant(None)
                hi = self.visit(node.target.slice.upper) if node.target.slice.upper else Constant(None)
                st = self.visit(node.target.slice.step) if node.target.slice.step else Constant(None)
                key = self._get_temp()
                self._emit(BuildSlice(key, lo, hi, st))
            else:
                key = self.visit(node.target.slice)
            old = self._get_temp()
            self._emit(GetItem(old, obj, key))
            new = self._get_temp()
            self._emit(BinaryOp(new, old, op, rhs))
            self._emit(SetItem(obj, key, new))
        elif isinstance(node.target, ast.Attribute):
            obj = self.visit(node.target.value)
            old = self._get_temp()
            self._emit(LoadAttr(old, obj, node.target.attr))
            new = self._get_temp()
            self._emit(BinaryOp(new, old, op, rhs))
            self._emit(StoreAttr(obj, node.target.attr, new))

    def visit_Expr(self, node: ast.Expr):
        result = self.visit(node.value)
        # If it's a bare call with no assignment, emit without target
        if isinstance(node.value, ast.Call) and result is not None:
            # The Call was already emitted with a temp target; re-emit as void
            # (last instruction in block is the Call with temp target — fine for IR)
            pass

    def visit_Return(self, node: ast.Return):
        val = self.visit(node.value) if node.value else None
        self._emit(Return(val))

    def visit_Raise(self, node: ast.Raise):
        exc = self.visit(node.exc) if node.exc else None
        self._emit(Raise(exc))

    def visit_Assert(self, node: ast.Assert):
        test = self.visit(node.test)
        msg = self.visit(node.msg) if node.msg else None
        self._emit(Assert(test, msg))

    def visit_Delete(self, node: ast.Delete):
        pass  # skip del statements

    def visit_Global(self, node: ast.Global):
        pass

    def visit_Nonlocal(self, node: ast.Nonlocal):
        pass

    def visit_Pass(self, node: ast.Pass):
        pass

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self._emit(Import(alias.name, alias.asname))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            self._emit(ImportFrom(node.module or "", alias.name, alias.asname))

    # ── Control flow ───────────────────────────────────────────────

    def visit_If(self, node: ast.If):
        cond = self.visit(node.test)
        true_block = self.cfg.create_block()
        false_block = self.cfg.create_block()
        exit_block = self.cfg.create_block()

        self._emit(Branch(cond, true_block.id, false_block.id))
        self.cfg.add_edge(self.current_block.id, true_block.id)
        self.cfg.add_edge(self.current_block.id, false_block.id)

        self.current_block = true_block
        for stmt in node.body:
            self.visit(stmt)
        if not self._is_terminated():
            self._emit(Jump(exit_block.id))
            self.cfg.add_edge(self.current_block.id, exit_block.id)

        self.current_block = false_block
        for stmt in node.orelse:
            self.visit(stmt)
        if not self._is_terminated():
            self._emit(Jump(exit_block.id))
            self.cfg.add_edge(self.current_block.id, exit_block.id)

        self.current_block = exit_block

    def visit_While(self, node: ast.While):
        header = self.cfg.create_block()
        body = self.cfg.create_block()
        exit_block = self.cfg.create_block()

        self._emit(Jump(header.id))
        self.cfg.add_edge(self.current_block.id, header.id)

        self.current_block = header
        cond = self.visit(node.test)
        self._emit(Branch(cond, body.id, exit_block.id))
        self.cfg.add_edge(header.id, body.id)
        self.cfg.add_edge(header.id, exit_block.id)

        self._loop_stack.append({'break': exit_block, 'continue': header})
        self.current_block = body
        for stmt in node.body:
            self.visit(stmt)
        if not self._is_terminated():
            self._emit(Jump(header.id))
            self.cfg.add_edge(self.current_block.id, header.id)
        self._loop_stack.pop()

        self.current_block = exit_block

    def visit_For(self, node: ast.For):
        iterable = self.visit(node.iter)
        header = self.cfg.create_block()
        body = self.cfg.create_block()
        exit_block = self.cfg.create_block()

        self._emit(Jump(header.id))
        self.cfg.add_edge(self.current_block.id, header.id)

        self.current_block = header
        elem = self._get_temp()
        self._emit(ForIter(elem, iterable, body.id, exit_block.id))
        self.cfg.add_edge(header.id, body.id)
        self.cfg.add_edge(header.id, exit_block.id)

        self.current_block = body
        self._assign_target(node.target, elem)

        self._loop_stack.append({'break': exit_block, 'continue': header})
        for stmt in node.body:
            self.visit(stmt)
        if not self._is_terminated():
            self._emit(Jump(header.id))
            self.cfg.add_edge(self.current_block.id, header.id)
        self._loop_stack.pop()

        if node.orelse:
            self.current_block = exit_block
            for stmt in node.orelse:
                self.visit(stmt)
        else:
            self.current_block = exit_block

    def visit_Break(self, node: ast.Break):
        if self._loop_stack:
            target = self._loop_stack[-1]['break']
            self._emit(Jump(target.id))
            self.cfg.add_edge(self.current_block.id, target.id)

    def visit_Continue(self, node: ast.Continue):
        if self._loop_stack:
            target = self._loop_stack[-1]['continue']
            self._emit(Jump(target.id))
            self.cfg.add_edge(self.current_block.id, target.id)

    def visit_Try(self, node: ast.Try):
        # Simplified: lift body, skip except/finally for now
        for stmt in node.body:
            self.visit(stmt)

    def visit_With(self, node: ast.With):
        for stmt in node.body:
            self.visit(stmt)

    # ── Definitions ────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef):
        sub = IR_Lifter()
        sub.cfg.name = node.name
        for stmt in node.body:
            sub.visit(stmt)
        args = [a.arg for a in node.args.args]
        self._emit(FuncDef(node.name, args, sub.cfg))

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef):
        pass  # skip class definitions for now

    def visit_Module(self, node: ast.Module):
        for stmt in node.body:
            self.visit(stmt)

    def visit_Interactive(self, node):
        for stmt in node.body:
            self.visit(stmt)
