# P1.1 Content Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give every exercise a reviewed reference solution, 5–8 categorised hidden tests and a bank of 3–5 single-line mutants, stored as reviewable JSON in the repo and synced into the DB only after team approval — without ever leaking hidden tests to students.

**Architecture:** One JSON file per exercise under `content/exercises/`. A pydantic schema parses it; an async validator proves it in the subprocess sandbox (reference passes everything, every mutant is killable but plausible, debug starters fail); a sync command upserts approved, valid files into `exercises`, `test_cases` (new `category` column) and a new `exercise_mutants` table. Leak guards make the student-facing endpoints ignore hidden tests before any exist.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, pydantic v2, pytest; bash for the backup scripts.

**Design:** `docs/superpowers/specs/2026-09-24-p1-design.md` (section P1.1). Roadmap: `docs/superpowers/specs/2026-09-24-scoring-roadmap.md`.

---

## Roadmap traceability

| Item | Task(s) |
|---|---|
| [2] Reference solution, 5–8 categorised hidden tests, mutant bank for 30 exercises | 2, 4, 5, 6, 7, 9 |
| Leak guards required before hidden tests exist (design P1.1) | 3 |
| Team review gate (4 members, LLM drafts) | 6, 8, 10 |
| (carried over) `restore_db.sh` restores a local file without S3 config | 1 |

## Conventions

- Worktree: `codeprove-backend/.claude/worktrees/ai-scoring-feedback-issues-f1bc15`, new branch `feat/p1-1-content-pipeline` from `origin/main`.
- Tests: `../../../.venv/Scripts/python.exe -m pytest -q` (baseline on `main`: 143 passed, 2 skipped).
- Code in content files is stored as **arrays of lines** so GitHub diffs are readable; `bug_line` is 1-based.
- `expected` is compared by the sandbox against `repr(return value)` (or the printed stdout): `"6"`, `"'abc'"`, `"[1, 2]"`, `"True"`, `"None"`.

---

### Task 1: `restore_db.sh` restores a local file without S3 config

**Files:** Modify `scripts/lib_db_backup.sh`, `scripts/backup_db.sh`, `scripts/restore_db.sh`

**Step 1: Reproduce.** With Docker running, create a throwaway DB + stand-in backend and an env file **without** `BACKUP_S3_BUCKET` (bash):

```bash
docker run -d --name cp_rt_db -e POSTGRES_USER=codeprove -e POSTGRES_PASSWORD=x -e POSTGRES_DB=codeprove postgres:16
docker run -d --name cp_rt_backend postgres:16-alpine sleep infinity
sleep 5 && docker exec cp_rt_db psql -U codeprove -d codeprove -q -c "CREATE TABLE t(x int); INSERT INTO t VALUES (1),(2);"
docker exec cp_rt_db pg_dump -U codeprove -d codeprove -Fc > /tmp/rt.dump
printf 'POSTGRES_USER=codeprove\nPOSTGRES_DB=codeprove\n' > /tmp/rt.env
echo codeprove | ENV_FILE=/tmp/rt.env DB_CONTAINER=cp_rt_db BACKEND_CONTAINER=cp_rt_backend HOME=/tmp bash scripts/restore_db.sh restore /tmp/rt.dump
```

Expected (bug): `ERROR: BACKUP_S3_BUCKET is not set`.

**Step 2: Fix.** In `scripts/lib_db_backup.sh`, delete the line
`[[ -n "$S3_BUCKET" ]] || die "BACKUP_S3_BUCKET is not set (in .env or the environment)"` from `load_config` and add below it:

```bash
# Only operations that talk to S3 need a bucket; restoring a local file does not.
require_s3() {
  [[ -n "$S3_BUCKET" ]] || die "BACKUP_S3_BUCKET is not set (in .env or the environment)"
}
```

- `scripts/backup_db.sh`: call `require_s3` right after `load_config` in `main`.
- `scripts/restore_db.sh`: call `require_s3` as the first line of `list_keys` and of `fetch`; move `aws` out of the global `require_cmds` in `main` (`require_cmds docker sha256sum join`) and call `require_cmds aws` inside `require_s3`'s callers (`list_keys`, `fetch`).

**Step 3: Verify** the Step 1 command now ends with `restore OK`, then `docker exec cp_rt_db psql -U codeprove -d codeprove -At -c "select count(*) from t"` → `2`. Re-run the 12 scenarios from PR #9 if convenient (at least: backup, verify latest, restore KEY with the fake `aws` stub). Clean up: `docker rm -f cp_rt_db cp_rt_backend`.

**Step 4: Commit**

