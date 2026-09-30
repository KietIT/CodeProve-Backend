"""Which student test inputs may run against the reference solution (P2.3).

A student test is a Python expression evaluated after the code under test. Run
against the reference, a free expression could read the reference itself and
leak it through the valid/invalid answer (`1 if 'x' in inspect.getsource(f)
else 0`), or reach the file system through a module the reference imported.
So an input must be one expression built only from literals, operators,
comprehensions, lambdas and calls, naming only what the reference defines at
top level (its functions, classes and constants) and a few safe builtins, with
no private or dunder attribute.
"""
import ast

from app.features.content.schema import ExerciseContent

MAX_INPUT_CHARS = 300
ENABLE_SHARE = 0.5  # the tab needs at least this share of the exercise's own tests to fit the rules

SAFE_BUILTINS = frozenset({
    "len", "sorted", "list", "dict", "set", "frozenset", "tuple", "range", "str", "int", "float", "bool",
    "min", "max", "sum", "abs", "any", "all", "enumerate", "zip", "reversed", "isinstance", "round",
    "True", "False", "None", "ValueError", "TypeError", "KeyError", "IndexError",
})
_ALLOWED_NODES = (
    ast.Expression, ast.Call, ast.keyword, ast.Name, ast.Load, ast.Store, ast.Constant, ast.Attribute,
    ast.List, ast.Tuple, ast.Dict, ast.Set, ast.Starred, ast.Subscript, ast.Slice,
    ast.UnaryOp, ast.UAdd, ast.USub, ast.Not, ast.Invert,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.BitOr, ast.BitAnd, ast.BitXor, ast.LShift, ast.RShift,
    ast.BoolOp, ast.And, ast.Or, ast.IfExp,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot,
    ast.Lambda, ast.arguments, ast.arg,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
)


def module_names(reference: str) -> set[str]:
    """Top-level functions, classes and assigned names of the reference (not its imports)."""
    names: set[str] = set()
    for node in ast.parse(reference).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {name for name in names if not name.startswith("_")}


def check_input(expr: str, allowed: set[str]) -> str | None:
    """None when the input may run, else why it may not (shown to the student)."""
    if len(expr) > MAX_INPUT_CHARS:
        return f"too long (max {MAX_INPUT_CHARS} characters)"
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"
    local = {n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}
    local |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return f"{type(node).__name__} is not allowed in a test"
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id.startswith("_") or node.id not in allowed | SAFE_BUILTINS | local:
                return f"name '{node.id}' is not allowed in a test"
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            return f"private attribute '{node.attr}' is not allowed in a test"
    return None


def enabled_share(content: ExerciseContent) -> float:
    """Share of the exercise's own tests that fit the rules: the tab is on when it is high enough."""
    allowed = module_names(content.reference_solution)
    fits = [check_input(t.input, allowed) is None for t in content.tests]
    return sum(fits) / len(fits) if fits else 0.0
