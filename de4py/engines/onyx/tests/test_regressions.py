import ast
import base64
import zlib
import pytest
import sys
import os

# Add the parent directory to sys.path so we can import engines
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from de4py.engines.onyx.pipeline import Pipeline

@pytest.fixture
def pipeline_no_llm():
    return Pipeline(use_llm=False)

def test_regression_proxy_cleaning_preserves_legitimate_names(pipeline_no_llm):
    """
    Regression test for: https://github.com/Fadi002/de4py/issues/BUG_ID
    Ensures that legitimate (non-mangled) variable names are not deleted
    even if they are assigned a constant and inlined.
    """
    source = "x = 'Legitimate Variable Name'\nprint(x)\n"
    result = pipeline_no_llm.run(source, "regression.py")
    assert result.success
    # 'x' is not mangled, so it should be preserved in the output
    assert "x =" in result.cleaned
    assert "Legitimate Variable Name" in result.cleaned

def test_regression_proxy_cleaning_removes_mangled_proxies(pipeline_no_llm):
    """
    Ensures that mangled proxy variables ARE removed after inlining.
    """
    source = "a1 = 'Mangled Proxy'\nprint(a1)\n"
    result = pipeline_no_llm.run(source, "mangled_proxy.py")
    assert result.success
    # 'a1' is mangled, so it should be inlined and removed
    assert "a1 =" not in result.cleaned
    assert "Mangled Proxy" in result.cleaned

def test_regression_snake_case_not_mangled(pipeline_no_llm):
    """
    Ensures that normal snake_case names are not considered mangled.
    """
    from de4py.engines.onyx.rule_renamer import is_mangled
    assert not is_mangled("total_count")
    assert not is_mangled("user_id")
    assert not is_mangled("file_name")

def test_regression_z_is_math_var(pipeline_no_llm):
    """
    Ensures 'z' is considered a conventional math var and NOT mangled.
    """
    from de4py.engines.onyx.rule_renamer import is_mangled
    assert not is_mangled("z")

def test_regression_confusable_identifiers_stay_distinct():
    """
    Regression for: distinct homoglyph identifiers silently colliding.

    SkariorObf-2.0's identifier obfuscation mixes Latin/Cyrillic/Greek
    lookalike characters to build several names that are visually confusable
    with each other but genuinely distinct. Normalizing each confusable
    character independently, without checking whether the result collides
    with another name's own normalized form, collapsed three separate
    variables into one identical ASCII name - silently aliasing them and
    corrupting a vars/globals/__builtins__ decode chain (the SkariorObf-2.0
    ground-truth pair dropped to ~2-5% literal recovery as a result).
    """
    from de4py.engines.onyx.proxy_cleaner import ProxyCleaner
    # 'О' is Cyrillic U+041E, 'Ο' is Greek U+039F - both confusable with Latin 'O'.
    latin, cyr, grk = 'O', 'О', 'Ο'
    name_a = latin + cyr + cyr + latin   # every arrangement normalizes to "OOOO"
    name_b = cyr + latin + latin + cyr
    name_c = grk + cyr + latin + grk
    source = f"{name_a} = 1\n{name_b} = 2\n{name_c} = 3\nprint({name_a}, {name_b}, {name_c})\n"

    out = ProxyCleaner().deobfuscate(source)
    tree = ast.parse(out)
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name) and n.func.id == "print")
    values = [a.value for a in call.args if isinstance(a, ast.Constant)]
    assert sorted(values, key=str) == [1, 2, 3], (
        f"three distinct identifiers collapsed onto one binding: print args {values}"
    )


