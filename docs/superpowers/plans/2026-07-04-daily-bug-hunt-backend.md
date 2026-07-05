# Daily Bug Hunt Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend half of "Daily Bug Hunt" - a single shared daily challenge where a user spots the one bug Ciel planted in a short Python solution, with a streak that survives anonymous play via a claim step.

**Architecture:** New self-contained feature module `app/features/daily/` (models, content generation, streak math, service, router) following the existing `app/features/<domain>/` pattern used by `exercises`/`attempts`/`mentor`. Two new tables (`daily_challenges`, `daily_attempts`) are fully separate from `exercises`/`attempts`/`fluency_reports` - nothing here touches the formal AI-Fluency/Integrity scoring. Content generation reuses the existing `MentorClient.judge()` JSON-mode method (already used by `judge_hypothesis`) with a new system prompt - no new OpenAI client code needed. There is no scheduler dependency: `GET /daily/today` lazily generates the day's challenge on first request if it doesn't exist yet, which is simpler and sufficient for this traffic level (YAGNI - no cron/APScheduler added).

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic + Pydantic v2 + pytest/pytest-asyncio (all already in `requirements.txt`), plus `tzdata` (new dependency - see Task 4).

## Global Constraints

- Non-goal: this feature must never write to `exercises`, `attempts`, `fluency_reports`, or any table read by the scoring engine (`app/features/scoring/engine.py`). Spec: `codeprove-backend/docs/superpowers/specs/2026-07-04-daily-bug-hunt-design.md`, section 1.
- The daily challenge resets at local midnight in `Asia/Ho_Chi_Minh` (spec section 4). V1 uses this fixed timezone for every user, no per-user timezone support.
- Anonymous play must work: `GET /daily/today` and `POST /daily/attempt` never require authentication. Anonymous submissions are not persisted server-side (spec section 7) - the client keeps its own history in `localStorage` and can later call `POST /daily/claim-streak` once it has an account.
- Streak = consecutive calendar days with **any** submitted attempt, correct or not (spec section 4) - it must not reset just because a day's guess was wrong.
- `time_taken_seconds` is client-reported and intentionally not server-verified (spec section 7, footnote) - this is acceptable because Daily Bug Hunt results never feed the formal score.
- No em dash (`—`) in any string - use a plain hyphen `-`.
- Follow the existing `features/<domain>/{router,service}.py` + `schemas/<domain>.py` + `models/<name>.py` split used by every existing feature (see `exercises`, `mentor`, `attempts`).

---

### Task 1: `DailyChallenge` and `DailyAttempt` models + migration

**Files:**
- Create: `app/models/daily_challenge.py`
- Create: `app/models/daily_attempt.py`
- Modify: `app/models/__init__.py`
- Create: `alembic/versions/e5a91f3d7c22_add_daily_bug_hunt.py`
- Test: `tests/test_daily_models.py`

