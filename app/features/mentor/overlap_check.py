"""Check the solution-overlap threshold on every content file (fix 2026-10-01).

    python -m app.features.mentor.overlap_check

For each exercise: the reference itself must reach the threshold; the served
starter and a set of generic snippets must stay below it. A generic snippet
that is itself part of the exercise's reference (e.g. creating a lock in the
race-condition exercise) is not generic there and is skipped. Mutants are shown
for information only: they are deliberately wrong code (insecure rewrites, or
the original bug on debug exercises), not near-solutions. Exits 1 if any
exercise fails, so it can gate a release.
"""
import sys

from app.features.content.schema import CONTENT_DIR, load_content_file
from app.features.exercises.starters import student_starter
from app.features.mentor.overlap import OVERLAP_THRESHOLD, code_grams, core_grams, coverage
from app.seed.exercises_seed import EXERCISES

GENERIC = [
    "for i in range(len(nums)):\n    print(nums[i])",
    "result = {}",
    "if x > 0:\n    return True",
    "while left < right:\n    left += 1",
    "def helper(x):\n    return x * 2",
    "s = s.strip().lower()",
    "items.sort()",
    "count = 0\nfor ch in s:\n    count += 1",
    "seen = set()\nif n in seen:\n    print(n)",
    "with lock:\n    counter += 1",
    "try:\n    value = int(text)\nexcept ValueError:\n    value = 0",
    "return len(stack) == 0",
    "import threading\nlock = threading.Lock()",
    "words = text.split()",
    "for key, value in d.items():\n    print(key, value)",
]


def check() -> list[dict]:
    seed = {e["code"]: e for e in EXERCISES}
    rows = []
    for path in sorted(CONTENT_DIR.glob("CP-*.json")):
        content = load_content_file(path)
        ex = seed[content.code]
        starter = student_starter(content.starter_for(ex.get("starter_code", "")), ex.get("kind", "implement"))
        ref = content.reference_solution
        ref_grams = code_grams(ref)
        generic_here = [g for g in GENERIC if not code_grams(g) <= ref_grams]  # part of this solution: not generic
        generic = max(((coverage(ref, starter, [g]), g) for g in generic_here), key=lambda item: item[0])
        mutants = [coverage(ref, starter, [m.code]) for m in content.mutants]
        row = {"code": content.code, "kind": ex.get("kind", "implement"), "core": len(core_grams(ref, starter)),
               "reference": coverage(ref, starter, [ref]), "mutant_min": min(mutants, default=1.0),
               "starter": coverage(ref, starter, [starter]), "generic_max": generic[0],
               "generic_worst": generic[1].splitlines()[0]}
        row["ok"] = (row["core"] > 0 and row["reference"] >= OVERLAP_THRESHOLD
                     and row["starter"] < OVERLAP_THRESHOLD and row["generic_max"] < OVERLAP_THRESHOLD)
        rows.append(row)
    return rows


def main() -> int:
    rows = check()
    print(f"threshold {OVERLAP_THRESHOLD:.0%}")
    print(f"{'code':<7} {'kind':<9} {'core':>4} {'ref':>5} {'mut.min':>7} {'starter':>7} {'generic':>7}  worst generic"
          "   (mut.min: information only)")
    for r in rows:
        flag = "" if r["ok"] else "  <-- FAIL"
        print(f"{r['code']:<7} {r['kind']:<9} {r['core']:>4} {r['reference']:>5.0%} {r['mutant_min']:>7.0%} "
              f"{r['starter']:>7.0%} {r['generic_max']:>7.0%}  {r['generic_worst']}{flag}")
    failed = [r["code"] for r in rows if not r["ok"]]
    print(f"{len(rows) - len(failed)}/{len(rows)} ok" + (f"; failing: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
