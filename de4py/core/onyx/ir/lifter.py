# de4py - Onyx Engine
# Python AST to IR Lifter

import ast
from typing import Any, List, Dict, Union, Optional
from .graph import CFG, BasicBlock
from .instructions import (
    Assign, BinaryOp, UnaryOp, Call, Jump, Branch, Return, LoadAttr, StoreAttr, Instruction
)
from .values import Constant, Variable, Temporary

class IR_Lifter(ast.NodeVisitor):
    def __init__(self):
        self.cfg = CFG()
        self.current_block = self.cfg.create_block()
        self._temp_count = 0
        self._loop_stack: List[dict] = [] # Stack of (break_block, continue_block)

    def _get_temp(self) -> Temporary:
        t = Temporary(self._temp_count)
        self._temp_count += 1
        return t

    def lift(self, tree: ast.AST) -> CFG:
        self.visit(tree)
        return self.cfg

    def _emit(self, instr: Instruction):
        self.current_block.add_instruction(instr)

    # --- Expressions ---

    def visit_Constant(self, node: ast.Constant) -> Union[Constant, Variable]:
        return Constant(node.value)

    def visit_Name(self, node: ast.Name) -> Variable:
        return Variable(node.id)

    def visit_BinOp(self, node: ast.BinOp) -> Variable:
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_map = {
            ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
            ast.FloorDiv: "//", ast.Mod: "%", ast.Pow: "**",
            ast.BitXor: "^", ast.BitAnd: "&", ast.BitOr: "|",
            ast.LShift: "<<", ast.RShift: ">>"
        }
        op = op_map.get(type(node.op), "?")
        target = self._get_temp()
        self._emit(BinaryOp(target, left, op, right))
        return target

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Variable:
        operand = self.visit(node.operand)
        op_map = {ast.USub: "-", ast.UAdd: "+", ast.Not: "not", ast.Invert: "~"}
        op = op_map.get(type(node.op), "?")
        target = self._get_temp()
        self._emit(UnaryOp(target, op, operand))
        return target

    def visit_Call(self, node: ast.Call) -> Variable:
        func = self.visit(node.func)
        args = [self.visit(arg) for arg in node.args]
        target = self._get_temp()
        self._emit(Call(target, func, args))
        return target

    def visit_Attribute(self, node: ast.Attribute) -> Variable:
        obj = self.visit(node.value)
        target = self._get_temp()
        self._emit(LoadAttr(target, obj, node.attr))
        return target

    # --- Statements ---

    def visit_Assign(self, node: ast.Assign):
        value = self.visit(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._emit(Assign(Variable(target.id), value))
            elif isinstance(target, ast.Attribute):
                obj = self.visit(target.value)
                self._emit(StoreAttr(obj, target.attr, value))

    def visit_Expr(self, node: ast.Expr):
        self.visit(node.value)

    def visit_Return(self, node: ast.Return):
        val = self.visit(node.value) if node.value else None
        self._emit(Return(val))

    def visit_If(self, node: ast.If):
        cond = self.visit(node.test)

        true_block = self.cfg.create_block()
        false_block = self.cfg.create_block()
        exit_block = self.cfg.create_block()

        self._emit(Branch(cond, true_block.id, false_block.id))
        self.cfg.add_edge(self.current_block.id, true_block.id)
        self.cfg.add_edge(self.current_block.id, false_block.id)

        # True branch
        self.current_block = true_block
        for stmt in node.body:
            self.visit(stmt)
        if not any(isinstance(i, (Jump, Return)) for i in self.current_block.instructions):
            self._emit(Jump(exit_block.id))
            self.cfg.add_edge(self.current_block.id, exit_block.id)

        # False branch (orelse)
        self.current_block = false_block
        for stmt in node.orelse:
            self.visit(stmt)
        if not any(isinstance(i, (Jump, Return)) for i in self.current_block.instructions):
            self._emit(Jump(exit_block.id))
            self.cfg.add_edge(self.current_block.id, exit_block.id)

        self.current_block = exit_block

    def visit_While(self, node: ast.While):
        header_block = self.cfg.create_block()
        body_block = self.cfg.create_block()
        exit_block = self.cfg.create_block()

        self._emit(Jump(header_block.id))
        self.cfg.add_edge(self.current_block.id, header_block.id)

        # Header: test condition
        self.current_block = header_block
        cond = self.visit(node.test)
        self._emit(Branch(cond, body_block.id, exit_block.id))
        self.cfg.add_edge(header_block.id, body_block.id)
        self.cfg.add_edge(header_block.id, exit_block.id)

        # Body
        self._loop_stack.append({'break': exit_block, 'continue': header_block})
        self.current_block = body_block
        for stmt in node.body:
            self.visit(stmt)
        if not any(isinstance(i, (Jump, Return)) for i in self.current_block.instructions):
            self._emit(Jump(header_block.id))
            self.cfg.add_edge(self.current_block.id, header_block.id)
        self._loop_stack.pop()

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