```bash
git add scripts/lib_db_backup.sh scripts/backup_db.sh scripts/restore_db.sh
git commit -m "fix(ops): restoring a local dump no longer requires S3 config"
```

---

### Task 2: Schema — test categories and the mutant table

**Files:**
- Create: `app/models/exercise_mutant.py`, `alembic/versions/b4e6a8c0d2f1_test_categories_and_mutants.py`
- Modify: `app/models/test_case.py`, `app/models/__init__.py`
- Test: `tests/test_models.py`

**Step 1: Failing test** (append to `tests/test_models.py`)

```python
async def test_mutants_and_test_categories_persist(db_session):
    from app.models import Exercise, ExerciseMutant, TestCase

    ex = Exercise(code="CP-990", title="t", difficulty="Easy", category="c", level="fresher",
                  language="python", summary="s", starter_code="x", hint="h", domain_keywords=[])
    db_session.add(ex)
    await db_session.flush()
    db_session.add(TestCase(exercise_id=ex.id, input_data="f(0)", expected_output="0",
                            description="zero", category="boundary", is_hidden=True, order_index=1))
    db_session.add(ExerciseMutant(exercise_id=ex.id, code="def f(n):\n    return 1", bug_line=2,
                                  bug_type="wrong-constant", note_vi="v", note_en="e", order_index=1))
    await db_session.commit()

    from sqlalchemy import select
    tc = (await db_session.execute(select(TestCase))).scalar_one()
    mut = (await db_session.execute(select(ExerciseMutant))).scalar_one()
    assert tc.category == "boundary"
    assert mut.bug_line == 2 and mut.exercise_id == ex.id
```

(`pytest.ini` sets `asyncio_mode = auto`, so async tests need no marker.)

**Step 2:** Run `../../../.venv/Scripts/python.exe -m pytest tests/test_models.py -q` → FAIL (`ImportError: ExerciseMutant`).

**Step 3: Implement**

`app/models/exercise_mutant.py`:

```python
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ExerciseMutant(Base):
    """A copy of the reference solution with exactly one line broken.

    Used by P2 for mutation-testing student tests and as the Ciel trap bank.
    """

    __tablename__ = "exercise_mutants"

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(Text)
    bug_line: Mapped[int] = mapped_column(Integer)  # 1-based
    bug_type: Mapped[str] = mapped_column(String(32))
    note_vi: Mapped[str] = mapped_column(Text, default="")
    note_en: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
```

`app/models/test_case.py`: add `String` to the sqlalchemy import and the column

```python
    # happy | boundary | edge | error (None for legacy seed rows).
    category: Mapped[str | None] = mapped_column(String(16), nullable=True)
```

`app/models/__init__.py`: import `ExerciseMutant` from `app.models.exercise_mutant` and add it to `__all__`.

`alembic/versions/b4e6a8c0d2f1_test_categories_and_mutants.py`:

```python
"""test case categories and exercise mutant bank

Revision ID: b4e6a8c0d2f1
Revises: f2c4d6e8a1b3
Create Date: 2026-09-24 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b4e6a8c0d2f1"
down_revision: Union[str, None] = "f2c4d6e8a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_cases", sa.Column("category", sa.String(length=16), nullable=True))
    op.create_table(
        "exercise_mutants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("bug_line", sa.Integer(), nullable=False),
        sa.Column("bug_type", sa.String(length=32), nullable=False),
        sa.Column("note_vi", sa.Text(), nullable=False, server_default=""),
        sa.Column("note_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_exercise_mutants_exercise_id", "exercise_mutants", ["exercise_id"])


def downgrade() -> None:
    op.drop_index("ix_exercise_mutants_exercise_id", table_name="exercise_mutants")
    op.drop_table("exercise_mutants")
    op.drop_column("test_cases", "category")
```

**Step 4:** Tests pass; then check upgrade → downgrade → upgrade on a throwaway Postgres 16 exactly like P0 Task 7 Step 5 (port 55432, `alembic current` ends at `b4e6a8c0d2f1`).

**Step 5: Commit** — `feat(content): add test categories and exercise mutant table`

---

### Task 3: Leak guards — students never see hidden tests

**Files:** Modify `app/features/exercises/service.py` (`get_detail` tests query), `app/features/attempts/router.py` (`run` cases query). Test: `tests/test_run_telemetry.py`, `tests/test_exercises.py`.

**Step 1: Failing tests**

Append to `tests/test_exercises.py`:

