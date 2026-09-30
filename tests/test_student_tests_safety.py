"""P2.3 Task 1: which student test inputs may run against the reference solution."""
import pytest

from app.features.content.schema import CONTENT_DIR, load_content_file
from app.features.student_tests.safety import MAX_INPUT_CHARS, check_input, enabled_share, module_names

REFERENCE = (
    "import os\nfrom collections import OrderedDict\n\nLIMIT = 3\n\n"
    "def two_sum(nums, target):\n    return []\n\n"
    "class LRUCache:\n    def __init__(self, capacity):\n        self.capacity = capacity\n"
)
NAMES = module_names(REFERENCE)


def test_module_names_are_the_reference_definitions_not_its_imports():
    assert NAMES == {"LIMIT", "two_sum", "LRUCache"}


@pytest.mark.parametrize("expr", [
    "two_sum([2, 7, 11, 15], 9)",
    "two_sum([-1, -2], -3) == [0, 1]",
    "(lambda c: (c.put(1, 1), c.get(1))[-1])(LRUCache(2))",
    "[two_sum([i, 1], i + 1) for i in range(3)]",
    "len(two_sum([], 0))",
    "sorted({'a': 1}.items())",
    "two_sum(nums=[1, 2], target=3)",
    "LIMIT * 2",
])
def test_ordinary_tests_are_allowed(expr):
    assert check_input(expr, NAMES) is None


@pytest.mark.parametrize("expr, reason", [
    ("__import__('os').getcwd()", "__import__"),
    ("globals()['LIMIT']", "globals"),
    ("two_sum.__code__", "private attribute"),
    ("(lambda c: c.__class__)(LRUCache(1))", "private attribute"),
    ("open('x').read()", "open"),
    ("getattr(two_sum, 'x')", "getattr"),
    ("os.getcwd()", "os"),                       # imported by the reference, not allowed
    ("OrderedDict()", "OrderedDict"),
    ("type(two_sum)", "type"),
    ("(x := 1)", "NamedExpr"),
    ("two_sum(", "syntax"),
    ("x = 1", "syntax"),                         # statements are not expressions
    ("_private()", "_private"),
])
def test_escapes_are_refused_with_a_reason(expr, reason):
    refused = check_input(expr, NAMES)
    assert refused is not None and reason in refused, refused


def test_long_inputs_are_refused():
    assert "too long" in check_input("two_sum([" + "1, " * MAX_INPUT_CHARS + "1], 2)", NAMES)


def test_the_tab_is_enabled_where_most_reference_tests_fit():
    shares = {path.stem: enabled_share(load_content_file(path)) for path in sorted(CONTENT_DIR.glob("CP-*.json"))}
    enabled = {code for code, share in shares.items() if share >= 0.5}
    # Plain-call exercises get the tab; thread/file/DB-fake exercises whose tests need globals() and
    # __import__ do not (their Testing stays the correctness indicator).
    assert {"CP-001", "CP-004", "CP-101", "CP-105"} <= enabled
    assert not {"CP-012", "CP-206", "CP-208"} & enabled
