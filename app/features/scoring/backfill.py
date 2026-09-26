"""Ask the rubric v2 judges for verdicts a session is missing (P1.4).

Sessions scored before the judges existed have no rubric levels. Each missing
verdict is asked once and stored as a new JUDGE event (events are append-only;
a hypothesis verdict points at its HYPOTHESIS event with `for_ts`), so later
rescoring reuses it instead of asking again. The v1 inputs (explain-back score,
hypothesis verdict) are left untouched.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.attempts import service as attempts_service
from app.features.attempts.scoring_service import judge_and_store_prompts
from app.features.scoring.judges import is_non_answer, judge_explain, judge_hypothesis
from app.models import Attempt, Event, Exercise, VerificationAnswer


async def backfill_judges(db: AsyncSession, attempt: Attempt, client) -> int:
    """Store the missing verdicts for one attempt; returns how many judge calls were made."""
    events = (await db.execute(select(Event).where(Event.attempt_id == attempt.id))).scalars().all()
    judged = [e.payload for e in events if e.type == "JUDGE"]
    judged_kinds = {p.get("kind") for p in judged}
    problem = (await db.execute(select(Exercise.summary).where(Exercise.id == attempt.exercise_id))).scalar_one()
    calls = 0

    if "explain" not in judged_kinds:
        answers = (await db.execute(select(VerificationAnswer).where(VerificationAnswer.attempt_id == attempt.id)
                                    .order_by(VerificationAnswer.id))).scalars().all()
        if answers:
            verdicts = [await judge_explain(client, a.question, a.answer) for a in answers]
            calls += sum(1 for a in answers if not is_non_answer(a.answer))  # non-answers skip the call
            await attempts_service.add_event(db, attempt.id, "JUDGE", {
                "kind": "explain", "model": client._model, "backfilled": True,
                "levels": [v["level"] for v in verdicts], "evidence": [v["evidence"] for v in verdicts]})

    if "prompts" not in judged_kinds and await judge_and_store_prompts(db, attempt, problem, client,
                                                                      backfilled=True):
        calls += 1

    done = {p.get("for_ts") for p in judged if p.get("kind") == "hypothesis"}
    for e in events:
        p = e.payload or {}
        if (e.type != "HYPOTHESIS" or p.get("proposedBy", "user") != "user" or isinstance(p.get("level"), int)
                or not p.get("text") or e.ts in done):
            continue
        verdict = await judge_hypothesis(client, problem, p["text"])
        calls += 1
        await attempts_service.add_event(db, attempt.id, "JUDGE", {
            "kind": "hypothesis", "model": client._model, "backfilled": True, "for_ts": e.ts,
            "level": verdict["level"], "evidence": verdict["evidence"]})
    await db.flush()
    return calls