```python
async def test_detail_lists_visible_tests_only(client, db_session, auth_headers):
    from app.models import Exercise, TestCase

    ex = Exercise(code="CP-903", title="t", difficulty="Easy", category="c", level="fresher",
                  language="python", summary="s", starter_code="def f(): pass", hint="", domain_keywords=[])
    db_session.add(ex); await db_session.flush()
    db_session.add(TestCase(exercise_id=ex.id, description="shown", is_hidden=False, order_index=1))
    db_session.add(TestCase(exercise_id=ex.id, description="secret_edge_case", is_hidden=True, order_index=2))
    await db_session.commit()

    body = (await client.get("/api/exercises/CP-903", headers=auth_headers)).json()
    assert body["tests"] == ["shown"]
```

Append to `tests/test_run_telemetry.py`:

```python
async def test_run_executes_visible_tests_only(client, db_session, auth_headers):
    from app.models import TestCase

    aid = await _attempt(client, db_session, auth_headers)   # 2 visible cases
    ex_id = (await db_session.execute(select(TestCase.exercise_id))).scalars().first()
    db_session.add(TestCase(exercise_id=ex_id, input_data="double(-1)", expected_output="-2",
                            description="secret_negative", is_hidden=True, order_index=3))
    await db_session.commit()

    r = await client.post(f"/api/attempts/{aid}/run", headers=auth_headers,
                          json={"source_code": "def double(x):\n    return x + x", "run_tests": True})
    body = r.json()
    assert body["total"] == 2
    assert all(c["name"] != "secret_negative" for c in body["cases"])
```

**Step 2:** Both FAIL.

**Step 3: Implement.** Add `TestCase.is_hidden.is_(False)` to the `where(...)` of both queries, with a one-line comment: `# Hidden tests only run at submit (P1.2); never expose their names or results here.`

**Step 4:** Full suite passes.

**Step 5: Commit** — `fix(exercises): never expose hidden tests in detail or /run`

---

### Task 4: Content file schema

**Files:** Create `app/features/content/__init__.py` (empty), `app/features/content/schema.py`. Test: `tests/test_content_schema.py`.

**Step 1: Failing tests** (`tests/test_content_schema.py`)

```python
import json

import pytest
from pydantic import ValidationError

from app.features.content.schema import ExerciseContent, load_content_file


def _raw(**over):
    raw = {
        "code": "CP-004",
        "reference_solution": ["def f(n):", "    return n + 1"],
        "tests": [{"description": "one", "input": "f(1)", "expected": "2", "category": "happy", "hidden": False}],
        "mutants": [{"code": ["def f(n):", "    return n - 1"], "bug_line": 2, "bug_type": "wrong-operator",
                     "note_vi": "Dấu trừ thay cho dấu cộng.", "note_en": "Minus instead of plus."}],
        "review": {"status": "draft", "author": "claude", "reviewer": None},
    }
    raw.update(over)
    return raw


def test_code_line_arrays_are_joined():
    c = ExerciseContent.model_validate(_raw())
    assert c.reference_solution == "def f(n):\n    return n + 1"
    assert c.mutants[0].code == "def f(n):\n    return n - 1"


def test_rejects_unknown_category_and_bad_code():
    with pytest.raises(ValidationError):
        ExerciseContent.model_validate(_raw(tests=[{"description": "x", "input": "f(1)", "expected": "2",
                                                    "category": "weird", "hidden": True}]))
    with pytest.raises(ValidationError):
        ExerciseContent.model_validate(_raw(code="EX-1"))


def test_approval_needs_a_reviewer_other_than_the_author():
    assert not ExerciseContent.model_validate(_raw()).is_approved
    same = _raw(review={"status": "approved", "author": "claude", "reviewer": "claude"})
    assert not ExerciseContent.model_validate(same).is_approved
    ok = _raw(review={"status": "approved", "author": "claude", "reviewer": "an"})
    assert ExerciseContent.model_validate(ok).is_approved


def test_limits_require_a_reason():
    with pytest.raises(ValidationError):
        ExerciseContent.model_validate(_raw(limits={"min_hidden": 3}))
    c = ExerciseContent.model_validate(_raw(limits={"min_hidden": 3, "reason": "timing-dependent"}))
    assert c.limits.min_hidden == 3


def test_load_content_file_checks_the_file_name(tmp_path):
    p = tmp_path / "CP-005.json"
    p.write_text(json.dumps(_raw()), encoding="utf-8")
    with pytest.raises(ValueError, match="CP-005"):
        load_content_file(p)
```

**Step 2:** FAIL (`ModuleNotFoundError`).

**Step 3: Implement** `app/features/content/schema.py`:

