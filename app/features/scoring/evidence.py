"""Everything rubric v2 scores from, gathered for one attempt (P1.4).

Events carry the timeline, but Ciel's reply text lives in prompt logs and the
code in snapshots, so v1's event-only features cannot tell pasting AI code from
fixing it. `load_evidence` collects all of it; the rubric stays pure over the
result. Times are epoch milliseconds throughout.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attempt, CodeSnapshot, Event, Exercise, PromptLog, VerificationAnswer

_CODE_BLOCK = re.compile(r"```[\w+-]*\n(.*?)```", re.DOTALL)


def code_blocks(text: str | None) -> list[str]:
    """Fenced code blocks of a chat reply (inline `code` is not a block)."""
    return [b.strip("\n") for b in _CODE_BLOCK.findall(text or "")]


def code_lines(code: str) -> list[str]:
    """Code lines compared by content: indentation, blank lines and comment lines dropped."""
    lines = (line.strip() for line in code.replace("\r\n", "\n").split("\n"))
    return [line for line in lines if line and not line.startswith("#")]


def adopted(block: str, code: str) -> float:
    """Share of the block's code lines that appear in `code` (0.0-1.0),
    ignoring indentation, blank lines and comments."""
    wanted = code_lines(block)
    if not wanted:
        return 0.0
    present = set(code_lines(code))
    return round(sum(line in present for line in wanted) / len(wanted), 3)


def _ms(moment: datetime) -> int:
    if moment.tzinfo is None:  # SQLite returns naive datetimes; they are UTC
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp() * 1000)


@dataclass(frozen=True)
class Reply:
    """One exchange with Ciel."""

    prompt: str
    text: str
    at_ms: int
    injected: bool

    @property
    def blocks(self) -> list[str]:
        return code_blocks(self.text)


@dataclass(frozen=True)
class Snapshot:
    version: int
    code: str
    at_ms: int


@dataclass
class Evidence:
    exercise_kind: str
    events: list[dict] = field(default_factory=list)  # sorted by ts
    replies: list[Reply] = field(default_factory=list)
    snapshots: list[Snapshot] = field(default_factory=list)  # sorted by time
    answers: list[dict] = field(default_factory=list)  # explain-back {question, answer}

    @property
    def final_code(self) -> str:
        # Same rule as attempts.service.latest_code: the highest version.
        return max(self.snapshots, key=lambda s: s.version).code if self.snapshots else ""

    @property
    def submit_suite(self) -> dict | None:
        suites = [e["payload"] for e in self.events if e["type"] == "SUBMIT_TESTS"]
        return suites[-1] if suites else None

    @property
    def runs(self) -> list[dict]:
        return [e for e in self.events if e["type"] == "RUN"]

    @property
    def judges(self) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for e in self.events:
            if e["type"] == "JUDGE":
                out.setdefault(e["payload"].get("kind", ""), []).append(e["payload"])
        return out

    def code_at(self, at_ms: int) -> str | None:
        """The editor code as last saved at or before `at_ms`."""
        before = [s for s in self.snapshots if s.at_ms <= at_ms]
        return before[-1].code if before else None

    def runs_after(self, at_ms: int) -> list[dict]:
        return [e["payload"] for e in self.runs if e["ts"] > at_ms]


async def load_evidence(db: AsyncSession, attempt: Attempt) -> Evidence:
    kind = (await db.execute(select(Exercise.kind).where(Exercise.id == attempt.exercise_id))).scalar_one()
    events = [
        {"type": e.type, "ts": e.ts, "payload": e.payload or {}, "integrity_flags": e.integrity_flags or []}
        for e in (await db.execute(select(Event).where(Event.attempt_id == attempt.id))).scalars().all()
    ]
    events.sort(key=lambda e: e["ts"])
    logs = (await db.execute(
        select(PromptLog).where(PromptLog.attempt_id == attempt.id).order_by(PromptLog.id))).scalars().all()
    # AI_REPLY events and prompt logs are written together, in the same order.
    ai_replies = [e for e in events if e["type"] == "AI_REPLY"]
    replies = [
        Reply(prompt=log.prompt or "", text=log.response or "", at_ms=_ms(log.created_at),
              injected=bool(ai_replies[i]["payload"].get("injectedError")) if i < len(ai_replies) else False)
        for i, log in enumerate(logs)
    ]
    snapshots = sorted(
        (Snapshot(version=s.version, code=s.source_code or "", at_ms=_ms(s.created_at))
         for s in (await db.execute(select(CodeSnapshot).where(CodeSnapshot.attempt_id == attempt.id))).scalars()),
        key=lambda s: (s.at_ms, s.version),
    )
    answers = [
        {"question": a.question, "answer": a.answer}
        for a in (await db.execute(select(VerificationAnswer).where(VerificationAnswer.attempt_id == attempt.id)
                                   .order_by(VerificationAnswer.id))).scalars()
    ]
    return Evidence(exercise_kind=kind or "implement", events=events, replies=replies, snapshots=snapshots,
                    answers=answers)
