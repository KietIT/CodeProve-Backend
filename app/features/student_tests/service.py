"""Student-written tests during an attempt (P2.3): save, check, run on own code.

A check runs one test against the reference solution and answers only valid /
wrong_expected / error (for an error: the allow-list reason or the exception
type), never the reference's output. Running the saved tests on the student's
own code shows actual values: that code is theirs.
"""
import ast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.attempts import service
from app.features.sandbox.runner import run_tests
from app.features.student_tests.safety import check_input, module_names
from app.models import Attempt, Event, Exercise

MAX_TESTS = 10
REQUIRED_VALID = 3  # junior/senior: valid tests needed for full marks


def normalize_expected(expected: str) -> str:
    """The repr the sandbox compares with, so `[0,1]` and `[0, 1]` match; free text stays as written."""
    try:
        return repr(ast.literal_eval(expected.strip()))
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return expected.strip()


def as_case(test: dict, i: int) -> dict:
    return {"input_data": test["input"], "expected_output": normalize_expected(test["expected"]),
            "description": f"student test {i}", "weight": 1.0}


def _error_type(error: str | None) -> str:
    return (error or "Error").split(":", 1)[0].strip() or "Error"


def _require_tab(ex: Exercise) -> None:
    if not ex.student_tests or not ex.reference_solution:
        raise HTTPException(status_code=400, detail="This exercise has no Tests tab")


def _require_open(attempt: Attempt) -> None:
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt already submitted")


async def saved_tests(db: AsyncSession, attempt_id: int) -> list[dict]:
    row = (await db.execute(select(Event).where(Event.attempt_id == attempt_id, Event.type == "TESTS_SAVED")
                            .order_by(Event.id.desc()))).scalars().first()
    return list((row.payload or {}).get("tests") or []) if row else []


async def state(db: AsyncSession, attempt: Attempt, ex: Exercise) -> dict | None:
    if not ex.student_tests:
        return None
    return {"enabled": True, "required": ex.level != "fresher", "tests": await saved_tests(db, attempt.id)}


async def save(db: AsyncSession, attempt: Attempt, ex: Exercise, tests: list[dict]) -> None:
    _require_tab(ex)
    _require_open(attempt)
    await service.add_event(db, attempt.id, "TESTS_SAVED", {"tests": tests})
    await db.commit()


async def check(db: AsyncSession, attempt: Attempt, ex: Exercise, test: dict) -> dict:
    _require_tab(ex)
    _require_open(attempt)
    reason = check_input(test["input"], module_names(ex.reference_solution))
    if reason:
        status = "error"
    else:
        result = await run_tests(ex.reference_solution, [as_case(test, 1)], get_settings().sandbox_timeout)
        case = result["cases"][0]
        if case["passed"]:
            status = "valid"
        elif case.get("error") or result.get("runtime_error"):
            status, reason = "error", _error_type(case.get("error") or result.get("runtime_error"))
        else:
            status = "wrong_expected"
    await service.add_event(db, attempt.id, "TEST_CHECK", {"input": test["input"], "status": status})
    await db.commit()
    return {"status": status, "reason": reason}


async def run_on_own_code(db: AsyncSession, attempt: Attempt, ex: Exercise, source_code: str) -> list[dict]:
    """The saved tests on the student's code; inputs outside the rules are not run (same as at submit)."""
    _require_tab(ex)
    tests = await saved_tests(db, attempt.id)
    allowed = module_names(ex.reference_solution)
    refused = {i: check_input(t["input"], allowed) for i, t in enumerate(tests)}
    runnable = [(i, t) for i, t in enumerate(tests) if refused[i] is None]
    result = await run_tests(source_code, [as_case(t, i) for i, t in runnable], get_settings().sandbox_timeout) \
        if runnable else {"cases": []}
    by_index = {i: case for (i, _), case in zip(runnable, result["cases"])}
    out = []
    for i in range(len(tests)):
        if refused[i]:
            out.append({"passed": False, "actual": None, "error": refused[i]})
        else:
            case = by_index[i]
            out.append({"passed": bool(case["passed"]), "actual": case.get("actual"), "error": case.get("error")})
    return out