```python
"""Schema of the per-exercise content files in content/exercises/<CODE>.json."""
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

CONTENT_DIR = Path(__file__).resolve().parents[3] / "content" / "exercises"

Category = Literal["happy", "boundary", "edge", "error"]


def _join_lines(value: object) -> object:
    # Files store code as an array of lines so review diffs stay readable.
    return "\n".join(value) if isinstance(value, list) else value


CodeText = Annotated[str, BeforeValidator(_join_lines), Field(min_length=1)]


class ContentTest(BaseModel):
    description: str = Field(min_length=1)
    input: str = Field(min_length=1)
    expected: str
    category: Category
    hidden: bool


class ContentMutant(BaseModel):
    code: CodeText
    bug_line: int = Field(ge=1)
    bug_type: str = Field(min_length=1, max_length=32)
    note_vi: str = Field(min_length=1)
    note_en: str = Field(min_length=1)


class ContentLimits(BaseModel):
    """Lower minimums for exercises that cannot be tested deterministically
    in the eval sandbox (e.g. timing-dependent concurrency). Needs a reason
    the reviewer accepts."""

    min_hidden: int = Field(ge=3, le=5)
    reason: str = Field(min_length=10)


class ContentReview(BaseModel):
    status: Literal["draft", "approved"]
    author: str = Field(min_length=1)
    reviewer: str | None = None


class ExerciseContent(BaseModel):
    code: str = Field(pattern=r"^CP-\d{3}$")
    reference_solution: CodeText
    tests: list[ContentTest] = Field(min_length=1)
    mutants: list[ContentMutant]
    limits: ContentLimits | None = None
    review: ContentReview

    @property
    def is_approved(self) -> bool:
        r = self.review
        return r.status == "approved" and bool(r.reviewer) and r.reviewer != r.author


def load_content_file(path: Path) -> ExerciseContent:
    content = ExerciseContent.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if path.stem != content.code:
        raise ValueError(f"{path.name}: file name must match its code {content.code}")
    return content
```

Note: `ContentLimits.reason` has `min_length=10`, so `{"min_hidden": 3}` fails on the missing field and a real reason passes. `test_load_content_file_checks_the_file_name` writes CP-004 content into `CP-005.json`, so the error message contains `CP-005`.

**Step 4:** `pytest tests/test_content_schema.py -q` → PASS.

**Step 5: Commit** — `feat(content): add exercise content file schema`

---

### Task 5: Sandbox validator

**Files:** Create `app/features/content/validate.py`. Test: `tests/test_content_validate.py`.

**Step 1: Failing tests** (`tests/test_content_validate.py`)

