from app.features.exercises.debug_regions import derive, hint_range, hit_regions

REFERENCE = "def f(n):\n    total = 0\n    for i in range(1, n + 1):\n        total += i\n    return total"
SERVED = "def f(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total"


def test_a_replaced_line_is_a_region():
    assert derive(SERVED, REFERENCE) == [[3]]


def test_separate_changes_are_separate_regions_and_adjacent_lines_one_region():
    served = "a = 1\nb = 2\nc = 3\nd = 4\ne = 5"
    reference = "a = 9\nb = 2\nc = 3\nd = 8\ne = 7"
    assert derive(served, reference) == [[1], [4, 5]]


def test_deleted_lines_count_and_pure_insertions_do_not_when_something_else_changed():
    served = "x = 0\n\ndef inc():\n    global x\n    x += 1"
    reference = "import threading\n\nlock = threading.Lock()\nx = 0\n\ndef inc():\n    global x\n    with lock:\n        x += 1"
    assert derive(served, reference) == [[5]]


def test_only_insertions_point_at_the_line_after_them():
    served = "def f(x):\n    return x"
    reference = "def f(x):\n    if x is None:\n        return 0\n    return x"
    assert derive(served, reference) == [[2]]


def test_comments_in_the_reference_do_not_create_regions():
    assert derive(SERVED, REFERENCE.replace("+ 1):", "+ 1):  # include n")) == [[3]]


def test_hint_range_widens_every_region_by_one_line_and_stays_in_the_file():
    assert hint_range([[3]], 5) == (2, 4)
    assert hint_range([[1], [4, 5]], 5) == (1, 5)


def test_hit_regions_marks_each_region_the_selection_touches():
    assert hit_regions([[1], [4, 5]], [5, 2]) == [False, True]
    assert hit_regions([[3]], []) == [False]
