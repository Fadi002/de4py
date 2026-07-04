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