```python
import pytest

from app.features.content.schema import ExerciseContent
from app.features.content.validate import validate_content

pytestmark = pytest.mark.asyncio

REF = ["def sum_to_n(n):", "    total = 0", "    for i in range(1, n + 1):", "        total += i", "    return total"]
BUGGY_STARTER = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total"


def _t(desc, inp, exp, cat, hidden):
    return {"description": desc, "input": inp, "expected": exp, "category": cat, "hidden": hidden}


def _mut(line, new, bug_type="off-by-one"):
    code = list(REF)
    code[line - 1] = new
    return {"code": code, "bug_line": line, "bug_type": bug_type, "note_vi": "x", "note_en": "x"}


def _content(**over):
    raw = {
        "code": "CP-004",
        "reference_solution": REF,
        "tests": [
            _t("n=3", "sum_to_n(3)", "6", "happy", False),
            _t("n=5", "sum_to_n(5)", "15", "happy", False),
            _t("zero", "sum_to_n(0)", "0", "boundary", True),
            _t("one", "sum_to_n(1)", "1", "boundary", True),
            _t("negative", "sum_to_n(-4)", "0", "edge", True),
            _t("hundred", "sum_to_n(100)", "5050", "happy", True),
            _t("two", "sum_to_n(2)", "3", "happy", True),
        ],
        "mutants": [
            _mut(3, "    for i in range(1, n):"),
            _mut(4, "        total += i * i", "wrong-operator"),
            _mut(3, "    for i in range(2, n + 1):"),
        ],
        "review": {"status": "draft", "author": "claude", "reviewer": None},
    }
    raw.update(over)
    return ExerciseContent.model_validate(raw)


async def test_valid_content_has_no_errors():
    assert await validate_content(_content(), "debug", BUGGY_STARTER) == []


async def test_reference_must_pass_every_test():
    bad = list(REF); bad[4] = "    return total + 1"
    errors = await validate_content(_content(reference_solution=bad), "implement", "")
    assert any("reference solution fails" in e for e in errors)


async def test_equivalent_mutant_is_rejected():
    c = _content(mutants=[_mut(3, "    for i in range(0, n + 1):"), _mut(3, "    for i in range(1, n):"),
                          _mut(4, "        total += i * i")])
    errors = await validate_content(c, "implement", "")
    assert any("mutant 1: no test kills it" in e for e in errors)


async def test_mutant_must_change_exactly_its_bug_line():
    m = _mut(3, "    for i in range(1, n):")
    m["code"][1] = "    total = 1"
    errors = await validate_content(_content(mutants=[m, _mut(4, "        total += i * i"),
                                                      _mut(3, "    for i in range(2, n + 1):")]), "implement", "")
    assert any("mutant 1: must change exactly line 3" in e for e in errors)


async def test_mutant_failing_everything_is_not_plausible():
    c = _content(mutants=[_mut(5, "    return None"), _mut(3, "    for i in range(1, n):"),
                          _mut(4, "        total += i * i")])
    errors = await validate_content(c, "implement", "")
    assert any("mutant 1: fails every test" in e for e in errors)


async def test_hidden_test_count_and_categories():
    few = _content(tests=[_t("n=3", "sum_to_n(3)", "6", "happy", False),
                          _t("zero", "sum_to_n(0)", "0", "boundary", True),
                          _t("one", "sum_to_n(1)", "1", "boundary", True),
                          _t("two", "sum_to_n(2)", "3", "happy", True)])
    errors = await validate_content(few, "implement", "")
    assert any("hidden tests: 3" in e for e in errors)
    assert any("no hidden 'edge' test" in e for e in errors)


async def test_limits_lower_the_hidden_minimum():
    few = _content(tests=[_t("n=3", "sum_to_n(3)", "6", "happy", False),
                          _t("zero", "sum_to_n(0)", "0", "boundary", True),
                          _t("neg", "sum_to_n(-1)", "0", "edge", True),
                          _t("two", "sum_to_n(2)", "3", "happy", True)],
                   limits={"min_hidden": 3, "reason": "illustrating the override"})
    errors = await validate_content(few, "implement", "")
    assert not any("hidden tests" in e for e in errors)


async def test_debug_starter_must_fail_a_test():
    errors = await validate_content(_content(), "debug", "\n".join(REF))
    assert any("debug starter passes every test" in e for e in errors)


async def test_descriptions_must_be_unique():
    c = _content()
    c.tests[1].description = c.tests[0].description
    errors = await validate_content(c, "implement", "")
    assert any("duplicate test description" in e for e in errors)
```

**Step 2:** FAIL (`ModuleNotFoundError`).

**Step 3: Implement** `app/features/content/validate.py`:

```python
"""Prove an exercise content file in the sandbox before it can be synced."""
from app.features.content.schema import ExerciseContent
from app.features.sandbox.runner import run_tests

VISIBLE_RANGE = (1, 2)
HIDDEN_MAX = 8
HIDDEN_MIN_DEFAULT = 5
MUTANT_RANGE = (3, 5)
REQUIRED_HIDDEN_CATEGORIES = ("boundary", "edge")


def _cases(content: ExerciseContent) -> list[dict]:
    return [{"input_data": t.input, "expected_output": t.expected, "description": t.description, "weight": 1.0}
            for t in content.tests]


def _changed_lines(reference: str, mutant: str) -> list[int] | None:
    a, b = reference.split("\n"), mutant.split("\n")
    if len(a) != len(b):
        return None
    return [i for i, (x, y) in enumerate(zip(a, b), start=1) if x != y]


def _structure_errors(content: ExerciseContent) -> list[str]:
    errors: list[str] = []
    visible = [t for t in content.tests if not t.hidden]
    hidden = [t for t in content.tests if t.hidden]
    hidden_min = content.limits.min_hidden if content.limits else HIDDEN_MIN_DEFAULT
    if not VISIBLE_RANGE[0] <= len(visible) <= VISIBLE_RANGE[1]:
        errors.append(f"visible tests: {len(visible)} (need {VISIBLE_RANGE[0]}-{VISIBLE_RANGE[1]})")
    if not hidden_min <= len(hidden) <= HIDDEN_MAX:
        errors.append(f"hidden tests: {len(hidden)} (need {hidden_min}-{HIDDEN_MAX})")
    for category in REQUIRED_HIDDEN_CATEGORIES:
        if not any(t.category == category for t in hidden):
            errors.append(f"no hidden '{category}' test")
    seen: set[str] = set()
    for t in content.tests:
        if t.description in seen:
            errors.append(f"duplicate test description: {t.description!r}")
        seen.add(t.description)
    if not MUTANT_RANGE[0] <= len(content.mutants) <= MUTANT_RANGE[1]:
        errors.append(f"mutants: {len(content.mutants)} (need {MUTANT_RANGE[0]}-{MUTANT_RANGE[1]})")
    return errors


async def validate_content(content: ExerciseContent, kind: str, starter_code: str, timeout: int = 5) -> list[str]:
    """Return every problem found (empty list = valid).

    kind / starter_code come from the exercise row (or the seed): a debug
    exercise's buggy starter must fail at least one test.
    """
    errors = _structure_errors(content)
    cases = _cases(content)

    ref = await run_tests(content.reference_solution, cases, timeout)
    if ref["runtime_error"]:
        errors.append(f"reference solution raises: {ref['runtime_error']}")
    failing = [c["name"] for c in ref["cases"] if not c["passed"]]
    if failing:
        errors.append(f"reference solution fails: {failing}")

    for i, mutant in enumerate(content.mutants, start=1):
        changed = _changed_lines(content.reference_solution, mutant.code)
        if changed is None:
            errors.append(f"mutant {i}: must keep the reference's number of lines")
        elif changed != [mutant.bug_line]:
            errors.append(f"mutant {i}: must change exactly line {mutant.bug_line}, changed {changed}")
        res = await run_tests(mutant.code, cases, timeout)
        if res["passed"] == res["total"]:
            errors.append(f"mutant {i}: no test kills it (equivalent mutant or missing test)")
        elif res["passed"] == 0:
            errors.append(f"mutant {i}: fails every test (too obviously broken to be a useful bug)")

    if kind == "debug":
        res = await run_tests(starter_code, cases, timeout)
        if res["passed"] == res["total"]:
            errors.append("debug starter passes every test: no test covers the planted bug")
    return errors
```

