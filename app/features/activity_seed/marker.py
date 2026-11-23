"""How seeded (operator-generated) attempts are recognised.

A seeded attempt has no events, so anything that recomputes from events (rescore), calibrates
exercises (learner difficulty Elo), samples sessions for human raters, or meters real usage
(monthly submit quota) must skip it. The marker lives in the report's feedback JSON.
"""
from typing import Any

SEED_KEY = "seed_batch"


def seed_batch_of(feedback: Any) -> str | None:
    if isinstance(feedback, dict):
        batch = feedback.get(SEED_KEY)
        return batch if isinstance(batch, str) else None
    return None


def is_seeded(feedback: Any) -> bool:
    return seed_batch_of(feedback) is not None
