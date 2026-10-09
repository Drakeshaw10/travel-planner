"""Every Streamlit cache decorator must hide its spinner.

By default `st.cache_resource` / `st.cache_data` show "Running `get_graph()`."
while the function first runs, which shows users our internal function names.
This test reads the source (it doesn't run anything), so a new cached function
added without `show_spinner=False` fails here instead of in the browser.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [ROOT / "app.py", *sorted((ROOT / "planner").rglob("*.py"))]


def cache_decorators(tree):
    """Yield (line, decorator node) for every st.cache_resource / st.cache_data."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                if (isinstance(target, ast.Attribute) and target.attr in ("cache_resource", "cache_data")
                        and isinstance(target.value, ast.Name) and target.value.id == "st"):
                    yield node.name, dec


def test_cache_decorators_hide_the_spinner():
    offenders, found = [], 0
    for path in SOURCES:
        for name, dec in cache_decorators(ast.parse(path.read_text(encoding="utf-8"))):
            found += 1
            hides = isinstance(dec, ast.Call) and any(
                kw.arg == "show_spinner" and isinstance(kw.value, ast.Constant) and kw.value.value is False
                for kw in dec.keywords)
            if not hides:
                offenders.append(f"{path.relative_to(ROOT)}: {name}()")
    assert found >= 4, "expected get_graph, get_pool, get_checkpointer and get_llm"
    assert not offenders, f"cached without show_spinner=False: {offenders}"