**Step 4:** `pytest tests/test_content_validate.py -q` → PASS (runs the real sandbox; ~5 s).

**Step 5: Commit** — `feat(content): validate content files in the sandbox`

---

### Task 6: Sync command (review-gated upsert)

**Files:** Create `app/features/content/sync.py`. Test: `tests/test_content_sync.py`.

**Step 1: Failing tests** (`tests/test_content_sync.py`)

```python
import json

import pytest
from sqlalchemy import select

from app.features.content.sync import sync_content
from tests.test_content_validate import BUGGY_STARTER, _content

pytestmark = pytest.mark.asyncio


async def _exercise(db_session):
    from app.models import Exercise, TestCase

    ex = Exercise(code="CP-004", title="t", difficulty="Easy", category="c", level="fresher", kind="debug",
                  language="python", summary="s", starter_code=BUGGY_STARTER, hint="h", domain_keywords=[])
    db_session.add(ex); await db_session.flush()
    db_session.add(TestCase(exercise_id=ex.id, input_data="sum_to_n(3)", expected_output="6",
                            description="legacy", is_hidden=False, order_index=1))
    await db_session.commit()
    return ex


def _write(tmp_path, review):
    c = _content(review=review)
    raw = json.loads(c.model_dump_json())
    p = tmp_path / "CP-004.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    return p


APPROVED = {"status": "approved", "author": "claude", "reviewer": "an"}


async def test_dry_run_reports_without_writing(db_session, tmp_path):
    from app.models import TestCase

    await _exercise(db_session)
    results = await sync_content(db_session, [_write(tmp_path, APPROVED)], apply=False)
    assert results[0]["status"] == "ok"
    assert results[0]["hidden"] == 5 and results[0]["mutants"] == 3
    descs = (await db_session.execute(select(TestCase.description))).scalars().all()
    assert descs == ["legacy"]


async def test_apply_replaces_tests_and_mutants(db_session, tmp_path):
    from app.models import Exercise, ExerciseMutant, TestCase

    await _exercise(db_session)
    await sync_content(db_session, [_write(tmp_path, APPROVED)], apply=True)
    await sync_content(db_session, [_write(tmp_path, APPROVED)], apply=True)   # idempotent
    tests = (await db_session.execute(select(TestCase).order_by(TestCase.order_index))).scalars().all()
    assert len(tests) == 7
    assert sum(t.is_hidden for t in tests) == 5
    assert {t.category for t in tests} >= {"happy", "boundary", "edge"}
    assert len((await db_session.execute(select(ExerciseMutant))).scalars().all()) == 3
    ex = (await db_session.execute(select(Exercise))).scalar_one()
    assert ex.reference_solution.startswith("def sum_to_n(n):")


async def test_unapproved_or_self_reviewed_files_are_skipped(db_session, tmp_path):
    await _exercise(db_session)
    draft = await sync_content(db_session, [_write(tmp_path, {"status": "draft", "author": "claude", "reviewer": None})], apply=True)
    assert draft[0]["status"] == "skipped" and "approved" in draft[0]["reason"]
    self_rev = await sync_content(db_session, [_write(tmp_path, {"status": "approved", "author": "an", "reviewer": "an"})], apply=True)
    assert self_rev[0]["status"] == "skipped"


async def test_invalid_content_is_not_written(db_session, tmp_path):
    from app.models import TestCase

    await _exercise(db_session)
    p = _write(tmp_path, APPROVED)
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["reference_solution"] = "def sum_to_n(n):\n    return 0"
    p.write_text(json.dumps(raw), encoding="utf-8")
    results = await sync_content(db_session, [p], apply=True)
    assert results[0]["status"] == "invalid" and results[0]["errors"]
    assert len((await db_session.execute(select(TestCase))).scalars().all()) == 1
```

