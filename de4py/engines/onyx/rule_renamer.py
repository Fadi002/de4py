# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Deterministic rename of obfuscated Python identifiers using type inference and naming heuristics.
"""

import ast
import re
import builtins
from typing import Dict, Set, Optional, List

# --- Config -------------------------------------------------------------------

CALL_TO_NAME: Dict[str, str] = {
    # I/O
    "open":              "file_handle",
    "read":              "file_content",
    "readlines":         "lines",
    "readline":          "line",
    "write":             "bytes_written",
    "input":             "user_input",
    "print":             "output",

    # Collections
    "list":              "items",
    "dict":              "mapping",
    "set":               "unique_items",
    "tuple":             "record",
    "sorted":            "sorted_items",
    "reversed":          "reversed_iter",
    "enumerate":         "indexed_iter",
    "zip":               "zipped",
    "map":               "mapped",
    "filter":            "filtered",
    "range":             "range_iter",
    "defaultdict":       "default_mapping",
    "OrderedDict":       "ordered_mapping",
    "Counter":           "counter",
    "deque":             "queue",
    "heapq":             "heap",
    "chain":             "chained_iter",

    # Types
    "str":               "text",
    "int":               "number",
    "float":             "value",
    "bool":              "flag",
    "bytes":             "raw_bytes",
    "bytearray":         "byte_buffer",
    "memoryview":        "memory_view",
    "complex":           "complex_num",

    # String operations
    "split":             "parts",
    "rsplit":            "parts",
    "join":              "joined",
    "strip":             "stripped",
    "lstrip":            "stripped",
    "rstrip":            "stripped",
    "replace":           "replaced",
    "encode":            "encoded",
    "decode":            "decoded",
    "format":            "formatted",
    "lower":             "lowercase",
    "upper":             "uppercase",
    "title":             "title_cased",
    "capitalize":        "capitalized",
    "find":              "found_index",
    "index":             "found_index",
    "count":             "occurrence_count",
    "startswith":        "starts_with_result",
    "endswith":          "ends_with_result",
    "zfill":             "zero_padded",
    "ljust":             "left_justified",
    "rjust":             "right_justified",
    "expandtabs":        "expanded_text",
    "translate":         "translated",
    "maketrans":         "translation_table",
    "partition":         "partitioned",

    # Math / compute
    "len":               "count",
    "sum":               "total",
    "max":               "maximum",
    "min":               "minimum",
    "abs":               "absolute",
    "round":             "rounded",
    "pow":               "power",
    "divmod":            "div_and_mod",
    "hash":              "hash_value",
    "id":                "object_id",
    "hex":               "hex_string",
    "oct":               "oct_string",
    "bin":               "bin_string",
    "chr":               "character",
    "ord":               "char_code",

    # OS / paths
    "getcwd":            "current_dir",
    "listdir":           "dir_entries",
    "path.join":         "path",
    "path.dirname":      "dir_path",
    "path.basename":     "filename",
    "path.exists":       "path_exists",
    "path.abspath":      "abs_path",
    "path.splitext":     "name_and_ext",
    "path.expanduser":   "expanded_path",
    "glob":              "matched_paths",
    "scandir":           "dir_scanner",
    "makedirs":          "created_dirs",
    "getenv":            "env_value",
    "environ":           "env_vars",
    "getpid":            "process_id",
    "getuid":            "user_id",
    "gethostname":       "hostname",

    # JSON / serialization
    "json.loads":        "parsed_data",
    "json.dumps":        "json_string",
    "json.load":         "loaded_data",
    "json.dump":         "json_output",
    "pickle.loads":      "deserialized",
    "pickle.dumps":      "serialized",
    "yaml.safe_load":    "parsed_yaml",
    "yaml.dump":         "yaml_string",
    "toml.loads":        "parsed_toml",
    "configparser":      "config",

    # Network / requests
    "requests.get":      "response",
    "requests.post":     "response",
    "requests.put":      "response",
    "requests.delete":   "response",
    "requests.request":  "response",
    "requests.Session":  "session",
    "urlopen":           "url_response",
    "socket":            "sock",
    "connect":           "connection",
    "gethostbyname":     "ip_address",
    "getaddrinfo":       "addr_info",
    "create_connection": "connection",
    "AsyncClient":       "async_client",
    "ClientSession":     "http_session",

    # Subprocess
    "subprocess.run":    "proc_result",
    "subprocess.Popen":  "process",
    "check_output":      "cmd_output",
    "check_call":        "call_result",
    "communicate":       "proc_output",
    "Popen":             "process",

    # Hashing / crypto
    "md5":               "md5_hash",
    "sha1":              "sha1_hash",
    "sha256":            "sha256_hash",
    "sha512":            "sha512_hash",
    "sha3_256":          "sha3_hash",
    "blake2b":           "blake_hash",
    "hexdigest":         "hex_hash",
    "digest":            "hash_bytes",
    "pbkdf2_hmac":       "derived_key",
    "Fernet":            "cipher",
    "AES":               "cipher",
    "RSA":               "rsa_key",
    "generate_key":      "secret_key",
    "encrypt":           "encrypted_data",
    "decrypt":           "decrypted_data",

    # Regex
    "compile":           "pattern",
    "match":             "match_result",
    "search":            "search_result",
    "findall":           "matches",
    "finditer":          "match_iter",
    "sub":               "substituted",
    "subn":              "substituted",
    "groups":            "groups",
    "group":             "match_group",
    "groupdict":         "match_dict",
    "span":              "match_span",

    # Time
    "time":              "timestamp",
    "monotonic":         "monotonic_time",
    "perf_counter":      "perf_time",
    "sleep":             "sleep_result",
    "strftime":          "formatted_time",
    "strptime":          "parsed_time",
    "gmtime":            "utc_time",
    "localtime":         "local_time",
    "datetime":          "dt",
    "timedelta":         "time_delta",
    "now":               "current_time",
    "today":             "today",
    "utcnow":            "utc_now",

    # Random
    "random":            "random_value",
    "randint":           "random_int",
    "choice":            "random_choice",
    "choices":           "random_choices",
    "sample":            "random_sample",
    "shuffle":           "shuffled",
    "uniform":           "random_float",
    "seed":              "rng",
    "uuid4":             "unique_id",
    "uuid1":             "unique_id",

    # Threading / async
    "Thread":            "thread",
    "Lock":              "lock",
    "Event":             "event",
    "Queue":             "task_queue",
    "Semaphore":         "semaphore",
    "gather":            "gathered_results",
    "create_task":       "task",
    "run":               "task_result",

    # Argparse / CLI
    "ArgumentParser":    "arg_parser",
    "parse_args":        "args",
    "add_argument":      "arg_def",

    # Logging
    "getLogger":         "logger",
    "StreamHandler":     "log_handler",
    "FileHandler":       "file_log_handler",
    "Formatter":         "log_formatter",

    # Data / ML
    "DataFrame":         "df",
    "Series":            "series",
    "read_csv":          "df",
    "read_json":         "df",
    "read_excel":        "df",
    "array":             "arr",
    "zeros":             "zero_array",
    "ones":              "one_array",
    "arange":            "num_range",
    "linspace":          "lin_space",
    "reshape":           "reshaped",
    "transpose":         "transposed",
    "mean":              "mean_value",
    "std":               "std_dev",
    "var":               "variance",
    "dot":               "dot_product",
    "matmul":            "matrix_product",
    "concatenate":       "concatenated",
    "vstack":            "stacked",
    "hstack":            "stacked",

    # Database
    "connect":           "db_conn",
    "cursor":            "db_cursor",
    "execute":           "db_result",
    "fetchall":          "rows",
    "fetchone":          "row",
    "commit":            "commit_result",
    "rollback":          "rollback_result",
}

NEVER_RENAME: Set[str] = {
    *dir(builtins),
    'self', 'cls', 'args', 'kwargs',
    '__name__', '__file__', '__doc__', '__module__', '__package__',
    '__init__', '__new__', '__del__', '__repr__', '__str__',
    '__len__', '__iter__', '__next__', '__enter__', '__exit__',
    '__get__', '__set__', '__delete__', '__call__',
    '__add__', '__sub__', '__mul__', '__truediv__', '__floordiv__',
    '__eq__', '__ne__', '__lt__', '__gt__', '__le__', '__ge__',
    '__getitem__', '__setitem__', '__delitem__', '__contains__',
    '__hash__', '__bool__', '__int__', '__float__', '__bytes__',
    '__getattr__', '__setattr__', '__delattr__', '__slots__',
    '__class__', '__bases__', '__mro__', '__dict__', '__weakref__',
    'main', 'run', 'start', 'stop', 'init', 'setup', 'teardown',
    'parse', 'format', 'encode', 'decode', 'read', 'write',
    'get', 'set', 'add', 'remove', 'update', 'delete', 'create',
    'load', 'save', 'open', 'close', 'connect', 'disconnect',
    'i', 'j', 'k', 'n', 'x', 'y', 'z',  # conventional math vars
    'e',    # except Exception as e — convention
    'f',    # file handles (f = open(...))
    'fp',   # file pointer
    'ok',   # boolean result
    'err',  # error variable
    'ex',   # exception
    'exc',  # exception
    'msg',  # message
    'buf',  # buffer
    'tmp',  # temporary
    'ret',  # return value
    'res',  # result
    'val',  # value
    'idx',  # index
    'key',  # dict key
    'kw',   # keyword
}

# --- Pattern detection --------------------------------------------------------

MANGLED_PATTERNS = [
    re.compile(r'^[a-zA-Z]\d{1,3}$'),              # a1, b99, Z12
    re.compile(r'^[a-zA-Z]{1,2}$'),                 # a, ab (but single letter math vars are ok)
    re.compile(r'^[OIl1]{3,}$'),                    # OOIl11lI — zero/one confusables
    re.compile(r'^[O0][O0][O0]+\w*$'),             # OO0O0O style
    re.compile(r'^_{3,}\w+'),                       # ___var, ____x
    re.compile(r'^[A-Z][a-z][A-Z][a-z]$'),         # AbCd style
    re.compile(r'^l[0-9O]+$'),                      # l0, lO, lO0
    re.compile(r'^[a-z]{1,2}\d{2,}$'),              # ab12, z99
    re.compile(r'^[a-z]{2,4}__$'),                  # gvs__, dva__, cvf__
    re.compile(r'^[a-z]{1,3}v[a-z]__$'),            # xvx__ pattern
    re.compile(r'^[a-zA-Z][a-zA-Z0-9]{4,}__$'),    # longer __-suffix names
    re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,3}v[a-zA-Z0-9_]{1,3}__$'),
    # Random obfuscated names: 3+ consonant clusters with digits
    re.compile(r'^[a-z]{2,5}\d+[a-z]{2,5}$'),      # ab12cd, zpk3pg2
    re.compile(r'^[a-z]{2,6}_[a-z]{3,8}$'),         # ors8odw, suyfet (short_word style when both parts random)
    re.compile(r'^[a-z]\d[a-z]{2,4}\d[a-z]{1,4}$'),# u3vd2, j0tmc pattern
    re.compile(r'^[a-z]{2,4}\d{1,3}[a-z]{2,4}\d{1,4}$'), # xm7uo4zhy0d2 style
    re.compile(r'^[a-z]{1,4}\d{1,2}[a-z]{1,4}\d{1,2}[a-z]{1,4}$'),  # mixed digit-letter
    re.compile(r'[0-9]{2,}[a-z]{2,}[0-9]'),          # contains 2+ digits total in middle
    re.compile(r'^[a-z]{2,8}\d{4,}$'),              # snlgaimd + long digit run
    re.compile(r'^[a-z]{1,3}\d{3,4}[a-z]{2,5}$'),  # u3vd2_nusnh prefix part
]


def is_mangled(name: str) -> bool:
    if name in NEVER_RENAME:
        return False
    if name.startswith('__') and name.endswith('__'):
        return False
    for pattern in MANGLED_PATTERNS:
        if pattern.match(name):
            return True
    return False


# --- Main class ---------------------------------------------------------------

class RuleRenamer:

    def __init__(self):
        self._rename_map: Dict[str, str] = {}
        self._counters:   Dict[str, int] = {}

    def rename(self, source: str) -> str:
        self._rename_map = {}
        self._counters   = {}

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        try:
            # Pass 1: collect rename decisions
            collector = _NameCollector(self._rename_map, self._counters)
            collector.visit(tree)

            if not self._rename_map:
                return source

            # Pass 2: apply renames
            applier = _NameApplier(self._rename_map)
            tree    = applier.visit(tree)
            ast.fix_missing_locations(tree)

            return ast.unparse(tree)
        except RecursionError:
            return source
        except Exception:
            return source

    def _fresh(self, base: str) -> str:
        n = self._counters.get(base, 0)
        self._counters[base] = n + 1
        return base if n == 0 else f"{base}_{n}"


# --- Pass 1: Collector --------------------------------------------------------

class _NameCollector(ast.NodeVisitor):

    def __init__(self, rename_map: Dict[str, str], counters: Dict[str, int]):
        self._map      = rename_map
        self._counters = counters

        # Build usage profile: name → list of uses  (for usage-pattern analysis)
        self._usages: Dict[str, List[ast.Call]] = {}

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and is_mangled(target.id):
                if target.id not in self._map:
                    name = self._infer_from_value(node.value)
                    self._map[target.id] = self._fresh(name)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        if isinstance(node.target, ast.Name) and is_mangled(node.target.id):
            if node.target.id not in self._map:
                # x += N where N is numeric → it's a counter
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)):
                    self._map[node.target.id] = self._fresh("counter")
                else:
                    self._map[node.target.id] = self._fresh("accumulator")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if isinstance(node.target, ast.Name) and is_mangled(node.target.id):
            if node.target.id not in self._map:
                name = self._infer_from_annotation(node.annotation)
                self._map[node.target.id] = self._fresh(name)
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        if isinstance(node.target, ast.Name) and is_mangled(node.target.id):
            if node.target.id not in self._map:
                iter_name = self._infer_iter_name(node.iter)
                self._map[node.target.id] = self._fresh(iter_name)
        # Also handle tuple unpacking in for loops
        elif isinstance(node.target, ast.Tuple):
            for elt in node.target.elts:
                if isinstance(elt, ast.Name) and is_mangled(elt.id):
                    if elt.id not in self._map:
                        self._map[elt.id] = self._fresh("item")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        """Rename exception variable in: except SomeError as mangled_name"""
        if node.name and is_mangled(node.name) and node.name not in self._map:
            exc_type = "exc"
            if node.type and isinstance(node.type, ast.Name):
                base = node.type.id.lower()
                if base.endswith('error') or base.endswith('exception') or base.endswith('warning'):
                    exc_type = base.replace('error', '_err').replace('exception', '_exc').replace('warning', '_warn')
                else:
                    exc_type = base + "_exc"
            self._map[node.name] = self._fresh(exc_type)
        self.generic_visit(node)

    def visit_withitem(self, node):
        """Rename with-statement targets: with open(f) as mangled → as file_handle"""
        if node.optional_vars and isinstance(node.optional_vars, ast.Name):
            name = node.optional_vars.id
            if is_mangled(name) and name not in self._map:
                # Try to infer from the context manager
                cm_name = self._infer_context_manager(node.context_expr)
                self._map[name] = self._fresh(cm_name)

    def visit_arg(self, node: ast.arg):
        if is_mangled(node.arg) and node.arg not in self._map:
            if node.annotation:
                name = self._infer_from_annotation(node.annotation)
            else:
                name = "param"
            self._map[node.arg] = self._fresh(name)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if is_mangled(node.name) and node.name not in self._map:
            self._map[node.name] = self._fresh("func")
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef):
        if is_mangled(node.name) and node.name not in self._map:
            self._map[node.name] = self._fresh("MyClass")
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp):
        """Rename comprehension loop variables."""
        for generator in node.generators:
            if isinstance(generator.target, ast.Name) and is_mangled(generator.target.id):
                if generator.target.id not in self._map:
                    iter_name = self._infer_iter_name(generator.iter)
                    self._map[generator.target.id] = self._fresh(iter_name)
        self.generic_visit(node)

    visit_SetComp      = visit_ListComp
    visit_GeneratorExp = visit_ListComp

    def visit_Lambda(self, node: ast.Lambda):
        """Rename lambda parameters if they are mangled."""
        for arg in node.args.args:
            if is_mangled(arg.arg) and arg.arg not in self._map:
                self._map[arg.arg] = self._fresh('param')
        for arg in (node.args.vararg, node.args.kwarg):
            if arg and is_mangled(arg.arg) and arg.arg not in self._map:
                self._map[arg.arg] = self._fresh('param')
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp):
        for generator in node.generators:
            if isinstance(generator.target, ast.Name) and is_mangled(generator.target.id):
                if generator.target.id not in self._map:
                    self._map[generator.target.id] = self._fresh("item")
            elif isinstance(generator.target, ast.Tuple):
                elts = generator.target.elts
                if len(elts) == 2:
                    k, v = elts
                    if isinstance(k, ast.Name) and is_mangled(k.id) and k.id not in self._map:
                        self._map[k.id] = self._fresh("key")
                    if isinstance(v, ast.Name) and is_mangled(v.id) and v.id not in self._map:
                        self._map[v.id] = self._fresh("value")
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr):
        """Handle walrus operator: (x := expr)"""
        if isinstance(node.target, ast.Name) and is_mangled(node.target.id):
            if node.target.id not in self._map:
                name = self._infer_from_value(node.value)
                self._map[node.target.id] = self._fresh(name)
        self.generic_visit(node)

    # --- Inference helpers ------------------------------------------------------

    def _infer_from_value(self, value: ast.expr) -> str:
        if isinstance(value, ast.Constant):
            return self._infer_from_constant(value.value)

        if isinstance(value, ast.Call):
            return self._infer_from_call(value)

        if isinstance(value, ast.List):          return "items"
        if isinstance(value, ast.Dict):          return "mapping"
        if isinstance(value, ast.Set):           return "unique_items"
        if isinstance(value, ast.Tuple):         return "record"
        if isinstance(value, ast.ListComp):      return "items"
        if isinstance(value, ast.DictComp):      return "mapping"
        if isinstance(value, ast.SetComp):       return "unique_items"
        if isinstance(value, ast.GeneratorExp):  return "generator"
        if isinstance(value, ast.Lambda):        return "func"
        if isinstance(value, ast.IfExp):         return "conditional_value"
        if isinstance(value, ast.Subscript):     return "item"
        if isinstance(value, ast.JoinedStr):     return "text"  # f-string

        if isinstance(value, ast.Attribute):
            attr = value.attr
            if not is_mangled(attr):
                return attr if attr not in NEVER_RENAME else "attribute"
            return "attribute"

        if isinstance(value, ast.BinOp):
            # String + String → text; int + int → number; etc.
            if isinstance(value.op, ast.Add):
                l = self._infer_from_value(value.left)
                r = self._infer_from_value(value.right)
                if l == r:
                    return l
                if 'text' in (l, r) or 'string' in (l, r):
                    return "text"
                return "computed_value"
            return "computed_value"

        if isinstance(value, ast.Name):
            # Propagate rename if already seen
            if value.id in self._map:
                return self._map[value.id]
            if not is_mangled(value.id):
                return value.id

        return "var"

    def _infer_from_constant(self, val) -> str:
        if isinstance(val, bool):      return "flag"
        if isinstance(val, int):       return "value"
        if isinstance(val, float):     return "value"
        if isinstance(val, str):       return "text"
        if isinstance(val, bytes):     return "raw_bytes"
        if val is None:                return "result"
        return "constant"

    def _infer_from_call(self, node: ast.Call) -> str:
        func_name = _get_func_name(node)

        if func_name in CALL_TO_NAME:
            return CALL_TO_NAME[func_name]

        short = func_name.split('.')[-1]
        if short in CALL_TO_NAME:
            return CALL_TO_NAME[short]

        # Heuristic: ClassName() → instance_of_classname
        if short and short[0].isupper():
            snake = re.sub(r'(?<!^)(?=[A-Z])', '_', short).lower()
            if len(snake) > 2:
                return snake

        if func_name and not is_mangled(func_name):
            return f"{short}_result" if short else "result"

        return "result"

    def _infer_from_annotation(self, annotation: ast.expr) -> str:
        if isinstance(annotation, ast.Name):
            name = annotation.id.lower()
            type_to_name = {
                'str': 'text', 'int': 'number', 'float': 'value',
                'bool': 'flag', 'bytes': 'raw_bytes', 'list': 'items',
                'dict': 'mapping', 'set': 'unique_items', 'tuple': 'record',
                'none': 'result', 'any': 'value', 'callable': 'func',
                'optional': 'maybe_value', 'sequence': 'sequence',
                'iterator': 'iterator', 'generator': 'generator',
                'type': 'cls', 'object': 'obj',
            }
            return type_to_name.get(name, name)

        if isinstance(annotation, ast.Subscript):
            # Optional[str] → text, List[str] → items, Dict[k,v] → mapping
            if isinstance(annotation.value, ast.Name):
                outer = annotation.value.id.lower()
                if outer in ('list', 'sequence', 'tuple', 'set', 'frozenset'):
                    return 'items'
                if outer in ('dict', 'mapping', 'ordereddict'):
                    return 'mapping'
                if outer == 'optional':
                    return 'maybe_value'
                if outer == 'callable':
                    return 'func'
                if outer in ('generator', 'iterator', 'iterable'):
                    return 'iterator'

        return "var"

    def _infer_iter_name(self, iter_node: ast.expr) -> str:
        if isinstance(iter_node, ast.Call):
            fname = _get_func_name(iter_node)
            if fname == 'range':        return "index"
            if fname == 'enumerate':    return "indexed_item"
            if fname == 'zip':          return "pair"
            if fname == 'items':        return "kv_pair"
            if fname == 'keys':         return "key"
            if fname == 'values':       return "value"
            if fname == 'reversed':     return "item"
            if fname == 'sorted':       return "item"
            if fname == 'filter':       return "item"
            if fname == 'map':          return "mapped_item"
            if fname == 'chain':        return "item"
        if isinstance(iter_node, ast.Name):
            name = iter_node.id.rstrip('s')   # items → item
            if not is_mangled(name) and len(name) > 2:
                return name
        if isinstance(iter_node, ast.Attribute):
            attr = iter_node.attr
            if attr in ('items', 'keys', 'values', 'children', 'entries', 'rows', 'columns'):
                return attr.rstrip('s') or 'item'
        return "item"

    def _infer_context_manager(self, cm: ast.expr) -> str:
        if isinstance(cm, ast.Call):
            fname = _get_func_name(cm)
            cm_map = {
                'open': 'file_handle',
                'lock': 'lock',
                'Lock': 'lock',
                'connect': 'connection',
                'session': 'session',
                'Session': 'session',
                'transaction': 'transaction',
                'Transaction': 'transaction',
                'cursor': 'cursor',
                'connection': 'connection',
                'suppress': 'suppressed',
                'TemporaryFile': 'temp_file',
                'NamedTemporaryFile': 'temp_file',
                'TemporaryDirectory': 'temp_dir',
                'patch': 'mock',
                'MagicMock': 'mock',
                'contextmanager': 'ctx',
            }
            short = fname.split('.')[-1]
            return cm_map.get(short, cm_map.get(fname, 'ctx_manager'))
        return "ctx_manager"

    def _fresh(self, base: str) -> str:
        # Never assign a name that is in NEVER_RENAME (e.g. 'getattr', 'setattr')
        if base in NEVER_RENAME:
            base = base + "_ref"
        n = self._counters.get(base, 0)
        self._counters[base] = n + 1
        return base if n == 0 else f"{base}_{n}"


# --- Pass 2: Applier ----------------------------------------------------------

class _NameApplier(ast.NodeTransformer):

    def __init__(self, rename_map: Dict[str, str]):
        self._map = rename_map

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self._map:
            node.id = self._map[node.id]
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        if node.arg in self._map:
            node.arg = self._map[node.arg]
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        if node.name in self._map:
            node.name = self._map[node.name]
        self.generic_visit(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        if node.name in self._map:
            node.name = self._map[node.name]
        self.generic_visit(node)
        return node

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler:
        if node.name and node.name in self._map:
            node.name = self._map[node.name]
        self.generic_visit(node)
        return node

    def visit_Global(self, node: ast.Global) -> ast.Global:
        node.names = [self._map.get(n, n) for n in node.names]
        return node

    def visit_Nonlocal(self, node: ast.Nonlocal) -> ast.Nonlocal:
        node.names = [self._map.get(n, n) for n in node.names]
        return node


# --- Utilities ----------------------------------------------------------------

def _get_func_name(call_node: ast.Call) -> str:
    func = call_node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts   = []
        current = func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return '.'.join(reversed(parts))
    return ""
