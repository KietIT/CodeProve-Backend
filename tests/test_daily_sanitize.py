import pytest

from app.features.daily.sanitize import strip_python_comments


def test_trailing_comment_removed():
    code = "def rev(s):\n    return s[::-1]  # This line is incorrect"
    assert strip_python_comments(code) == "def rev(s):\n    return s[::-1]"


def test_comment_only_line_becomes_empty():
    code = "def f(x):\n    # the bug is below\n    return x + 1"
    assert strip_python_comments(code) == "def f(x):\n\n    return x + 1"


def test_line_count_unchanged():
    code = (
        "# header comment\n"
        "def f(xs):\n"
        "    total = 0  # accumulator\n"
        "    # loop over items\n"
        "    for x in xs:\n"
        "        total += x\n"
        "    return total\n"
    )
    stripped = strip_python_comments(code)
    assert stripped.split("\n") == [
        "",
        "def f(xs):",
        "    total = 0",
        "",
        "    for x in xs:",
        "        total += x",
        "    return total",
        "",
    ]
    assert len(stripped.split("\n")) == len(code.split("\n"))


def test_hash_inside_string_literals_kept():
    code = (
        "def tag(s):\n"
        "    prefix = '#'\n"
        '    sep = "a#b"  # real comment\n'
        "    return prefix + s + sep"
    )
    assert strip_python_comments(code) == (
        "def tag(s):\n"
        "    prefix = '#'\n"
        '    sep = "a#b"\n'
        "    return prefix + s + sep"
    )


def test_hash_inside_triple_quoted_string_kept():
    code = 'def f():\n    text = """\n    # not a comment\n    """\n    return text  # bug'
    assert strip_python_comments(code) == (
        'def f():\n    text = """\n    # not a comment\n    """\n    return text'
    )


def test_hash_inside_fstring_kept():
    code = 'def f(n):\n    return f"#{n}"  # hint'
    assert strip_python_comments(code) == 'def f(n):\n    return f"#{n}"'


def test_code_without_comments_is_unchanged():
    code = "def f(a, b):\n    if a < b:\n        return a\n    return b"
    assert strip_python_comments(code) == code


def test_crlf_line_endings_preserved():
    code = "def f():\r\n    return 1  # note\r\n"
    assert strip_python_comments(code) == "def f():\r\n    return 1\r\n"


def test_untokenizable_code_raises_value_error():
    with pytest.raises(ValueError):
        strip_python_comments('def f():\n    return """unterminated')