**Step 2:** FAIL (`ModuleNotFoundError`).

**Step 3: Implement** `app/features/content/sync.py`:

```python
"""Load reviewed exercise content into the database.

    python -m app.features.content.sync              # dry run, every file
    python -m app.features.content.sync CP-004 ...   # dry run, some files
    python -m app.features.content.sync --apply      # write

Only files approved by a reviewer other than the author, and that pass the
sandbox validator, are written. A written exercise has its test cases and
mutants replaced by the file's (the file is the source of truth).
"""
import argparse
import asyncio
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.features.content.schema import CONTENT_DIR, ExerciseContent, load_content_file
from app.features.content.validate import validate_content
from app.models import Exercise, ExerciseMutant, TestCase


async def _write(db: AsyncSession, ex: Exercise, content: ExerciseContent) -> None:
    ex.reference_solution = content.reference_solution
    await db.execute(delete(TestCase).where(TestCase.exercise_id == ex.id))
    await db.execute(delete(ExerciseMutant).where(ExerciseMutant.exercise_id == ex.id))
    for i, t in enumerate(content.tests, start=1):
        db.add(TestCase(exercise_id=ex.id, input_data=t.input, expected_output=t.expected,
                        description=t.description, category=t.category, is_hidden=t.hidden,
                        order_index=i, weight=1.0))
    for i, m in enumerate(content.mutants, start=1):
        db.add(ExerciseMutant(exercise_id=ex.id, code=m.code, bug_line=m.bug_line, bug_type=m.bug_type,
                              note_vi=m.note_vi, note_en=m.note_en, order_index=i))


async def sync_content(db: AsyncSession, files: list[Path], apply: bool) -> list[dict]:
    results: list[dict] = []
    for path in sorted(files):
        content = load_content_file(path)
        ex = (await db.execute(select(Exercise).where(Exercise.code == content.code))).scalar_one_or_none()
        if ex is None:
            results.append({"code": content.code, "status": "skipped", "reason": "exercise not in the database"})
            continue
        if not content.is_approved:
            results.append({"code": content.code, "status": "skipped",
                            "reason": "not approved by a reviewer other than the author"})
            continue
        errors = await validate_content(content, ex.kind, ex.starter_code)
        if errors:
            results.append({"code": content.code, "status": "invalid", "errors": errors})
            continue
        results.append({"code": content.code, "status": "ok", "tests": len(content.tests),
                        "hidden": sum(t.hidden for t in content.tests), "mutants": len(content.mutants)})
        if apply:
            await _write(db, ex, content)
    if apply:
        await db.commit()
    return results


async def _main(codes: list[str], apply: bool) -> int:
    files = [CONTENT_DIR / f"{c.upper()}.json" for c in codes] if codes else sorted(CONTENT_DIR.glob("*.json"))
    async with async_session_maker() as db:
        results = await sync_content(db, files, apply)
    for r in results:
        if r["status"] == "ok":
            print(f"{r['code']}  ok       tests={r['tests']} hidden={r['hidden']} mutants={r['mutants']}")
        elif r["status"] == "skipped":
            print(f"{r['code']}  skipped  {r['reason']}")
        else:
            print(f"{r['code']}  INVALID")
            for e in r["errors"]:
                print(f"    - {e}")
    written = sum(r["status"] == "ok" for r in results)
    print(f"{written} exercise(s) {'written' if apply else 'ready (dry run, use --apply to write)'}")
    return 1 if any(r["status"] == "invalid" for r in results) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("codes", nargs="*", help="exercise codes (default: every content file)")
    parser.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main(args.codes, args.apply)))
```

**Step 4:** `pytest tests/test_content_sync.py -q` → PASS; full suite passes.

**Step 5: Commit** — `feat(content): add review-gated content sync command`

---

### Task 7: Every content file is valid (pytest)

