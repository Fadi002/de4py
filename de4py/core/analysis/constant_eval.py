# de4py - Onyx Engine
# Pre-lift AST constant folding + deobfuscation passes

import ast
from base64 import b64decode, b85decode

_SAFE_ENV = {
    'b64decode': b64decode,
    'b85decode': b85decode,
    'chr': chr, 'ord': ord, 'len': len, 'int': int,
    'str': str, 'bytes': bytes, 'list': list, 'range': range,
    'True': True, 'False': False, 'None': None,
    '__builtins__': {},
}


def _safe_eval(node: ast.AST):
    try:
        val = eval(compile(ast.Expression(body=node), '<fold>', 'eval'), _SAFE_ENV)
        if isinstance(val, (int, float, str, bytes, bool, type(None))):
            return True, val
    except Exception:
        pass
    return False, None


class ConstantExprFolder(ast.NodeTransformer):
    def _fold(self, node):
        ok, val = _safe_eval(node)
        if ok:
            return ast.copy_location(ast.Constant(value=val), node)
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_Call(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_Subscript(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_Attribute(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_JoinedStr(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_IfExp(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_Compare(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        return self._fold(node)


class GlobalsBuiltinResolver(ast.NodeTransformer):
    """globals()['key'] → Name('key')"""

    def visit_Subscript(self, node: ast.Subscript):
        self.generic_visit(node)
        if (isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == 'globals'
                and not node.value.args
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            return ast.copy_location(ast.Name(id=node.slice.value, ctx=ast.Load()), node)
        return node


class BuiltinsDictUnwrapper(ast.NodeTransformer):
    """
    Resolves builtins-dict subscript pattern used in style-2 obfuscation.
    Detects the variable holding globals()['__builtins__'] (or __dict__)
    and replaces dict['name'] with just Name('name').
    """

    def __init__(self):
        self._builtins_src: set = {'__builtins__'}
        self._builtins_dict: set = set()

    def visit_Module(self, node: ast.Module):
        self._collect_aliases(node)
        self.generic_visit(node)
        return node

    def _collect_aliases(self, node: ast.AST):
        for child in ast.walk(node):
            if not isinstance(child, ast.Assign) or len(child.targets) != 1:
                continue
            tgt = child.targets[0]
            if not isinstance(tgt, ast.Name):
                continue
            val = child.value
            name = tgt.id

            # x = __builtins__
            if isinstance(val, ast.Name) and val.id in self._builtins_src:
                self._builtins_src.add(name)
                self._builtins_dict.add(name)

            # x = y if isinstance(y, dict) else y.__dict__
            elif isinstance(val, ast.IfExp):
                body_name = val.body.id if isinstance(val.body, ast.Name) else None
                orelse_obj = (val.orelse.value.id
                              if isinstance(val.orelse, ast.Attribute)
                              and isinstance(val.orelse.value, ast.Name)
                              and val.orelse.attr == '__dict__' else None)
                if body_name in self._builtins_src or orelse_obj in self._builtins_src:
                    self._builtins_dict.add(name)

        self._builtins_dict.update(self._builtins_src)

    def visit_Subscript(self, node: ast.Subscript):
        self.generic_visit(node)
        if (isinstance(node.value, ast.Name)
                and node.value.id in self._builtins_dict
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            return ast.copy_location(ast.Name(id=node.slice.value, ctx=ast.Load()), node)
        return node


def _run_fold(tree: ast.AST, passes: int = 8) -> ast.AST:
    for _ in range(passes):
        new = ConstantExprFolder().visit(tree)
        ast.fix_missing_locations(new)
        if ast.dump(new) == ast.dump(tree):
            break
        tree = new
    return tree


def fold_constants(tree: ast.AST) -> ast.AST:
    """
    Full pre-lift deobfuscation pipeline:
    1. Fold constants (so lambda args become string literals)
    2. Resolve globals()['key'] → Name('key')
    3. Fold again
    4. Unwrap builtins-dict subscript calls → direct names
    5. Final fold
    """
    ast.fix_missing_locations(tree)
    tree = _run_fold(tree, 8)
    tree = GlobalsBuiltinResolver().visit(tree)
    ast.fix_missing_locations(tree)
    tree = _run_fold(tree, 4)
    tree = BuiltinsDictUnwrapper().visit(tree)
    ast.fix_missing_locations(tree)
    tree = _run_fold(tree, 4)
    return tree