def test_regression_builtins_indirection_exec_compile_chain(pipeline_no_llm):
    """
    Regression for: blank_obf_mild.py / test_obf.py style loaders were
    stuck at ~5% recovery even after individual pieces (getattr-via-
    builtins, __import__('builtins'), single-name container folding) were
    each fixed in isolation - only the full chain together unwraps the real
    obfuscator shape: every builtin (`exec`, `getattr`, `compile`,
    `__import__` itself) is reached only through
    `__import__('builtins').<name>`, never as a bare name, specifically so a
    static "eval(" / "exec(" grep on the source finds nothing. The payload
    is `zlib.decompress(base64.b64decode(...))`, wrapped in
    `compile(source, filename, 'exec')`, itself wrapped in `exec(...)`.
    """
    payload = zlib.compress(b"print('recovered')")
    b64 = base64.b64encode(payload).decode()
    source = (
        "__import__('builtins').exec(__import__('builtins').compile("
        "__import__('builtins').getattr(__import__('builtins').__import__('zlib'), 'decompress')("
        "__import__('builtins').getattr(__import__('builtins').__import__('base64'), 'b64decode')"
        f"('{b64}')), '<payload>', 'exec'))\n"
    )
    result = pipeline_no_llm.run(source, "builtins_indirection.py")
    assert result.success
    assert "print('recovered')" in result.cleaned or 'print("recovered")' in result.cleaned
    assert "__import__('builtins')" not in result.cleaned


def test_regression_single_name_container_assignment_folds():
    """
    Regression for: a bare-name assignment whose RHS folds to a list/dict
    (e.g. a nested comprehension decoding dotted-IP-style encoded ints) was
    left as an unreadable multi-hundred-character expression, because the
    only container-folding pass required a tuple/list *unpack* target
    (`a, b, c = <expr>`) - a single `name = <expr>` producing a list fell
    through untouched.
    """
    from de4py.engines.onyx.constant_eval import fold_constants
    source = (
        "pool = [int(part) for entry in "
        "[s.split('.') for s in ['1.2.3.4', '5.6.7.8']] for part in entry]\n"
    )
    out = fold_constants(source)
    tree = ast.parse(out)
    assign = next(n for n in tree.body if isinstance(n, ast.Assign))
    assert isinstance(assign.value, ast.List), (
        f"container-valued single-name assignment did not fold: {out!r}"
    )
    values = [e.value for e in assign.value.elts]
    assert values == [1, 2, 3, 4, 5, 6, 7, 8]


def test_regression_class_attribute_constant_pool_inlines(pipeline_no_llm):
    """
    Regression for: AbuDabu-pythonObf wraps each source literal as one
    attribute of a synthetic class (``class _x: _y = const``) instead of a
    bare-name proxy (``_y = const``). ``proxy_cleaner`` already inlines the
    bare-name form and removes the binding once every use is substituted;
    the class-attribute form fell through untouched, leaving the whole
    class definition plus ``ClassName.attr`` at every call site instead of
    the five original literals it stood in for.
    """
    source = (
        "class _x59721862x_:\n"
        "    _x89235192x_ = 'HELLO WORldd :))'\n"
        "    _x86557917x_ = b'hello world :((('\n"
        "print(_x59721862x_._x89235192x_)\n"
        "print(_x59721862x_._x86557917x_)\n"
    )
    result = pipeline_no_llm.run(source, "class_attr_pool.py")
    assert result.success
    assert "class _x59721862x_" not in result.cleaned
    assert "'HELLO WORldd :))'" in result.cleaned
    assert "b'hello world :((('" in result.cleaned


def test_regression_pure_function_evaluator_folds_container_results():
    """
    Regression for: a module-level decoder helper whose return value is a
    list/dict (a VM bytecode array recovered via
    ``json.loads(zlib.decompress(...))``, a decoded name/const pool, etc.)
    was left as an unresolved call at every call site, because
    ``PureFunctionEvaluator`` only accepted scalar results
    (str/int/float/bytes/bool/None) - the exact shape a bytecode-array
    decoder never has. This left custom-VM samples (vmmmm.py) with their
    encoded bytecode payload still hidden behind a function call instead of
    readable as a plain Python list literal.
    """
    from de4py.engines.onyx.constant_eval import fold_constants
    source = (
        "def decode_pool(parts):\n"
        "    return [int(p) for p in parts]\n"
        "prog = decode_pool(['1', '2', '3'])\n"
    )
    out = fold_constants(source)
    tree = ast.parse(out)
    assign = next(n for n in tree.body if isinstance(n, ast.Assign)
                  and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'prog')
    assert isinstance(assign.value, ast.List), (
        f"container-returning function call did not fold: {out!r}"
    )
    assert [e.value for e in assign.value.elts] == [1, 2, 3]