**Files:** Create `tests/test_content_files.py`, `content/exercises/.gitkeep`.

```python
"""Every file in content/exercises must parse and pass the sandbox validator.

Run before opening a content PR: pytest tests/test_content_files.py -q
"""
import pytest

from app.features.content.schema import CONTENT_DIR, load_content_file
from app.features.content.validate import validate_content
from app.seed.exercises_seed import EXERCISES

SEED = {e["code"]: e for e in EXERCISES}
FILES = sorted(CONTENT_DIR.glob("*.json"))


@pytest.mark.asyncio
@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
async def test_content_file_is_valid(path):
    content = load_content_file(path)
    assert content.code in SEED, f"{content.code} is not a known exercise"
    seed = SEED[content.code]
    errors = await validate_content(content, seed.get("kind", "implement"), seed["starter_code"])
    assert errors == [], "\n".join(errors)
```

With no files yet pytest reports this test as skipped (empty parameter set). Commit — `test(content): validate every content file`.

---

### Task 8: Authoring + review guide for the team

**Files:** Create `docs/content-authoring.md` (English, like the rest of `docs/`), containing:

1. **Workflow:** Claude drafts `content/exercises/<CODE>.json` with `review.status: "draft"`, `author: "claude"` → `pytest tests/test_content_files.py` must pass → PR per batch → the assigned reviewer checks the file against the checklist, edits if needed, sets `status: "approved"` and `reviewer: "<their name>"` in the same PR → merge → on EC2: backup, `docker exec codeprove_backend python -m app.features.content.sync` (dry run), then `--apply`.
2. **Format** (the JSON example from the design doc), categories, `expected` = `repr` of the return value, code as arrays of lines, `limits` only with a reason.
3. **Reviewer checklist:**
   - Reference solution is correct, idiomatic, and solves the problem **as the summary states it** (not a different reading).
   - Visible tests only show typical cases; hidden tests cover boundary + edge cases a careful student should think of, and none depends on an unstated assumption.
   - Each mutant is a bug a real developer (or an AI) could plausibly write; `note_vi`/`note_en` explain it in one sentence each, and would make sense to show to a student after submit.
   - For debug exercises: the planted bug in the starter is caught by at least one hidden test.
   - Nothing in visible test descriptions reveals hidden cases.
4. **Assignment** (4 members, each reviews 6–8 exercises):

| Reviewer | Exercises |
|---|---|
| Kiệt | CP-001 … CP-008 |
| Trung | CP-009 … CP-012, CP-101 … CP-104 |
| Minh | CP-105 … CP-110, CP-201, CP-202 |
| Phát | CP-203 … CP-208 |

Commit — `docs(content): add authoring and review guide`.

---

### Task 9: Draft the content for all 30 exercises

Claude drafts in-session (no API cost), in three batches — fresher (CP-001…CP-012), junior (CP-101…CP-110), senior (CP-201…CP-208). For each exercise:

1. Read its seed entry (`app/seed/exercises_seed.py`): summary, starter, the 2 existing visible tests (keep them as the visible tests, `category: "happy"`, unless one is clearly an edge case).
2. Write the reference solution matching the starter's signature (debug exercises: the starter with the bug fixed and nothing else changed).
3. Write 5–8 hidden tests covering boundary + edge (+ error only if the summary defines error behaviour).
4. Write 3–5 mutants of the reference, one line each, realistic bug types (off-by-one, wrong boundary, swapped operator, wrong variable, missing case, inverted condition).
5. For exercises that cannot be tested deterministically in the eval sandbox (timing-dependent concurrency), use `limits` with a precise reason; the reviewer must agree.
6. Run `pytest tests/test_content_files.py -q -k CP-XXX` until green.

After each batch: full `pytest -q`, commit `content: draft <level> exercises (<n>)`. Report any exercise whose summary is too ambiguous to test, instead of guessing — list it in the PR for the team to decide.

---

### Task 10: PR, team review, rollout

1. Push `feat/p1-1-content-pipeline`; open one PR for the code (Tasks 1–8) and — so reviewers can work in parallel — let the drafted content ride in the same PR only if the team prefers; otherwise one PR per batch on top.
2. Team reviews content per the guide; each reviewer approves in-file.
3. Deploy order on EC2 (the leak guards in Task 3 **must** be live before any hidden test is synced):
   1. backup;
   2. `git pull && docker compose up -d --build` (runs migration `b4e6a8c0d2f1`);
   3. `docker exec codeprove_backend python -m app.features.content.sync` → review;
   4. `... sync --apply`.
4. Spot-check: an exercise detail page lists only visible tests; `/run` shows only visible results.
