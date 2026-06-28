from app.features.exercises.starters import student_safe_starter


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
