from app.features.exercises.starters import (
    is_untouched,
    strip_comments,
    student_safe_starter,
    student_starter,
)


def test_student_safe_starter_removes_function_body() -> None:
    starter = student_safe_starter(
        "def reverse_list(head):\n"
        "    prev = None\n"
        "    while head:\n"
        "        nxt = head.next\n"
        "        head.next = prev\n"
        "    return prev"
    )

    assert starter == "def reverse_list(head):\n    pass"
    assert "while head" not in starter
    assert "head.next" not in starter


def test_student_safe_starter_keeps_imports_and_class_signatures() -> None:
    starter = student_safe_starter(
        "from collections import OrderedDict\n\n"
        "class LRUCache:\n"
        "    def __init__(self, capacity):\n"
        "        self.cap = capacity\n"
        "    def get(self, key):\n"
        "        return -1"
    )

    assert "from collections import OrderedDict" in starter
    assert "class LRUCache:" in starter
    assert "def __init__(self, capacity):" in starter
    assert "def get(self, key):" in starter
    assert "self.cap = capacity" not in starter



def test_strip_comments_removes_inline_and_full_line_comments() -> None:
    src = (
        "def sum_to_n(n):\n"
        "    # accumulate\n"
        "    total = 0\n"
        "    for i in range(1, n):   # bug: never adds n itself\n"
        "        total += i\n"
        "    return total"
    )
    assert strip_comments(src) == (
        "def sum_to_n(n):\n"
        "    total = 0\n"
        "    for i in range(1, n):\n"
        "        total += i\n"
        "    return total"
    )


def test_strip_comments_keeps_hash_inside_strings() -> None:
    src = 'def tag():\n    return "#not-a-comment"  # real comment'
    assert strip_comments(src) == 'def tag():\n    return "#not-a-comment"'


def test_strip_comments_returns_source_unchanged_when_untokenizable() -> None:
    src = "def broken(:\n    x = (1,"
    assert strip_comments(src) == src


def test_student_starter_strips_comments_for_debug_and_body_for_implement() -> None:
    buggy = "def f(n):\n    return n - 1  # bug: should be n + 1"
    assert student_starter(buggy, "debug") == "def f(n):\n    return n - 1"
    assert student_starter("def f(n):\n    return n + 1", "implement") == "def f(n):\n    pass"


def test_is_untouched_ignores_whitespace_and_detects_empty_editor() -> None:
    starter = "def f(n):\n    pass"
    assert is_untouched("def f(n):\n    pass\n\n", starter) is True
    assert is_untouched("def f(n):   \r\n    pass", starter) is True
    assert is_untouched("   \n", starter) is True
    assert is_untouched("def f(n):\n    return n", starter) is False
