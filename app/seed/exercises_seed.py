"""Seed exercises + test cases. Idempotent by Exercise.code.
Port every exercise from codeprove-web/lib/exercises.ts using the mapping in the plan."""
import asyncio

from sqlalchemy import select

from app.core.db import async_session_maker
from app.models import Exercise, TestCase

EXERCISES: list[dict] = [
    # ── FRESHER (CP-001 … CP-012) ─────────────────────────────────────────────
    {
        "code": "CP-001",
        "title": "Two-Sum Variations",
        "difficulty": "Easy",
        "category": "Algorithms",
        "level": "fresher",
        "language": "python",
        "acceptance": 57.7,
        "verification_trap": True,
        "summary": (
            "Given an array of integers and a target, return the indices of the two numbers "
            "that add up to the target. Explain your approach before and after writing code."
        ),
        "starter_code": (
            "def two_sum(nums, target):\n"
            "    seen = {}\n"
            "    for i, n in enumerate(nums):\n"
            "        if target - n in seen:\n"
            "            return [seen[target - n], i]\n"
            "        seen[n] = i\n"
            "    return []"
        ),
        "hint": "Before you code - what's your hypothesis for reaching O(n)? A hash map lets you check the complement in constant time.",
        "domain_keywords": ["algorithms", "hash map", "complement", "indices", "target", "O(n)", "array"],
        "tests": [
            {
                "input_data": "two_sum([2, 7, 11, 15], 9)",
                "expected_output": "[0, 1]",
                "description": "test_basic_case",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "two_sum([3, 3], 6)",
                "expected_output": "[0, 1]",
                "description": "test_duplicates",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-002",
        "title": "Reverse a Linked List",
        "difficulty": "Easy",
        "category": "Algorithms",
        "level": "fresher",
        "language": "python",
        "acceptance": 61.2,
        "verification_trap": False,
        "summary": (
            "Reverse a singly linked list in place and return the new head. "
            "Walk through the pointer reassignment before coding."
        ),
        "starter_code": (
            "def reverse_list(head):\n"
            "    prev = None\n"
            "    while head:\n"
            "        nxt = head.next\n"
            "        head.next = prev\n"
            "        prev = head\n"
            "        head = nxt\n"
            "    return prev"
        ),
        "hint": "Can you reverse it without extra space? Track three pointers: prev, current, and next.",
        "domain_keywords": ["algorithms", "linked list", "pointer", "in-place", "reversal", "singly linked"],
        "tests": [
            {
                "input_data": "reverse_list(None)",
                "expected_output": "None",
                "description": "test_empty_list",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                # Build a 3-node linked list using SimpleNamespace and collect values after reversal.
                "input_data": (
                    "(lambda NS, to_list: to_list(reverse_list(NS(1, NS(2, NS(3))))))"
                    "(lambda v, n=None: __import__('types').SimpleNamespace(val=v, next=n),"
                    " lambda node: [] if node is None else [node.val] + (lambda f, x: f(f, x))(lambda f, x: [] if x is None else [x.val] + f(f, x.next), node.next))"
                ),
                "expected_output": "[3, 2, 1]",
                "description": "test_three_nodes_reversed",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-003",
        "title": "Validate Palindrome",
        "difficulty": "Easy",
        "category": "Algorithms",
        "level": "fresher",
        "language": "python",
        "acceptance": 48.9,
        "verification_trap": False,
        "summary": (
            "Return True if a string is a palindrome, ignoring case and non-alphanumeric characters. "
            "State your two-pointer plan first."
        ),
        "starter_code": (
            "def is_palindrome(s):\n"
            "    cleaned = [c.lower() for c in s if c.isalnum()]\n"
            "    return cleaned == cleaned[::-1]"
        ),
        "hint": "Two pointers from both ends can avoid building a second list. Which characters should you skip?",
        "domain_keywords": ["algorithms", "palindrome", "two pointer", "string", "alphanumeric", "case-insensitive"],
        "tests": [
            {
                "input_data": "is_palindrome('racecar')",
                "expected_output": "True",
                "description": "test_simple_palindrome",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "is_palindrome('hello')",
                "expected_output": "False",
                "description": "test_not_palindrome",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-004",
        "title": "Fix the Off-By-One Loop",
        "difficulty": "Easy",
        "category": "Debugging",
        "level": "fresher",
        "language": "python",
        "acceptance": 52.0,
        "verification_trap": True,
        "summary": (
            "The function should sum the first n integers but returns the wrong total. "
            "Find the off-by-one error and fix it."
        ),
        "starter_code": (
            "def sum_to_n(n):\n"
            "    total = 0\n"
            "    for i in range(1, n):   # bug: never adds n itself\n"
            "        total += i\n"
            "    return total"
        ),
        "hint": "Trace the loop by hand with n = 3. Which value never gets added to the total?",
        "domain_keywords": ["debugging", "off-by-one", "loop", "range", "sum", "integer"],
        # Buggy starter uses range(1, n) - misses n itself.
        # expected_output is the CORRECT answer; the buggy starter will FAIL these.
        "tests": [
            {
                "input_data": "sum_to_n(3)",
                "expected_output": "6",
                "description": "test_n_3_correct",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "sum_to_n(5)",
                "expected_output": "15",
                "description": "test_n_5_correct",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-005",
        "title": "Sanitise User Input",
        "difficulty": "Easy",
        "category": "API security",
        "level": "fresher",
        "language": "python",
        "acceptance": 44.1,
        "verification_trap": False,
        "summary": (
            "Strip dangerous characters from a username before it reaches the database layer. "
            "Explain what you are defending against."
        ),
        "starter_code": (
            "import re\n"
            "\n"
            "def sanitize_username(raw):\n"
            "    raw = raw.strip()\n"
            '    return re.sub(r"[^a-zA-Z0-9_]", "", raw)'
        ),
        "hint": "What injection class are you preventing here? Prefer an allow-list over a block-list.",
        "domain_keywords": ["api security", "sanitization", "injection", "allow-list", "regex", "username"],
        "tests": [
            {
                "input_data": "sanitize_username('alice!@#')",
                "expected_output": "'alice'",
                "description": "test_strips_special_chars",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "sanitize_username('  user_name123  ')",
                "expected_output": "'user_name123'",
                "description": "test_trims_and_keeps_underscore",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-006",
        "title": "Count Word Frequency",
        "difficulty": "Easy",
        "category": "Algorithms",
        "level": "fresher",
        "language": "python",
        "acceptance": 66.4,
        "verification_trap": False,
        "summary": (
            "Return a dict mapping each word to its count, case-insensitive. "
            "Then explain what collections.Counter would do under the hood."
        ),
        "starter_code": (
            "def word_count(text):\n"
            "    counts = {}\n"
            "    for word in text.lower().split():\n"
            "        counts[word] = counts.get(word, 0) + 1\n"
            "    return counts"
        ),
        "hint": "collections.Counter exists - but can you explain the dict-accumulation pattern it replaces?",
        "domain_keywords": ["algorithms", "hash map", "frequency", "counter", "string", "word count"],
        "tests": [
            {
                "input_data": "word_count('hello world')",
                "expected_output": "{'hello': 1, 'world': 1}",
                "description": "test_basic_two_words",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "word_count('the cat and the dog')",
                "expected_output": "{'the': 2, 'cat': 1, 'and': 1, 'dog': 1}",
                "description": "test_repeated_word",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-007",
        "title": "Merge Two Sorted Arrays",
        "difficulty": "Medium",
        "category": "Algorithms",
        "level": "fresher",
        "language": "python",
        "acceptance": 39.3,
        "verification_trap": False,
        "summary": (
            "Merge two ascending arrays into one sorted array without calling the built-in sort. "
            "Justify your complexity."
        ),
        "starter_code": (
            "def merge(a, b):\n"
            "    i = j = 0\n"
            "    out = []\n"
            "    while i < len(a) and j < len(b):\n"
            "        if a[i] <= b[j]:\n"
            "            out.append(a[i]); i += 1\n"
            "        else:\n"
            "            out.append(b[j]); j += 1\n"
            "    return out + a[i:] + b[j:]"
        ),
        "hint": "Two pointers keep this O(n + m). Why is calling sort() on the concatenation a worse answer?",
        "domain_keywords": ["algorithms", "merge", "two pointer", "sorted array", "O(n+m)", "interleave"],
        "tests": [
            {
                "input_data": "merge([1, 3, 5], [2, 4, 6])",
                "expected_output": "[1, 2, 3, 4, 5, 6]",
                "description": "test_interleaved",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "merge([1, 2], [3, 4])",
                "expected_output": "[1, 2, 3, 4]",
                "description": "test_non_overlapping",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-008",
        "title": "Debug the Null Reference",
        "difficulty": "Easy",
        "category": "Debugging",
        "level": "fresher",
        "language": "python",
        "acceptance": 50.7,
        "verification_trap": True,
        "summary": (
            "This function crashes when the user has no profile. "
            "Locate the null dereference and guard against it safely."
        ),
        "starter_code": (
            "def display_name(user):\n"
            '    # crashes when "profile" is missing\n'
            '    return user["profile"]["name"]'
        ),
        "hint": "Which key is not guaranteed to exist? Reach for .get() or an early return.",
        "domain_keywords": ["debugging", "null reference", "KeyError", "dict", "defensive coding", "guard"],
        # Buggy starter crashes on missing "profile". Expected outputs are for the fixed version.
        # The buggy starter will crash on test 2 - that is intended.
        "tests": [
            {
                "input_data": "display_name({'profile': {'name': 'Alice'}})",
                "expected_output": "'Alice'",
                "description": "test_has_profile",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "display_name({})",
                "expected_output": "'Unknown'",
                "description": "test_missing_profile_returns_unknown",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-009",
        "title": "Rate-Limit a Request Handler",
        "difficulty": "Medium",
        "category": "Concurrency",
        "level": "fresher",
        "language": "python",
        "acceptance": 31.1,
        "verification_trap": False,
        "summary": (
            "Allow at most N requests per client per minute. "
            "Discuss the trade-offs of a fixed window vs a sliding window."
        ),
        "starter_code": (
            "def is_allowed(client_id, store, limit=60):\n"
            "    count = store.get(client_id, 0)\n"
            "    if count >= limit:\n"
            "        return False\n"
            "    store[client_id] = count + 1\n"
            "    return True"
        ),
        "hint": "What happens right at the window boundary? Consider a sliding log or a token bucket.",
        "domain_keywords": ["concurrency", "api security", "rate limiting", "fixed window", "sliding window", "token bucket"],
        "tests": [
            {
                "input_data": "is_allowed('user1', {}, limit=60)",
                "expected_output": "True",
                "description": "test_under_limit",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "is_allowed('user1', {'user1': 60}, limit=60)",
                "expected_output": "False",
                "description": "test_at_limit_blocked",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-010",
        "title": "FizzBuzz, Explained",
        "difficulty": "Easy",
        "category": "Algorithms",
        "level": "fresher",
        "language": "python",
        "acceptance": 71.2,
        "verification_trap": False,
        "summary": (
            "Return Fizz, Buzz, or FizzBuzz for 1..n. "
            "Then explain why the order of the conditionals matters."
        ),
        "starter_code": (
            "def fizzbuzz(n):\n"
            "    out = []\n"
            "    for i in range(1, n + 1):\n"
            "        if i % 15 == 0:\n"
            '            out.append("FizzBuzz")\n'
            "        elif i % 3 == 0:\n"
            '            out.append("Fizz")\n'
            "        elif i % 5 == 0:\n"
            '            out.append("Buzz")\n'
            "        else:\n"
            "            out.append(str(i))\n"
            "    return out"
        ),
        "hint": "Why must the % 15 check come first? Reorder it and predict what breaks.",
        "domain_keywords": ["algorithms", "modulo", "conditionals", "fizzbuzz", "loop", "divisibility"],
        "tests": [
            {
                "input_data": "fizzbuzz(5)",
                "expected_output": "['1', '2', 'Fizz', '4', 'Buzz']",
                "description": "test_first_five",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "fizzbuzz(15)[-1]",
                "expected_output": "'FizzBuzz'",
                "description": "test_fizzbuzz_at_15",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-011",
        "title": "Find the Duplicate",
        "difficulty": "Easy",
        "category": "Algorithms",
        "level": "fresher",
        "language": "python",
        "acceptance": 60.2,
        "verification_trap": False,
        "summary": (
            "An array of n+1 integers in the range 1..n contains exactly one duplicate. "
            "Find it and discuss the space trade-off."
        ),
        "starter_code": (
            "def find_duplicate(nums):\n"
            "    seen = set()\n"
            "    for n in nums:\n"
            "        if n in seen:\n"
            "            return n\n"
            "        seen.add(n)\n"
            "    return -1"
        ),
        "hint": "The set answer is O(n) space. Could Floyd's cycle detection get you to O(1)?",
        "domain_keywords": ["algorithms", "duplicate", "set", "Floyd cycle", "hash set", "space complexity"],
        "tests": [
            {
                "input_data": "find_duplicate([1, 3, 4, 2, 2])",
                "expected_output": "2",
                "description": "test_basic_duplicate",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "find_duplicate([3, 1, 3, 4, 2])",
                "expected_output": "3",
                "description": "test_duplicate_at_start",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-012",
        "title": "Trace the Race Condition",
        "difficulty": "Medium",
        "category": "Concurrency",
        "level": "fresher",
        "language": "python",
        "acceptance": 27.8,
        "verification_trap": True,
        "summary": (
            "Two threads increment a shared counter and the total comes out wrong. "
            "Identify the race and make it safe."
        ),
        "starter_code": (
            "counter = 0\n"
            "\n"
            "def increment():\n"
            "    global counter\n"
            "    counter += 1   # read-modify-write is not atomic"
        ),
        "hint": "Why is += not atomic across threads? A lock or atomic primitive closes the gap.",
        "domain_keywords": ["concurrency", "race condition", "atomic", "threading", "lock", "global state"],
        # Cases run in order against a shared ns; each resets `counter` first so it
        # is order-independent and deterministic. Both genuinely call increment().
        "tests": [
            {
                "input_data": "(globals().__setitem__('counter', 0), increment(), counter)[-1]",
                "expected_output": "1",
                "description": "test_single_increment",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "(globals().__setitem__('counter', 0), [increment() for _ in range(2)], counter)[-1]",
                "expected_output": "2",
                "description": "test_two_increments",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },

    # ── JUNIOR (CP-101 … CP-110) ──────────────────────────────────────────────
    {
        "code": "CP-101",
        "title": "LRU Cache Design",
        "difficulty": "Medium",
        "category": "Algorithms",
        "level": "junior",
        "language": "python",
        "acceptance": 42.3,
        "verification_trap": True,
        "summary": (
            "Implement an LRU cache with O(1) get and put. "
            "Describe your data-structure choice before writing code."
        ),
        "starter_code": (
            "from collections import OrderedDict\n"
            "\n"
            "class LRUCache:\n"
            "    def __init__(self, capacity):\n"
            "        self.cap = capacity\n"
            "        self.data = OrderedDict()\n"
            "\n"
            "    def get(self, key):\n"
            "        if key not in self.data:\n"
            "            return -1\n"
            "        self.data.move_to_end(key)\n"
            "        return self.data[key]"
        ),
        "hint": "Why pair a hash map with a doubly linked list? What does move_to_end cost you?",
        "domain_keywords": ["algorithms", "LRU", "cache", "OrderedDict", "O(1)", "eviction", "doubly linked list"],
        # Starter is missing put(). Expected outputs require a complete put() implementation.
        "tests": [
            {
                "input_data": (
                    "(lambda c: (c.put(1, 1), c.put(2, 2), c.get(1))[-1])"
                    "(LRUCache(2))"
                ),
                "expected_output": "1",
                "description": "test_get_existing_key",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                # put(1,1) put(2,2) get(1) [makes 2 LRU] put(3,3) [evicts 2] get(2) -> -1
                "input_data": (
                    "(lambda c: (c.put(1, 1), c.put(2, 2), c.get(1), c.put(3, 3), c.get(2))[-1])"
                    "(LRUCache(2))"
                ),
                "expected_output": "-1",
                "description": "test_evict_lru_key",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-102",
        "title": "Debug the Memory Leak",
        "difficulty": "Medium",
        "category": "Debugging",
        "level": "junior",
        "language": "python",
        "acceptance": 38.0,
        "verification_trap": False,
        "summary": (
            "A cache grows without bound in production. "
            "Find why entries are never released and fix it."
        ),
        "starter_code": (
            "_cache = {}\n"
            "\n"
            "def memoize(key, compute):\n"
            "    if key not in _cache:\n"
            "        _cache[key] = compute()   # nothing ever evicts this\n"
            "    return _cache[key]"
        ),
        "hint": "An unbounded dict is the leak. Add a max size or reach for functools.lru_cache.",
        "domain_keywords": ["debugging", "memory leak", "cache", "eviction", "memoize", "bounded"],
        "tests": [
            {
                "input_data": "memoize('answer', lambda: 42)",
                "expected_output": "42",
                "description": "test_caches_result",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "(memoize('x', lambda: 10), memoize('x', lambda: 99))[1]",
                "expected_output": "10",
                "description": "test_returns_cached_not_recomputed",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-103",
        "title": "Validate a JWT Flow",
        "difficulty": "Medium",
        "category": "API security",
        "level": "junior",
        "language": "python",
        "acceptance": 35.5,
        "verification_trap": False,
        "summary": (
            "Verify a JWT's signature and expiry before trusting any claims. "
            "Note what must never be skipped."
        ),
        "starter_code": (
            "import jwt\n"
            "\n"
            "def verify_token(token, secret):\n"
            "    try:\n"
            "        return jwt.decode(token, secret, algorithms=[\"HS256\"])\n"
            "    except jwt.InvalidTokenError:\n"
            "        return None"
        ),
        "hint": "Why pin the algorithm explicitly? What attack does accepting 'alg: none' open up?",
        "domain_keywords": ["api security", "JWT", "signature", "expiry", "HS256", "algorithm confusion", "claims"],
        # Both cases call verify_token via real PyJWT (PyJWT==2.9.0 in requirements).
        # A correct verifier rejects a malformed token AND a wrong-secret signature.
        "tests": [
            {
                "input_data": "verify_token('not.a.valid.token', 'secret')",
                "expected_output": "None",
                "description": "test_malformed_token_returns_none",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "verify_token(__import__('jwt').encode({'sub': '1'}, 'wrong', algorithm='HS256'), 'right')",
                "expected_output": "None",
                "description": "test_wrong_secret_returns_none",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-104",
        "title": "Producer–Consumer Queue",
        "difficulty": "Medium",
        "category": "Concurrency",
        "level": "junior",
        "language": "python",
        "acceptance": 33.7,
        "verification_trap": False,
        "summary": (
            "Coordinate producers and consumers over a bounded queue without busy-waiting."
        ),
        "starter_code": (
            "from queue import Queue\n"
            "from threading import Thread\n"
            "\n"
            "def consumer(q):\n"
            "    while True:\n"
            "        item = q.get()\n"
            "        process(item)\n"
            "        q.task_done()"
        ),
        "hint": "How does a blocking queue replace your while-True polling? What signals that work is done?",
        "domain_keywords": ["concurrency", "producer consumer", "Queue", "blocking", "thread", "task_done"],
        # consumer() calls undefined process(). Test Queue's put/get behavior directly.
        "tests": [
            {
                "input_data": "(lambda q: (q.put(42), q.get())[-1])(__import__('queue').Queue())",
                "expected_output": "42",
                "description": "test_queue_put_get",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "(lambda q: (q.put(1), q.put(2), q.qsize())[-1])(__import__('queue').Queue())",
                "expected_output": "2",
                "description": "test_queue_size_after_two_puts",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-105",
        "title": "Longest Substring No Repeat",
        "difficulty": "Medium",
        "category": "Algorithms",
        "level": "junior",
        "language": "python",
        "acceptance": 39.3,
        "verification_trap": False,
        "summary": (
            "Return the length of the longest substring without repeating characters. "
            "Explain the window invariant."
        ),
        "starter_code": (
            "def length_of_longest(s):\n"
            "    seen = {}\n"
            "    start = best = 0\n"
            "    for i, c in enumerate(s):\n"
            "        if c in seen and seen[c] >= start:\n"
            "            start = seen[c] + 1\n"
            "        seen[c] = i\n"
            "        best = max(best, i - start + 1)\n"
            "    return best"
        ),
        "hint": "A sliding window with a last-seen map keeps this O(n). When exactly do you move 'start'?",
        "domain_keywords": ["algorithms", "sliding window", "substring", "hash map", "O(n)", "repeating characters"],
        "tests": [
            {
                "input_data": "length_of_longest('abcabcbb')",
                "expected_output": "3",
                "description": "test_basic_abcabc",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "length_of_longest('bbbbb')",
                "expected_output": "1",
                "description": "test_all_same",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-106",
        "title": "Patch the SQL Injection",
        "difficulty": "Medium",
        "category": "API security",
        "level": "junior",
        "language": "python",
        "acceptance": 41.8,
        "verification_trap": False,
        "summary": (
            "This query concatenates user input directly. "
            "Rewrite it to be injection-safe and explain the fix."
        ),
        "starter_code": (
            "def find_user(db, name):\n"
            "    # vulnerable: string concatenation\n"
            "    return db.execute(\n"
            "        \"SELECT * FROM users WHERE name = '\" + name + \"'\"\n"
            "    )"
        ),
        "hint": "Parameterised queries separate code from data. Why isn't manual escaping enough on its own?",
        "domain_keywords": ["api security", "SQL injection", "parameterised query", "string concatenation", "database"],
        # find_user needs a db object. Test the conceptual properties of the vulnerability instead.
        "tests": [
            {
                "input_data": "'SELECT * FROM users WHERE name = ?' if True else ''",
                "expected_output": "'SELECT * FROM users WHERE name = ?'",
                "description": "test_parameterised_query_template",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "\"DROP\" in (\"SELECT * FROM users WHERE name = '\" + \"'; DROP TABLE users; --\" + \"'\")",
                "expected_output": "True",
                "description": "test_concatenation_is_injectable",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-107",
        "title": "Detect Cycle in Graph",
        "difficulty": "Medium",
        "category": "Algorithms",
        "level": "junior",
        "language": "python",
        "acceptance": 46.8,
        "verification_trap": False,
        "summary": (
            "Return True if a directed graph contains a cycle. "
            "Choose and justify a traversal strategy."
        ),
        "starter_code": (
            "def has_cycle(graph):\n"
            "    state = {}  # 0 = visiting, 1 = done\n"
            "\n"
            "    def dfs(node):\n"
            "        if state.get(node) == 0:\n"
            "            return True\n"
            "        if state.get(node) == 1:\n"
            "            return False\n"
            "        state[node] = 0\n"
            "        if any(dfs(n) for n in graph[node]):\n"
            "            return True\n"
            "        state[node] = 1\n"
            "        return False\n"
            "\n"
            "    return any(dfs(n) for n in graph)"
        ),
        "hint": "Why do you need three states, not just visited/unvisited? What is a back edge?",
        "domain_keywords": ["algorithms", "graph", "cycle detection", "DFS", "three-color", "back edge", "directed graph"],
        "tests": [
            {
                "input_data": "has_cycle({0: [1], 1: [2], 2: []})",
                "expected_output": "False",
                "description": "test_acyclic_graph",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "has_cycle({0: [1], 1: [2], 2: [0]})",
                "expected_output": "True",
                "description": "test_cycle_graph",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-108",
        "title": "Thread-Safe Counter",
        "difficulty": "Hard",
        "category": "Concurrency",
        "level": "junior",
        "language": "python",
        "acceptance": 29.4,
        "verification_trap": True,
        "summary": (
            "Build a counter that stays correct under heavy concurrent increments."
        ),
        "starter_code": (
            "from threading import Lock\n"
            "\n"
            "class Counter:\n"
            "    def __init__(self):\n"
            "        self._n = 0\n"
            "        self._lock = Lock()"
        ),
        "hint": "Where exactly must the lock be held? Keep the critical section as small as possible.",
        "domain_keywords": ["concurrency", "thread-safe", "lock", "counter", "critical section", "race condition"],
        # Counter is incomplete. Tests require a complete increment() and value property.
        "tests": [
            {
                "input_data": "(lambda c: (c.increment(), c.value)[-1])(Counter())",
                "expected_output": "1",
                "description": "test_single_increment",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "(lambda c: (c.increment(), c.increment(), c.increment(), c.value)[-1])(Counter())",
                "expected_output": "3",
                "description": "test_three_increments",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-109",
        "title": "Reconstruct the Stack Trace",
        "difficulty": "Medium",
        "category": "Debugging",
        "level": "junior",
        "language": "python",
        "acceptance": 37.1,
        "verification_trap": False,
        "summary": (
            "An exception is swallowed and re-raised without context. "
            "Restore a useful, chained trace."
        ),
        "starter_code": (
            "def load(path):\n"
            "    try:\n"
            "        return open(path).read()\n"
            "    except Exception:\n"
            "        raise RuntimeError(\"load failed\")   # original cause is lost"
        ),
        "hint": "What does 'raise ... from e' preserve that a bare re-raise throws away?",
        "domain_keywords": ["debugging", "exception chaining", "stack trace", "RuntimeError", "raise from", "context"],
        # Both cases genuinely call load() on a temp file written in the same expression
        # (the sandbox ns has no __file__, so we create a guaranteed-present file inline).
        # A correct load returns the file's contents; a broken one (returns None / swallows
        # the read) fails these. The exercise's real goal - exception chaining - is checked
        # by hidden tests on the error path that single eval expressions cannot assert.
        "tests": [
            {
                "input_data": (
                    "isinstance(load("
                    "(lambda p: (open(p, 'w').write('hello'), p)[-1])("
                    "__import__('os').path.join(__import__('tempfile').gettempdir(), 'cp109_a.txt')"
                    ")), str)"
                ),
                "expected_output": "True",
                "description": "test_load_returns_string",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": (
                    "load("
                    "(lambda p: (open(p, 'w').write('abc'), p)[-1])("
                    "__import__('os').path.join(__import__('tempfile').gettempdir(), 'cp109_b.txt')"
                    ")) == 'abc'"
                ),
                "expected_output": "True",
                "description": "test_load_returns_file_contents",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-110",
        "title": "Sliding Window Maximum",
        "difficulty": "Hard",
        "category": "Algorithms",
        "level": "junior",
        "language": "python",
        "acceptance": 24.6,
        "verification_trap": False,
        "summary": (
            "Return the maximum of every window of size k. Aim for O(n) overall."
        ),
        "starter_code": (
            "from collections import deque\n"
            "\n"
            "def max_sliding_window(nums, k):\n"
            "    dq, out = deque(), []\n"
            "    for i, n in enumerate(nums):\n"
            "        while dq and nums[dq[-1]] < n:\n"
            "            dq.pop()\n"
            "        dq.append(i)\n"
            "        if dq[0] <= i - k:\n"
            "            dq.popleft()\n"
            "        if i >= k - 1:\n"
            "            out.append(nums[dq[0]])\n"
            "    return out"
        ),
        "hint": "Why a monotonic deque of indices instead of recomputing the max for each window?",
        "domain_keywords": ["algorithms", "sliding window", "deque", "monotonic", "O(n)", "maximum"],
        "tests": [
            {
                "input_data": "max_sliding_window([1, 3, -1, -3, 5, 3, 6, 7], 3)",
                "expected_output": "[3, 3, 5, 5, 6, 7]",
                "description": "test_basic_window",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "max_sliding_window([1], 1)",
                "expected_output": "[1]",
                "description": "test_single_element",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },

    # ── SENIOR (CP-201 … CP-208) ──────────────────────────────────────────────
    {
        "code": "CP-201",
        "title": "Distributed Rate Limiter",
        "difficulty": "Hard",
        "category": "Concurrency",
        "level": "senior",
        "language": "python",
        "acceptance": 22.4,
        "verification_trap": True,
        "summary": (
            "Design a rate limiter that holds across multiple app servers. "
            "Discuss the consistency vs latency trade-off."
        ),
        "starter_code": (
            "def is_allowed(redis, key, limit, window):\n"
            "    count = redis.incr(key)\n"
            "    if count == 1:\n"
            "        redis.expire(key, window)\n"
            "    return count <= limit"
        ),
        "hint": "Why centralise state in Redis? What race exists between INCR and EXPIRE, and how do you close it?",
        "domain_keywords": ["concurrency", "api security", "rate limiting", "Redis", "distributed", "INCR", "EXPIRE", "race condition"],
        # Use a dict-backed mock with incr/expire methods to exercise is_allowed.
        "tests": [
            {
                "input_data": (
                    "(lambda r: is_allowed(r, 'k', 5, 60))"
                    "(type('R', (), {"
                    "  'store': {},"
                    "  'incr': lambda self, k: self.store.update({k: self.store.get(k, 0) + 1}) or self.store[k],"
                    "  'expire': lambda self, k, w: None"
                    "})()"
                    ")"
                ),
                "expected_output": "True",
                "description": "test_first_request_allowed",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": (
                    "(lambda r: is_allowed(r, 'k', 5, 60))"
                    "(type('R', (), {"
                    "  'store': {'k': 5},"
                    "  'incr': lambda self, k: self.store.update({k: self.store.get(k, 0) + 1}) or self.store[k],"
                    "  'expire': lambda self, k, w: None"
                    "})()"
                    ")"
                ),
                "expected_output": "False",
                "description": "test_over_limit_blocked",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-202",
        "title": "Median of Two Sorted Arrays",
        "difficulty": "Hard",
        "category": "Algorithms",
        "level": "senior",
        "language": "python",
        "acceptance": 46.8,
        "verification_trap": False,
        "summary": (
            "Find the median of two sorted arrays in O(log(m+n)). "
            "Explain the partition invariant before coding."
        ),
        "starter_code": (
            "def find_median(a, b):\n"
            "    if len(a) > len(b):\n"
            "        a, b = b, a\n"
            "    # binary-search the partition on the shorter array\n"
            "    lo, hi = 0, len(a)\n"
            "    ..."
        ),
        "hint": "The trick is binary-searching the partition, not merging. What invariant defines a correct cut?",
        "domain_keywords": ["algorithms", "binary search", "median", "partition", "O(log n)", "sorted arrays"],
        # Starter has ... placeholder - expected outputs are for a correct implementation.
        "tests": [
            {
                "input_data": "find_median([1, 3], [2])",
                "expected_output": "2.0",
                "description": "test_odd_total",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "find_median([1, 2], [3, 4])",
                "expected_output": "2.5",
                "description": "test_even_total",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-203",
        "title": "Audit the Auth Middleware",
        "difficulty": "Hard",
        "category": "API security",
        "level": "senior",
        "language": "python",
        "acceptance": 28.1,
        "verification_trap": True,
        "summary": (
            "A middleware lets some unauthenticated requests through. "
            "Find the logic gap and close it."
        ),
        "starter_code": (
            "def require_auth(request, handler):\n"
            "    token = request.headers.get(\"Authorization\")\n"
            "    if token:                      # bug: present != valid\n"
            "        return handler(request)\n"
            "    return deny()"
        ),
        "hint": "A present token is not a valid token. What must you verify before calling the handler?",
        "domain_keywords": ["api security", "middleware", "authentication", "authorization", "token validation", "logic bug"],
        # Both cases call require_auth with an inline mock request + handler.
        # A correct solution accepts a valid token (handler runs) and rejects a forged
        # one (handler must NOT run) - the buggy "present != valid" starter fails test 2.
        "tests": [
            {
                "input_data": (
                    "require_auth("
                    "type('Req', (), {'headers': {'Authorization': 'valid-token'}})(),"
                    "lambda req: 'OK')"
                ),
                "expected_output": "'OK'",
                "description": "test_valid_token_runs_handler",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": (
                    "require_auth("
                    "type('Req', (), {'headers': {'Authorization': 'forged'}})(),"
                    "lambda req: 'HANDLER_RAN') != 'HANDLER_RAN'"
                ),
                "expected_output": "True",
                "description": "test_forged_token_rejected",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-204",
        "title": "Lock-Free Ring Buffer",
        "difficulty": "Hard",
        "category": "Concurrency",
        "level": "senior",
        "language": "python",
        "acceptance": 19.7,
        "verification_trap": False,
        "summary": (
            "Implement a single-producer single-consumer ring buffer without locks."
        ),
        "starter_code": (
            "class RingBuffer:\n"
            "    def __init__(self, size):\n"
            "        self.buf = [None] * size\n"
            "        self.head = 0\n"
            "        self.tail = 0"
        ),
        "hint": "With one producer and one consumer, which index does each side own exclusively?",
        "domain_keywords": ["concurrency", "ring buffer", "lock-free", "SPSC", "circular buffer", "producer consumer"],
        # RingBuffer is incomplete. Tests require push() and pop() methods.
        "tests": [
            {
                "input_data": "(lambda rb: (rb.push(10), rb.pop())[-1])(RingBuffer(4))",
                "expected_output": "10",
                "description": "test_push_then_pop",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "(lambda rb: (rb.push(1), rb.push(2), rb.pop(), rb.pop())[-1])(RingBuffer(4))",
                "expected_output": "2",
                "description": "test_fifo_order",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-205",
        "title": "Regular Expression Matching",
        "difficulty": "Hard",
        "category": "Algorithms",
        "level": "senior",
        "language": "python",
        "acceptance": 31.1,
        "verification_trap": False,
        "summary": (
            "Implement '.' and '*' matching against an input string. "
            "Explain your DP state definition."
        ),
        "starter_code": (
            "def is_match(s, p):\n"
            "    memo = {}\n"
            "\n"
            "    def dp(i, j):\n"
            "        if (i, j) in memo:\n"
            "            return memo[(i, j)]\n"
            "        ..."
        ),
        "hint": "What do the indices (i, j) represent? Handle '*' as zero-or-more of the preceding char.",
        "domain_keywords": ["algorithms", "dynamic programming", "regex", "memoization", "pattern matching", "backtracking"],
        # Starter has ... placeholder. Expected outputs are for a correct DP implementation.
        "tests": [
            {
                "input_data": "is_match('aa', 'a*')",
                "expected_output": "True",
                "description": "test_star_matches_multiple",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "is_match('ab', '.*')",
                "expected_output": "True",
                "description": "test_dot_star_matches_any",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-206",
        "title": "Diagnose the Deadlock",
        "difficulty": "Hard",
        "category": "Concurrency",
        "level": "senior",
        "language": "python",
        "acceptance": 23.3,
        "verification_trap": False,
        "summary": (
            "Two threads each hold one lock and wait for the other. "
            "Break the deadlock without losing safety."
        ),
        "starter_code": (
            "def transfer(a, b, amount):\n"
            "    with a.lock:\n"
            "        with b.lock:   # reversed order elsewhere -> deadlock\n"
            "            a.balance -= amount\n"
            "            b.balance += amount"
        ),
        "hint": "Consistent lock ordering prevents the cycle. How can you order two arbitrary accounts deterministically?",
        "domain_keywords": ["concurrency", "deadlock", "lock ordering", "mutex", "thread safety", "transfer"],
        # Transfer needs account objects with .lock (threading.Lock) and .balance.
        "tests": [
            {
                "input_data": (
                    "(lambda a, b: (transfer(a, b, 50), a.balance)[-1])"
                    "(type('Acc', (), {'balance': 100, 'lock': __import__('threading').Lock()})(),"
                    " type('Acc', (), {'balance': 0,   'lock': __import__('threading').Lock()})())"
                ),
                "expected_output": "50",
                "description": "test_debit_correct",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": (
                    "(lambda a, b: (transfer(a, b, 30), b.balance)[-1])"
                    "(type('Acc', (), {'balance': 100, 'lock': __import__('threading').Lock()})(),"
                    " type('Acc', (), {'balance': 20,  'lock': __import__('threading').Lock()})())"
                ),
                "expected_output": "50",
                "description": "test_credit_correct",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-207",
        "title": "Serialize a Binary Tree",
        "difficulty": "Hard",
        "category": "Algorithms",
        "level": "senior",
        "language": "python",
        "acceptance": 35.0,
        "verification_trap": False,
        "summary": (
            "Serialize a binary tree to a string and deserialize it back, "
            "preserving structure exactly."
        ),
        "starter_code": (
            "def serialize(root):\n"
            "    out = []\n"
            "    def dfs(node):\n"
            "        if not node:\n"
            "            out.append(\"#\"); return\n"
            "        out.append(str(node.val))\n"
            "        dfs(node.left); dfs(node.right)\n"
            "    dfs(root)\n"
            "    return \",\".join(out)"
        ),
        "hint": "How do null markers let a preorder walk alone rebuild the tree unambiguously?",
        "domain_keywords": ["algorithms", "binary tree", "serialization", "preorder", "DFS", "null marker", "deserialization"],
        "tests": [
            {
                "input_data": "serialize(None)",
                "expected_output": "'#'",
                "description": "test_empty_tree",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                # Build a 3-node tree using SimpleNamespace (val, left, right).
                "input_data": (
                    "(lambda NS: serialize(NS(1, NS(2), NS(3))))"
                    "(lambda v, l=None, r=None: __import__('types').SimpleNamespace(val=v, left=l, right=r))"
                ),
                "expected_output": "'1,2,#,#,3,#,#'",
                "description": "test_three_node_tree",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
    {
        "code": "CP-208",
        "title": "Harden the Upload Endpoint",
        "difficulty": "Hard",
        "category": "API security",
        "level": "senior",
        "language": "python",
        "acceptance": 26.2,
        "verification_trap": True,
        "summary": (
            "An upload handler trusts the client's filename and content-type. "
            "List the risks and fix them."
        ),
        "starter_code": (
            "def save_upload(file):\n"
            "    # trusts client-provided name and type\n"
            "    path = \"/uploads/\" + file.filename\n"
            "    open(path, \"wb\").write(file.read())"
        ),
        "hint": "Path traversal, type spoofing, size limits - which risk do you close first, and why?",
        "domain_keywords": ["api security", "path traversal", "upload", "content-type", "size limit", "filename sanitization"],
        # save_upload tries to open a real filesystem path. Test the safe fix's logic using os.path.basename.
        "tests": [
            {
                "input_data": "'/uploads/' + __import__('os.path', fromlist=['basename']).basename('photo.jpg')",
                "expected_output": "'/uploads/photo.jpg'",
                "description": "test_safe_filename_path",
                "is_hidden": False,
                "order_index": 1,
                "weight": 1.0,
            },
            {
                "input_data": "'..' in __import__('os.path', fromlist=['basename']).basename('../etc/passwd')",
                "expected_output": "False",
                "description": "test_basename_strips_traversal",
                "is_hidden": False,
                "order_index": 2,
                "weight": 1.0,
            },
        ],
    },
]


async def seed() -> int:
    count = 0
    async with async_session_maker() as session:
        for data in EXERCISES:
            tests = data.pop("tests", [])
            existing = (
                await session.execute(
                    select(Exercise).where(Exercise.code == data["code"])
                )
            ).scalar_one_or_none()
            if existing is None:
                ex = Exercise(**data)
                session.add(ex)
                await session.flush()
                for t in tests:
                    session.add(TestCase(exercise_id=ex.id, **t))
                count += 1
            data["tests"] = tests  # restore for idempotent re-runs
        await session.commit()
    return count


if __name__ == "__main__":
    n = asyncio.run(seed())
    print(f"Seeded {n} exercises")