**Interfaces:**
- Produces: `DailyChallenge` (fields: `id`, `challenge_date: date` unique, `prompt_title: str`, `buggy_code: str`, `buggy_line: int`, `bug_category: str`, `hint_1: str`, `hint_2: str`, `explanation: str`, `created_at`). `DailyAttempt` (fields: `id`, `user_id: int` FK to `users.id`, `challenge_date: date`, `selected_line: int | None`, `hints_used: int`, `time_taken_seconds: int | None`, `tier: str | None`, `submitted_at: datetime | None`, unique on `(user_id, challenge_date)`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_daily_models.py`:

```python
import pytest
from datetime import date, datetime, timezone

from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def test_daily_challenge_round_trip(db_session):
    from app.models import DailyChallenge

    db_session.add(
        DailyChallenge(
            challenge_date=date(2026, 7, 4),
            prompt_title="Kiem tra so nguyen to",
            buggy_code="def is_prime(n):\n    return n > 1",
            buggy_line=2,
            bug_category="off-by-one",
            hint_1="Xem lai dieu kien bien",
            hint_2="So 4 co qua duoc khong?",
            explanation="Thieu kiem tra uoc so, moi n > 1 deu bi coi la nguyen to.",
        )
    )
    await db_session.commit()

    row = (
        await db_session.execute(
            select(DailyChallenge).where(DailyChallenge.challenge_date == date(2026, 7, 4))
        )
    ).scalar_one()
    assert row.prompt_title == "Kiem tra so nguyen to"
    assert row.buggy_line == 2


async def test_daily_challenge_date_is_unique(db_session):
    from app.models import DailyChallenge
    from sqlalchemy.exc import IntegrityError

    db_session.add(
        DailyChallenge(
            challenge_date=date(2026, 7, 5), prompt_title="a", buggy_code="x", buggy_line=1,
            bug_category="c", hint_1="h1", hint_2="h2", explanation="e",
        )
    )
    await db_session.commit()
    db_session.add(
        DailyChallenge(
            challenge_date=date(2026, 7, 5), prompt_title="b", buggy_code="y", buggy_line=1,
            bug_category="c", hint_1="h1", hint_2="h2", explanation="e",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_daily_attempt_unique_per_user_per_day(db_session):
    from app.models import DailyAttempt, User
    from sqlalchemy.exc import IntegrityError

    user = User(full_name="T", email="t@example.com", password_hash="x")
    db_session.add(user)
    await db_session.commit()

    db_session.add(DailyAttempt(user_id=user.id, challenge_date=date(2026, 7, 4)))
    await db_session.commit()
    db_session.add(DailyAttempt(user_id=user.id, challenge_date=date(2026, 7, 4)))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_daily_attempt_submit_fields(db_session):
    from app.models import DailyAttempt, User

    user = User(full_name="T2", email="t2@example.com", password_hash="x")
    db_session.add(user)
    await db_session.commit()

    attempt = DailyAttempt(user_id=user.id, challenge_date=date(2026, 7, 4))
    db_session.add(attempt)
    await db_session.commit()
    attempt.selected_line = 2
    attempt.hints_used = 1
    attempt.time_taken_seconds = 45
    attempt.tier = "yellow"
    attempt.submitted_at = datetime.now(timezone.utc)
    await db_session.commit()

    row = (
        await db_session.execute(select(DailyAttempt).where(DailyAttempt.id == attempt.id))
    ).scalar_one()
    assert row.tier == "yellow"
    assert row.submitted_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'DailyChallenge' from 'app.models'` (the models don't exist yet).

- [ ] **Step 3: Create the models**

Create `app/models/daily_challenge.py`:

```python
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DailyChallenge(Base):
    __tablename__ = "daily_challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    prompt_title: Mapped[str] = mapped_column(String(255))
    buggy_code: Mapped[str] = mapped_column(Text)
    buggy_line: Mapped[int] = mapped_column(Integer)
    bug_category: Mapped[str] = mapped_column(String(64))
    hint_1: Mapped[str] = mapped_column(Text)
    hint_2: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Create `app/models/daily_attempt.py`:

```python
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DailyAttempt(Base):
    __tablename__ = "daily_attempts"
    __table_args__ = (UniqueConstraint("user_id", "challenge_date", name="uq_daily_attempt_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    challenge_date: Mapped[date] = mapped_column(Date, index=True)
    selected_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tier: Mapped[str | None] = mapped_column(String(16), nullable=True)  # green|yellow|red
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Modify `app/models/__init__.py` (add the two new imports and `__all__` entries, keep everything else exactly as-is):

```python
from app.models.attempt import Attempt
from app.models.code_snapshot import CodeSnapshot
from app.models.daily_attempt import DailyAttempt
from app.models.daily_challenge import DailyChallenge
from app.models.event import Event
from app.models.exercise import Exercise
from app.models.fluency_report import FluencyReport
from app.models.prompt_log import PromptLog
from app.models.test_case import TestCase
from app.models.user import User
from app.models.verification_answer import VerificationAnswer

__all__ = [
    "Attempt", "CodeSnapshot", "DailyAttempt", "DailyChallenge", "Event", "Exercise",
    "FluencyReport", "PromptLog", "TestCase", "User", "VerificationAnswer",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_models.py -v`
Expected: 4 passed.

- [ ] **Step 5: Write the Alembic migration**

Create `alembic/versions/e5a91f3d7c22_add_daily_bug_hunt.py`:

```python
"""add daily bug hunt tables

Revision ID: e5a91f3d7c22
Revises: c8d4e2b7f1a0
Create Date: 2026-07-04 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e5a91f3d7c22"
down_revision: Union[str, None] = "c8d4e2b7f1a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("challenge_date", sa.Date(), nullable=False, unique=True),
        sa.Column("prompt_title", sa.String(length=255), nullable=False),
        sa.Column("buggy_code", sa.Text(), nullable=False),
        sa.Column("buggy_line", sa.Integer(), nullable=False),
        sa.Column("bug_category", sa.String(length=64), nullable=False),
        sa.Column("hint_1", sa.Text(), nullable=False),
        sa.Column("hint_2", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_daily_challenges_challenge_date", "daily_challenges", ["challenge_date"])

    op.create_table(
        "daily_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("challenge_date", sa.Date(), nullable=False),
        sa.Column("selected_line", sa.Integer(), nullable=True),
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("time_taken_seconds", sa.Integer(), nullable=True),
        sa.Column("tier", sa.String(length=16), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "challenge_date", name="uq_daily_attempt_user_date"),
    )
    op.create_index("ix_daily_attempts_user_id", "daily_attempts", ["user_id"])
    op.create_index("ix_daily_attempts_challenge_date", "daily_attempts", ["challenge_date"])


def downgrade() -> None:
    op.drop_index("ix_daily_attempts_challenge_date", table_name="daily_attempts")
    op.drop_index("ix_daily_attempts_user_id", table_name="daily_attempts")
    op.drop_table("daily_attempts")
    op.drop_index("ix_daily_challenges_challenge_date", table_name="daily_challenges")
    op.drop_table("daily_challenges")
```

- [ ] **Step 6: Commit**

```bash
git add app/models/daily_challenge.py app/models/daily_attempt.py app/models/__init__.py \
        alembic/versions/e5a91f3d7c22_add_daily_bug_hunt.py tests/test_daily_models.py
git commit -m "feat: add DailyChallenge and DailyAttempt models + migration"
```

---

### Task 2: Daily prompt bank + Ciel-based challenge content generation

**Files:**
- Create: `app/features/daily/__init__.py`
- Create: `app/features/daily/prompts_bank.py`
- Create: `app/features/daily/content.py`
- Modify: `app/features/mentor/prompts.py`
- Test: `tests/test_daily_content.py`

**Interfaces:**
- Consumes: `DailyChallenge` model (Task 1); `get_mentor_client()` and `MentorClient.judge(system, user) -> dict` from `app/features/mentor/client.py` (existing, already used by `judge_hypothesis` in `app/features/mentor/service.py:110-122` - do not modify `client.py`).
- Produces: `DAILY_PROMPTS: list[str]` (module-level constant in `prompts_bank.py`); `async def generate_challenge(db: AsyncSession, challenge_date: date) -> DailyChallenge` in `content.py` - later tasks call this only through the service layer (Task 4), never directly from the router.

- [ ] **Step 1: Write the failing test**

Create `tests/test_daily_content.py`:

```python
import pytest
from datetime import date

pytestmark = pytest.mark.asyncio


class FakeJudgeClient:
    _model = "fake"

    async def judge(self, system, user):
        assert "Problem title:" in user
        return {
            "buggy_code": "def is_prime(n):\n    for i in range(2, n):\n        if n % i == 0:\n            return False\n    return True",
            "buggy_line": 2,
            "bug_category": "off-by-one",
            "hint_1": "Xem lai vong lap",
            "hint_2": "So 0 va 1 co duoc xu ly dung khong?",
            "explanation": "Thieu kiem tra n < 2, nen 0 va 1 bi coi la so nguyen to.",
        }


@pytest.fixture(autouse=True)
def _patch_mentor_client(monkeypatch):
    import app.features.daily.content as content_mod

    fake = FakeJudgeClient()
    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: fake)


async def test_generate_challenge_creates_row(db_session):
    from app.features.daily.content import generate_challenge
    from app.models import DailyChallenge

    challenge = await generate_challenge(db_session, date(2026, 7, 4))
    assert isinstance(challenge, DailyChallenge)
    assert challenge.challenge_date == date(2026, 7, 4)
    assert challenge.buggy_line == 2
    assert challenge.bug_category == "off-by-one"
    assert challenge.prompt_title  # picked from the bank, non-empty


async def test_generate_challenge_avoids_titles_used_in_last_30_days(db_session):
    from app.features.daily.content import generate_challenge
    from app.features.daily.prompts_bank import DAILY_PROMPTS
    from app.models import DailyChallenge
    from datetime import timedelta

    # Fill every prompt except the last one with recent challenges, so the
    # generator is forced to pick the one remaining unused title.
    today = date(2026, 7, 4)
    for i, title in enumerate(DAILY_PROMPTS[:-1]):
        db_session.add(
            DailyChallenge(
                challenge_date=today - timedelta(days=i + 1),
                prompt_title=title, buggy_code="x", buggy_line=1, bug_category="c",
                hint_1="h", hint_2="h", explanation="e",
            )
        )
    await db_session.commit()

    challenge = await generate_challenge(db_session, today)
    assert challenge.prompt_title == DAILY_PROMPTS[-1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_content.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.features.daily'`.

- [ ] **Step 3: Add the new system prompt**

Modify `app/features/mentor/prompts.py` - append this constant at the end of the file (keep every existing constant exactly as-is):

```python

DAILY_CHALLENGE_SYSTEM = """You are generating content for CodeProve's "Daily Bug Hunt" - a
Wordle-style daily game where developers spot a bug in a short Python solution. This is a
DIFFERENT context from the tutoring mentor: here you must output a COMPLETE, standalone
solution, not a partial snippet, and you are not talking to the student.

Given a problem title, write a short Python solution (10-20 lines, a single function) that
looks correct at a glance but contains EXACTLY ONE subtle bug (e.g. off-by-one, wrong boundary
condition, swapped operator, wrong variable used, inverted condition). The bug must be
plausible - something a developer reviewing AI-generated code could genuinely miss on a quick
read. Do not use a syntax error and do not use anything a linter would flag.

Reply ONLY with compact JSON matching this exact shape:
{"buggy_code": "<the full Python function as a single string with real \\n line breaks>",
 "buggy_line": <1-indexed line number within buggy_code where the bug lives>,
 "bug_category": "<short category, e.g. \\"off-by-one\\">",
 "hint_1": "<vague hint pointing at the general area/concept, no line number>",
 "hint_2": "<clearer hint naming the kind of mistake, still not the fix>",
 "explanation": "<one or two sentences explaining the bug and the fix, shown after the player submits>"}"""
```

- [ ] **Step 4: Create the prompt bank**

Create `app/features/daily/__init__.py` (empty file, matches every other `features/<domain>/__init__.py`):

```python
```

Create `app/features/daily/prompts_bank.py`:

```python
# Problems for Daily Bug Hunt: short enough that Ciel's solution fits in
# 10-20 lines (spec section 3). Separate from `exercises_seed.py` - those
# problems are sized for full graded exercises, not a 2-5 minute daily game.
DAILY_PROMPTS: list[str] = [
    "Kiem tra mot so co phai so nguyen to",
    "Tim phan tu xuat hien nhieu nhat trong danh sach",
    "Dao nguoc mot chuoi",
    "Tinh tong N so Fibonacci dau tien",
    "Kiem tra chuoi co phai palindrome",
    "Tim so lon thu hai trong danh sach",
    "Dem so nguyen am trong danh sach",
    "Loai bo phan tu trung lap khoi danh sach, giu thu tu",
    "Tim uoc chung lon nhat cua hai so",
    "Kiem tra hai chuoi co phai la anagram",
    "Tinh giai thua cua mot so",
    "Tim phan tu con thieu trong day so lien tiep",
    "Dem so lan xuat hien cua moi ky tu trong chuoi",
    "Tim cap so trong danh sach co tong bang target",
    "Sap xep danh sach bang bubble sort",
    "Tim chuoi con dai nhat khong lap ky tu",
    "Kiem tra ngoac don co can bang khong",
    "Tinh trung binh cong bo qua gia tri am",
    "Tim phan tu xuat hien dung 1 lan trong danh sach co phan tu lap",
    "Chuyen so nguyen sang chuoi nhi phan",
    "Tinh so ngay giua hai moc thoi gian",
    "Gop hai danh sach da sap xep thanh mot danh sach sap xep",
    "Tim phan tu nho nhat trong danh sach da sap xep va xoay vong",
    "Dem so buoc de leo het cau thang (climbing stairs)",
    "Tim subarray lien tiep co tong lon nhat (Kadane)",
    "Kiem tra mot ma tran vuong co doi xung qua duong cheo khong",
    "Tim k phan tu lon nhat trong danh sach",
    "Nhom cac tu la anagram cua nhau",
    "Tinh khoang cach Levenshtein don gian giua hai chuoi ngan",
    "Tim phan tu chung giua hai danh sach",
]
```

- [ ] **Step 5: Implement `generate_challenge`**

Create `app/features/daily/content.py`:

```python
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.daily.prompts_bank import DAILY_PROMPTS
from app.features.mentor.client import get_mentor_client
from app.features.mentor.prompts import DAILY_CHALLENGE_SYSTEM
from app.models import DailyChallenge

_LOOKBACK_DAYS = 30


async def _recent_titles(db: AsyncSession, before: date) -> set[str]:
    cutoff = before - timedelta(days=_LOOKBACK_DAYS)
    rows = (
        await db.execute(
            select(DailyChallenge.prompt_title).where(
                DailyChallenge.challenge_date >= cutoff, DailyChallenge.challenge_date < before
            )
        )
    ).scalars().all()
    return set(rows)


def _pick_prompt(exclude: set[str]) -> str:
    available = [p for p in DAILY_PROMPTS if p not in exclude]
    # If the whole bank was used in the last 30 days, allow a repeat rather
    # than fail the day's challenge.
    pool = available or DAILY_PROMPTS
    return random.choice(pool)


async def generate_challenge(db: AsyncSession, challenge_date: date) -> DailyChallenge:
    """Pick an unused prompt title and ask Ciel to write a buggy solution for it."""
    exclude = await _recent_titles(db, challenge_date)
    prompt_title = _pick_prompt(exclude)
    data = await get_mentor_client().judge(DAILY_CHALLENGE_SYSTEM, f"Problem title: {prompt_title}")
    challenge = DailyChallenge(
        challenge_date=challenge_date,
        prompt_title=prompt_title,
        buggy_code=data.get("buggy_code", ""),
        buggy_line=int(data.get("buggy_line") or 1),
        bug_category=data.get("bug_category", "unknown"),
        hint_1=data.get("hint_1", ""),
        hint_2=data.get("hint_2", ""),
        explanation=data.get("explanation", ""),
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)
    return challenge
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_content.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add app/features/daily/__init__.py app/features/daily/prompts_bank.py \
        app/features/daily/content.py app/features/mentor/prompts.py tests/test_daily_content.py
git commit -m "feat: add daily prompt bank and Ciel-based bug-hunt content generation"
```

---

### Task 3: Streak computation (pure function)

**Files:**
- Create: `app/features/daily/streak.py`
- Test: `tests/test_daily_streak.py`

**Interfaces:**
- Produces: `def compute_streak(attempt_dates: set[date], today: date) -> int` - Task 4's service layer is the only consumer.

- [ ] **Step 1: Write the failing test**

Create `tests/test_daily_streak.py`:

```python
from datetime import date, timedelta


def test_streak_zero_when_no_attempts():
    from app.features.daily.streak import compute_streak

    assert compute_streak(set(), date(2026, 7, 4)) == 0


def test_streak_counts_consecutive_days_ending_today():
    from app.features.daily.streak import compute_streak

    today = date(2026, 7, 4)
    dates = {today, today - timedelta(days=1), today - timedelta(days=2)}
    assert compute_streak(dates, today) == 3


def test_streak_survives_if_today_not_played_yet_but_yesterday_was():
    from app.features.daily.streak import compute_streak

    today = date(2026, 7, 4)
    dates = {today - timedelta(days=1), today - timedelta(days=2)}
    assert compute_streak(dates, today) == 2


def test_streak_resets_after_a_full_gap_day():
    from app.features.daily.streak import compute_streak

    today = date(2026, 7, 4)
    # Played 3 and 4 days ago, but skipped yesterday and today.
    dates = {today - timedelta(days=3), today - timedelta(days=4)}
    assert compute_streak(dates, today) == 0


def test_streak_breaks_at_first_gap_counting_backward():
    from app.features.daily.streak import compute_streak

    today = date(2026, 7, 4)
    # Today and yesterday played, then a gap, then two older days - streak
    # must stop at the gap and not count the older run.
    dates = {today, today - timedelta(days=1), today - timedelta(days=3), today - timedelta(days=4)}
    assert compute_streak(dates, today) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_streak.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.features.daily.streak'`.

- [ ] **Step 3: Implement `compute_streak`**

Create `app/features/daily/streak.py`:

```python
from datetime import date, timedelta


def compute_streak(attempt_dates: set[date], today: date) -> int:
    """Current streak = consecutive calendar days with a submitted attempt,
    counted backward from today.

    If today has not been played yet, the streak still counts backward from
    yesterday instead of resetting to 0 - a streak is only broken once a full
    day is skipped (matches Wordle/Duolingo semantics, per spec section 4).
    """
    start = today if today in attempt_dates else today - timedelta(days=1)
    streak = 0
    cursor = start
    while cursor in attempt_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_streak.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/features/daily/streak.py tests/test_daily_streak.py
git commit -m "feat: add pure streak-computation function for daily bug hunt"
```

---

### Task 4: Service layer - get-or-create challenge, submit attempt, streak lookup

**Files:**
- Create: `app/features/daily/service.py`
- Modify: `requirements.txt`
- Test: `tests/test_daily_service.py`

**Interfaces:**
- Consumes: `generate_challenge` (Task 2), `compute_streak` (Task 3), `DailyChallenge`/`DailyAttempt` models (Task 1).
- Produces (used by Task 5's router and Task 6's claim-streak):
  - `def today_vn() -> date`
  - `async def get_or_create_challenge(db: AsyncSession, challenge_date: date) -> DailyChallenge`
  - `async def challenge_number(db: AsyncSession, challenge_date: date) -> int`
  - `async def get_attempt(db: AsyncSession, user_id: int, challenge_date: date) -> DailyAttempt | None`
  - `async def user_streak(db: AsyncSession, user_id: int, today: date) -> int`
  - `def tier_for(correct: bool, hints_used: int, time_taken_seconds: int) -> str`
  - `async def submit_attempt(db: AsyncSession, user_id: int | None, selected_line: int, hints_used: int, time_taken_seconds: int) -> dict` returning `{"correct": bool, "tier": str, "buggy_line": int, "explanation": str, "streak": int | None}`

- [ ] **Step 1: Add `tzdata` (Windows dev machines have no IANA tz database)**

Modify `requirements.txt` - add this line (anywhere in the file, alphabetical placement is not enforced elsewhere in this file so just append):

```
tzdata==2024.2
```

Run: `cd codeprove-backend && .venv/Scripts/python.exe -m pip install tzdata==2024.2` (use your venv's actual pip; on this project it's `codeprove-backend/.venv/Scripts/python.exe -m pip install ...` per prior session notes).

- [ ] **Step 2: Write the failing test**

Create `tests/test_daily_service.py`:

```python
import pytest
from datetime import date

pytestmark = pytest.mark.asyncio


class FakeJudgeClient:
    _model = "fake"
    calls = 0

    async def judge(self, system, user):
        FakeJudgeClient.calls += 1
        return {
            "buggy_code": "def f():\n    return 1",
            "buggy_line": 2,
            "bug_category": "off-by-one",
            "hint_1": "h1",
            "hint_2": "h2",
            "explanation": "e",
        }


@pytest.fixture(autouse=True)
def _patch_mentor_client(monkeypatch):
    import app.features.daily.content as content_mod

    FakeJudgeClient.calls = 0
    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: FakeJudgeClient())


async def _make_user(db_session, email="svc@example.com"):
    from app.models import User

    user = User(full_name="Svc", email=email, password_hash="x")
    db_session.add(user)
    await db_session.commit()
    return user


def test_today_vn_returns_a_date():
    from app.features.daily.service import today_vn

    assert isinstance(today_vn(), date)


async def test_get_or_create_challenge_returns_the_same_row_on_repeat_calls(db_session):
    from app.features.daily.service import get_or_create_challenge

    d = date(2026, 7, 4)
    first = await get_or_create_challenge(db_session, d)
    second = await get_or_create_challenge(db_session, d)
    assert first.id == second.id


async def test_get_or_create_challenge_calls_generation_only_once(db_session, monkeypatch):
    import app.features.daily.content as content_mod
    from app.features.daily.service import get_or_create_challenge

    calls = {"n": 0}
    original = content_mod.generate_challenge

    async def _counting(db, challenge_date):
        calls["n"] += 1
        return await original(db, challenge_date)

    monkeypatch.setattr("app.features.daily.service.generate_challenge", _counting)
    d = date(2026, 7, 5)
    await get_or_create_challenge(db_session, d)
    await get_or_create_challenge(db_session, d)
    assert calls["n"] == 1


async def test_challenge_number_counts_up_to_date(db_session):
    from app.features.daily.service import get_or_create_challenge, challenge_number

    await get_or_create_challenge(db_session, date(2026, 7, 1))
    await get_or_create_challenge(db_session, date(2026, 7, 2))
    await get_or_create_challenge(db_session, date(2026, 7, 3))
    assert await challenge_number(db_session, date(2026, 7, 2)) == 2
    assert await challenge_number(db_session, date(2026, 7, 3)) == 3


def test_tier_for_green_requires_no_hints_and_under_60s():
    from app.features.daily.service import tier_for

    assert tier_for(correct=True, hints_used=0, time_taken_seconds=59) == "green"


def test_tier_for_yellow_with_hint_or_slow():
    from app.features.daily.service import tier_for

    assert tier_for(correct=True, hints_used=1, time_taken_seconds=10) == "yellow"
    assert tier_for(correct=True, hints_used=0, time_taken_seconds=61) == "yellow"


def test_tier_for_red_when_incorrect():
    from app.features.daily.service import tier_for

    assert tier_for(correct=False, hints_used=0, time_taken_seconds=5) == "red"


async def test_submit_attempt_persists_for_logged_in_user_and_returns_streak(db_session):
    # submit_attempt resolves "today" itself via today_vn() - the test must
    # anchor on that same value rather than a hardcoded date, or this becomes
    # a test that only passes when run on one specific calendar day.
    from app.features.daily.service import get_or_create_challenge, submit_attempt, today_vn

    d = today_vn()
    challenge = await get_or_create_challenge(db_session, d)
    user = await _make_user(db_session)

    result = await submit_attempt(
        db_session, user.id, selected_line=challenge.buggy_line, hints_used=0, time_taken_seconds=30
    )
    assert result["correct"] is True
    assert result["tier"] == "green"
    assert result["buggy_line"] == challenge.buggy_line
    assert result["streak"] == 1


async def test_submit_attempt_anonymous_does_not_persist_and_streak_is_none(db_session):
    from app.features.daily.service import get_or_create_challenge, submit_attempt, today_vn
    from app.models import DailyAttempt
    from sqlalchemy import select

    d = today_vn()
    challenge = await get_or_create_challenge(db_session, d)

    result = await submit_attempt(
        db_session, None, selected_line=challenge.buggy_line, hints_used=0, time_taken_seconds=10
    )
    assert result["streak"] is None
    rows = (await db_session.execute(select(DailyAttempt))).scalars().all()
    assert rows == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.features.daily.service'`.

- [ ] **Step 4: Implement the service module**

Create `app/features/daily/service.py`:

```python
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.daily.content import generate_challenge
from app.features.daily.streak import compute_streak
from app.models import DailyAttempt, DailyChallenge

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def today_vn() -> date:
    return datetime.now(VN_TZ).date()


async def get_or_create_challenge(db: AsyncSession, challenge_date: date) -> DailyChallenge:
    existing = (
        await db.execute(select(DailyChallenge).where(DailyChallenge.challenge_date == challenge_date))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    try:
        return await generate_challenge(db, challenge_date)
    except IntegrityError:
        # Two simultaneous first-visitors-of-the-day both tried to generate;
        # the loser just reads back what the winner committed.
        await db.rollback()
        return (
            await db.execute(select(DailyChallenge).where(DailyChallenge.challenge_date == challenge_date))
        ).scalar_one()


async def challenge_number(db: AsyncSession, challenge_date: date) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(DailyChallenge)
            .where(DailyChallenge.challenge_date <= challenge_date)
        )
    ).scalar_one()


async def get_attempt(db: AsyncSession, user_id: int, challenge_date: date) -> DailyAttempt | None:
    return (
        await db.execute(
            select(DailyAttempt).where(
                DailyAttempt.user_id == user_id, DailyAttempt.challenge_date == challenge_date
            )
        )
    ).scalar_one_or_none()


async def user_streak(db: AsyncSession, user_id: int, today: date) -> int:
    rows = (
        await db.execute(
            select(DailyAttempt.challenge_date).where(
                DailyAttempt.user_id == user_id, DailyAttempt.submitted_at.is_not(None)
            )
        )
    ).scalars().all()
    return compute_streak(set(rows), today)


def tier_for(correct: bool, hints_used: int, time_taken_seconds: int) -> str:
    if not correct:
        return "red"
    if hints_used == 0 and time_taken_seconds < 60:
        return "green"
    return "yellow"


async def submit_attempt(
    db: AsyncSession,
    user_id: int | None,
    selected_line: int,
    hints_used: int,
    time_taken_seconds: int,
) -> dict:
    today = today_vn()
    challenge = await get_or_create_challenge(db, today)
    correct = selected_line == challenge.buggy_line
    tier = tier_for(correct, hints_used, time_taken_seconds)

    streak: int | None = None
    if user_id is not None:
        attempt = await get_attempt(db, user_id, today)
        if attempt is None:
            attempt = DailyAttempt(user_id=user_id, challenge_date=today)
            db.add(attempt)
        attempt.selected_line = selected_line
        attempt.hints_used = hints_used
        attempt.time_taken_seconds = time_taken_seconds
        attempt.tier = tier
        attempt.submitted_at = datetime.now(timezone.utc)
        await db.commit()
        streak = await user_streak(db, user_id, today)

    return {
        "correct": correct,
        "tier": tier,
        "buggy_line": challenge.buggy_line,
        "explanation": challenge.explanation,
        "streak": streak,
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_service.py tests/test_daily_streak.py tests/test_daily_content.py tests/test_daily_models.py -v`
Expected: all passed (this task's file plus every earlier daily-feature test file, to catch regressions).

- [ ] **Step 6: Commit**

```bash
git add app/features/daily/service.py requirements.txt tests/test_daily_service.py
git commit -m "feat: add daily bug hunt service layer (get-or-create, submit, streak)"
```

---

### Task 5: Schemas, router, optional-auth dependency, wiring into `main.py`

**Files:**
- Create: `app/schemas/daily.py`
- Create: `app/features/daily/router.py`
- Modify: `app/core/deps.py`
- Modify: `app/core/config.py`
- Modify: `app/main.py`
- Test: `tests/test_daily_router.py`

**Interfaces:**
- Consumes: everything from Task 4's `service.py`.
- Produces: `get_current_user_optional` dependency (used again by Task 6); the live `GET /api/daily/today`, `POST /api/daily/attempt`, `POST /api/daily/regenerate` endpoints.

- [ ] **Step 1: Add the optional-auth dependency**

Modify `app/core/deps.py` - append this function at the end of the file (do not change `get_current_user`):

```python


async def get_current_user_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Same identity resolution as get_current_user, but returns None instead
    of raising 401 - for endpoints that must work for anonymous visitors too
    (Daily Bug Hunt, spec section 7)."""
    if creds is None:
        return None
    sub = decode_token(creds.credentials)
    if sub is None:
        return None
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None
    return (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
```

- [ ] **Step 2: Add the admin key setting**

Modify `app/core/config.py` - add one field to the `Settings` class (insert after `sandbox_timeout: int = 5`):

```python
    # Shared-secret for the daily-challenge regenerate ops endpoint. Empty by
    # default so the endpoint is a no-op (always 403) until an operator sets
    # it - there is no user-role/admin system in this codebase to hook into.
    admin_api_key: str = ""
```

- [ ] **Step 3: Write the schemas**

Create `app/schemas/daily.py`:

```python
from pydantic import BaseModel


class DailyResult(BaseModel):
    correct: bool
    tier: str
    buggy_line: int
    explanation: str
    hints_used: int
    time_taken_seconds: int


class DailyChallengeOut(BaseModel):
    challenge_number: int
    prompt_title: str
    buggy_code: str
    already_played: bool
    result: DailyResult | None = None


class DailyAttemptIn(BaseModel):
    selected_line: int
    hints_used: int = 0
    time_taken_seconds: int


class DailyAttemptOut(BaseModel):
    correct: bool
    tier: str
    buggy_line: int
    explanation: str
    streak: int | None = None
```

- [ ] **Step 4: Write the failing router tests**

Create `tests/test_daily_router.py`:

```python
import pytest

pytestmark = pytest.mark.asyncio


class FakeJudgeClient:
    _model = "fake"

    async def judge(self, system, user):
        return {
            "buggy_code": "def f():\n    return 1",
            "buggy_line": 2,
            "bug_category": "off-by-one",
            "hint_1": "h1",
            "hint_2": "h2",
            "explanation": "e",
        }


@pytest.fixture(autouse=True)
def _patch_mentor_client(monkeypatch):
    import app.features.daily.content as content_mod

    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: FakeJudgeClient())


async def test_today_works_without_auth(client):
    r = await client.get("/api/daily/today")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["already_played"] is False
    assert body["result"] is None
    assert "buggy_line" not in body  # never leak the answer before submit
    assert body["challenge_number"] >= 1


async def test_attempt_works_without_auth_and_does_not_return_streak(client):
    r = await client.post(
        "/api/daily/attempt",
        json={"selected_line": 2, "hints_used": 0, "time_taken_seconds": 10},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["correct"] is True
    assert body["tier"] == "green"
    assert body["streak"] is None


async def test_attempt_with_auth_returns_streak_and_today_reflects_result(client, auth_headers):
    r = await client.post(
        "/api/daily/attempt",
        json={"selected_line": 2, "hints_used": 1, "time_taken_seconds": 90},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["streak"] == 1
    assert r.json()["tier"] == "yellow"

    today = await client.get("/api/daily/today", headers=auth_headers)
    body = today.json()
    assert body["already_played"] is True
    assert body["result"]["tier"] == "yellow"


async def test_attempt_twice_same_day_returns_409(client, auth_headers):
    payload = {"selected_line": 2, "hints_used": 0, "time_taken_seconds": 10}
    r1 = await client.post("/api/daily/attempt", json=payload, headers=auth_headers)
    assert r1.status_code == 200
    r2 = await client.post("/api/daily/attempt", json=payload, headers=auth_headers)
    assert r2.status_code == 409


async def test_regenerate_requires_admin_key(client, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
    get_settings.cache_clear()

    forbidden = await client.post("/api/daily/regenerate", headers={"X-Admin-Key": "wrong"})
    assert forbidden.status_code == 403

    ok = await client.post("/api/daily/regenerate", headers={"X-Admin-Key": "s3cret"})
    assert ok.status_code == 200

    get_settings.cache_clear()
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_router.py -v`
Expected: FAIL - `/api/daily/today` returns 404 (router not registered yet).

- [ ] **Step 6: Implement the router**

Create `app/features/daily/router.py`:

```python
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user_optional
from app.features.daily import service
from app.models import DailyChallenge, User
from app.schemas.daily import DailyAttemptIn, DailyAttemptOut, DailyChallengeOut, DailyResult

router = APIRouter(prefix="/api/daily", tags=["daily"])


@router.get("/today", response_model=DailyChallengeOut)
async def today(
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> DailyChallengeOut:
    d = service.today_vn()
    challenge = await service.get_or_create_challenge(db, d)
    num = await service.challenge_number(db, d)

    result = None
    already_played = False
    if user is not None:
        attempt = await service.get_attempt(db, user.id, d)
        if attempt is not None and attempt.submitted_at is not None:
            already_played = True
            result = DailyResult(
                correct=attempt.selected_line == challenge.buggy_line,
                tier=attempt.tier or "red",
                buggy_line=challenge.buggy_line,
                explanation=challenge.explanation,
                hints_used=attempt.hints_used,
                time_taken_seconds=attempt.time_taken_seconds or 0,
            )
    return DailyChallengeOut(
        challenge_number=num,
        prompt_title=challenge.prompt_title,
        buggy_code=challenge.buggy_code,
        already_played=already_played,
        result=result,
    )


@router.post("/attempt", response_model=DailyAttemptOut)
async def attempt(
    data: DailyAttemptIn,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> DailyAttemptOut:
    today_date = service.today_vn()
    if user is not None:
        existing = await service.get_attempt(db, user.id, today_date)
        if existing is not None and existing.submitted_at is not None:
            raise HTTPException(status_code=409, detail="Already played today")
    result = await service.submit_attempt(
        db,
        user.id if user is not None else None,
        data.selected_line,
        data.hints_used,
        data.time_taken_seconds,
    )
    return DailyAttemptOut(**result)


@router.post("/regenerate")
async def regenerate(
    x_admin_key: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = get_settings()
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    d = service.today_vn()
    existing = (
        await db.execute(select(DailyChallenge).where(DailyChallenge.challenge_date == d))
    ).scalar_one_or_none()
    if existing is not None:
        await db.delete(existing)
        await db.commit()
    challenge = await service.get_or_create_challenge(db, d)
    return {"regenerated": True, "prompt_title": challenge.prompt_title}
```

- [ ] **Step 7: Register the router**

Modify `app/main.py` - add these two lines after the `dashboard_router` block (keep everything else unchanged):

```python
    from app.features.daily.router import router as daily_router
    app.include_router(daily_router)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_router.py -v`
Expected: 5 passed.

- [ ] **Step 9: Run the full daily-feature suite plus a full regression pass**

Run: `cd codeprove-backend && python -m pytest tests/ -v`
Expected: all tests pass, including every pre-existing test file (no regressions from the new router/dependency/config changes).

- [ ] **Step 10: Commit**

```bash
git add app/schemas/daily.py app/features/daily/router.py app/core/deps.py app/core/config.py \
        app/main.py tests/test_daily_router.py
git commit -m "feat: add daily bug hunt API endpoints (today, attempt, regenerate)"
```

---

### Task 6: Claim-streak endpoint (merge anonymous history into an account)

**Files:**
- Modify: `app/features/daily/service.py`
- Modify: `app/schemas/daily.py`
- Modify: `app/features/daily/router.py`
- Test: `tests/test_daily_claim_streak.py`

**Interfaces:**
- Consumes: `get_attempt`, `tier_for`, `user_streak` (Task 4); `get_current_user` (existing, required auth - claiming needs a real account, unlike the other two endpoints).
- Produces: `async def claim_streak(db: AsyncSession, user_id: int, history: list[dict]) -> int` in `service.py`; `POST /api/daily/claim-streak`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_daily_claim_streak.py`:

```python
import pytest
from datetime import timedelta

pytestmark = pytest.mark.asyncio


class FakeJudgeClient:
    _model = "fake"

    async def judge(self, system, user):
        return {
            "buggy_code": "def f():\n    return 1",
            "buggy_line": 2,
            "bug_category": "off-by-one",
            "hint_1": "h1",
            "hint_2": "h2",
            "explanation": "e",
        }


@pytest.fixture(autouse=True)
def _patch_mentor_client(monkeypatch):
    import app.features.daily.content as content_mod

    monkeypatch.setattr(content_mod, "get_mentor_client", lambda: FakeJudgeClient())


async def test_claim_streak_creates_attempts_for_known_dates(client, db_session, auth_headers):
    # claim_streak resolves "today" itself via today_vn() (for the final
    # streak read) and the earlier /attempt calls in other tests do the same -
    # anchor every date here on today_vn() too, not a hardcoded literal.
    from app.features.daily.service import get_or_create_challenge, today_vn

    today = today_vn()
    yesterday = today - timedelta(days=1)
    await get_or_create_challenge(db_session, today)
    await get_or_create_challenge(db_session, yesterday)

    r = await client.post(
        "/api/daily/claim-streak",
        json={
            "history": [
                {"date": today.isoformat(), "selected_line": 2, "hints_used": 0, "time_taken_seconds": 30},
                {"date": yesterday.isoformat(), "selected_line": 1, "hints_used": 2, "time_taken_seconds": 100},
            ]
        },
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["streak"] == 2


async def test_claim_streak_skips_dates_without_a_challenge(client, auth_headers):
    r = await client.post(
        "/api/daily/claim-streak",
        json={"history": [{"date": "2020-01-01", "selected_line": 1, "hints_used": 0, "time_taken_seconds": 5}]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["streak"] == 0


async def test_claim_streak_never_overwrites_an_existing_real_attempt(client, db_session, auth_headers):
    from app.features.daily.service import get_or_create_challenge, today_vn

    today = today_vn()
    challenge = await get_or_create_challenge(db_session, today)

    real = await client.post(
        "/api/daily/attempt",
        json={"selected_line": challenge.buggy_line, "hints_used": 0, "time_taken_seconds": 5},
        headers=auth_headers,
    )
    assert real.status_code == 200

    # A claim with a *wrong* selected_line for the same day must not clobber
    # the real green result already recorded.
    claim = await client.post(
        "/api/daily/claim-streak",
        json={"history": [{"date": today.isoformat(), "selected_line": 999, "hints_used": 2, "time_taken_seconds": 200}]},
        headers=auth_headers,
    )
    assert claim.status_code == 200

    today_state = await client.get("/api/daily/today", headers=auth_headers)
    assert today_state.json()["result"]["tier"] == "green"


async def test_claim_streak_requires_auth(client):
    r = await client.post("/api/daily/claim-streak", json={"history": []})
    assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_claim_streak.py -v`
Expected: FAIL - `/api/daily/claim-streak` returns 404 (endpoint doesn't exist yet).

- [ ] **Step 3: Add `claim_streak` to the service**

Modify `app/features/daily/service.py` - add this function at the end of the file:

```python


async def claim_streak(db: AsyncSession, user_id: int, history: list[dict]) -> int:
    """Merge a client's localStorage play history into real DailyAttempt rows.

    Skips any date with no matching DailyChallenge (can't verify a tier for
    it) and never overwrites a date that already has a real submitted
    attempt for this user (spec section 5 - claiming must not clobber real
    play with replayed/edited client data).
    """
    for item in history:
        try:
            challenge_date = date.fromisoformat(item["date"])
        except (KeyError, ValueError, TypeError):
            continue
        challenge = (
            await db.execute(select(DailyChallenge).where(DailyChallenge.challenge_date == challenge_date))
        ).scalar_one_or_none()
        if challenge is None:
            continue

        existing = await get_attempt(db, user_id, challenge_date)
        if existing is not None and existing.submitted_at is not None:
            continue

        selected_line = item.get("selected_line", 0)
        hints_used = item.get("hints_used", 0)
        time_taken_seconds = item.get("time_taken_seconds", 0)
        correct = selected_line == challenge.buggy_line
        tier = tier_for(correct, hints_used, time_taken_seconds)

        if existing is None:
            existing = DailyAttempt(user_id=user_id, challenge_date=challenge_date)
            db.add(existing)
        existing.selected_line = selected_line
        existing.hints_used = hints_used
        existing.time_taken_seconds = time_taken_seconds
        existing.tier = tier
        existing.submitted_at = datetime.now(timezone.utc)

    await db.commit()
    return await user_streak(db, user_id, today_vn())
```

- [ ] **Step 4: Add the request/response schemas**

Modify `app/schemas/daily.py` - append at the end of the file:

```python


class ClaimHistoryItem(BaseModel):
    date: str
    selected_line: int
    hints_used: int = 0
    time_taken_seconds: int = 0


class ClaimStreakIn(BaseModel):
    history: list[ClaimHistoryItem]


class ClaimStreakOut(BaseModel):
    streak: int
```

- [ ] **Step 5: Add the endpoint**

Modify `app/features/daily/router.py` - change the import line:

```python
from app.core.deps import get_current_user_optional
```

to:

```python
from app.core.deps import get_current_user, get_current_user_optional
```

and change the schemas import line:

```python
from app.schemas.daily import DailyAttemptIn, DailyAttemptOut, DailyChallengeOut, DailyResult
```

to:

```python
from app.schemas.daily import (
    ClaimStreakIn,
    ClaimStreakOut,
    DailyAttemptIn,
    DailyAttemptOut,
    DailyChallengeOut,
    DailyResult,
)
```

then append this new endpoint at the end of the file:

```python


@router.post("/claim-streak", response_model=ClaimStreakOut)
async def claim_streak(
    data: ClaimStreakIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ClaimStreakOut:
    streak = await service.claim_streak(db, user.id, [item.model_dump() for item in data.history])
    return ClaimStreakOut(streak=streak)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd codeprove-backend && python -m pytest tests/test_daily_claim_streak.py -v`
Expected: 4 passed.

- [ ] **Step 7: Full regression pass**

Run: `cd codeprove-backend && python -m pytest tests/ -v`
Expected: all tests pass (every file from Tasks 1-6 plus every pre-existing test file).

- [ ] **Step 8: Commit**

```bash
git add app/features/daily/service.py app/schemas/daily.py app/features/daily/router.py \
        tests/test_daily_claim_streak.py
git commit -m "feat: add daily bug hunt claim-streak endpoint for anonymous-to-account merge"
```

---

### Final verification (after all 6 tasks)

- [ ] Run `cd codeprove-backend && python -m pytest tests/ -v` - expect zero failures across the whole suite (pre-existing tests + all new `test_daily_*` files).
- [ ] Manually start the API (`uvicorn app.main:app --reload`, per `RUNBOOK.md`) and hit `GET /api/daily/today` with curl/Swagger (`/docs`) with no `Authorization` header - confirm it returns 200 with no `buggy_line` in the body.
- [ ] Confirm `alembic upgrade head` applies the new migration cleanly against a real (non-sqlite) Postgres dev database, matching the `RUNBOOK.md` workflow used for prior migrations.
