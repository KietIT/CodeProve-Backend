"""Evaluate the student's tests when an attempt is submitted (P2.3).

Each saved test is checked against the reference (valid = the reference gives
the expected value); the valid tests then run against every validated mutant of
the exercise, and a mutant is killed when one of them fails on it. The result
is one STUDENT_TESTS event, written even when there are no tests, so the
rubric can tell "wrote no tests" from "a session before the Tests tab".
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.attempts import service
from app.features.sandbox.runner import run_tests
from app.features.student_tests.safety import check_input, module_names
from app.features.student_tests.service import as_case, saved_tests
from app.models import Attempt, Exercise, ExerciseMutant, TestCase


async def evaluate(db: AsyncSession, attempt: Attempt, ex: Exercise) -> dict | None:
    if not ex.student_tests or not ex.reference_solution:
        return None
    timeout = get_settings().sandbox_timeout
    tests = await saved_tests(db, attempt.id)
    allowed = module_names(ex.reference_solution)
    reasons = [check_input(test["input"], allowed) for test in tests]
    runnable = [i for i, reason in enumerate(reasons) if reason is None]
    valid = [False] * len(tests)
    if runnable:
        ref = await run_tests(ex.reference_solution, [as_case(tests[i], i) for i in runnable], timeout)
        for i, case in zip(runnable, ref["cases"]):
            valid[i] = bool(case["passed"])
            if not case["passed"]:
                reasons[i] = "error" if case.get("error") else "wrong_expected"
    valid_cases = [as_case(tests[i], i) for i in range(len(tests)) if valid[i]]

    mutants = (await db.execute(select(ExerciseMutant).where(ExerciseMutant.exercise_id == ex.id)
                                .order_by(ExerciseMutant.order_index))).scalars().all()

    async def killed(mutant: ExerciseMutant) -> bool:
        if not valid_cases:
            return False
        result = await run_tests(mutant.code, valid_cases, timeout)
        return result["passed"] < result["total"]

    kills = await asyncio.gather(*(killed(m) for m in mutants))
    categories = (await db.execute(select(TestCase.category).where(TestCase.exercise_id == ex.id,
                                                                   TestCase.category.is_not(None)))).scalars().all()
    payload = {
        "tests": [{**test, "valid": valid[i], "reason": None if valid[i] else reasons[i]}
                  for i, test in enumerate(tests)],
        "categories": sorted({tests[i]["category"] for i in range(len(tests)) if valid[i]}),
        "exercise_categories": sorted(set(categories)),
        "mutants": [{"id": m.id, "bug_type": m.bug_type, "killed": k} for m, k in zip(mutants, kills)],
        "killed": sum(kills),
        "total": len(mutants),
    }
    await service.add_event(db, attempt.id, "STUDENT_TESTS", payload)
    return payload
