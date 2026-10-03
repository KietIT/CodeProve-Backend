"""Authenticated authoring workflow for exercises.

The draft row is the mutable source for admin-managed content. The public exercise
row changes only after a distinct admin approves the same revision and it passes
the existing sandbox validator again at publish time.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select, union_all, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.db import get_db
from app.features.admin import service
from app.features.admin.router import Principal, ready_admin
from app.features.content.schema import ExerciseContent
from app.features.content.sync import _write
from app.features.content.validate import validate_content
from app.models import Exercise, ExerciseDraft, ExerciseMutant, TestCase, User

router = APIRouter(prefix="/api/admin/exercises", tags=["admin exercises"])


class DraftTest(BaseModel):
    description: str = Field(default="", max_length=500)
    input: str = Field(default="", max_length=10000)
    expected: str = Field(default="", max_length=10000)
    category: Literal["happy", "boundary", "edge", "error"] = "happy"
    hidden: bool = True


class DraftMutant(BaseModel):
    code: str = Field(default="", max_length=50000)
    bug_line: int = Field(default=1, ge=1)
    bug_type: str = Field(default="", max_length=32)
    note_vi: str = Field(default="", max_length=1000)
    note_en: str = Field(default="", max_length=1000)


class DraftPayload(BaseModel):
    code: str = Field(pattern=r"^CP-[0-9]{3}$")
    title: str = Field(min_length=1, max_length=255)
    difficulty: Literal["Easy", "Medium", "Hard"]
    category: str = Field(min_length=1, max_length=64)
    level: Literal["fresher", "junior", "senior"]
    kind: Literal["implement", "debug"]
    language: Literal["python"] = "python"
    description: str = Field(default="", max_length=50000)
    learning_objective: str = Field(default="", max_length=50000)
    domain_keywords: list[str] = Field(default_factory=list, max_length=30)
    summary: str = Field(default="", max_length=50000)
    starter_code: str = Field(default="", max_length=50000)
    hint: str = Field(default="", max_length=10000)
    reference_solution: str = Field(default="", max_length=50000)
    tests: list[DraftTest] = Field(default_factory=list, max_length=20)
    mutants: list[DraftMutant] = Field(default_factory=list, max_length=10)
    skills: list[str] = Field(default_factory=list, max_length=20)
    debug: dict | None = None
    limits: dict | None = None


class SaveDraftIn(BaseModel):
    expected_revision: int = Field(ge=1)
    payload: DraftPayload


class RevisionIn(BaseModel):
    expected_revision: int = Field(ge=1)


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Exercise draft not found")


def _conflict() -> HTTPException:
    return HTTPException(status_code=409, detail="Draft changed or is in another workflow state; reload it")


async def _draft(db: AsyncSession, code: str) -> ExerciseDraft:
    row = (await db.execute(select(ExerciseDraft).where(ExerciseDraft.code == code.upper()))).scalar_one_or_none()
    if row is None:
        raise _not_found()
    return row


async def _exercise(db: AsyncSession, code: str) -> Exercise | None:
    return (await db.execute(select(Exercise).where(Exercise.code == code.upper()))).scalar_one_or_none()


def _public_row(row: ExerciseDraft) -> dict:
    return {
        "code": row.code, "payload": row.payload, "status": row.status,
        "revision": row.revision, "author_user_id": row.author_user_id,
        "reviewer_user_id": row.reviewer_user_id, "updated_at": row.updated_at,
    }


async def _snapshot(db: AsyncSession, ex: Exercise) -> DraftPayload:
    tests = (await db.execute(select(TestCase).where(TestCase.exercise_id == ex.id)
                              .order_by(TestCase.order_index))).scalars().all()
    mutants = (await db.execute(select(ExerciseMutant).where(ExerciseMutant.exercise_id == ex.id)
                                .order_by(ExerciseMutant.order_index))).scalars().all()
    debug = None
    if ex.debug_meta:
        debug = {key: ex.debug_meta[key] for key in ("regions", "explanation_vi", "explanation_en", "hint_vi", "hint_en")
                 if key in ex.debug_meta}
    return DraftPayload(
        code=ex.code, title=ex.title, difficulty=ex.difficulty, category=ex.category,
        level=ex.level, kind=ex.kind, language=ex.language, description=ex.description,
        learning_objective=ex.learning_objective, domain_keywords=ex.domain_keywords or [],
        summary=ex.summary, starter_code=ex.starter_code, hint=ex.hint,
        reference_solution=ex.reference_solution or "",
        tests=[DraftTest(description=t.description, input=t.input_data, expected=t.expected_output,
                         category=t.category or "happy", hidden=t.is_hidden) for t in tests],
        mutants=[DraftMutant(code=m.code, bug_line=m.bug_line, bug_type=m.bug_type,
                             note_vi=m.note_vi, note_en=m.note_en) for m in mutants],
        skills=ex.skills or [], debug=debug,
    )


def _content(payload: DraftPayload, author_id: int, reviewer_id: int | None = None) -> ExerciseContent:
    author = str(author_id)
    review = {"status": "approved" if reviewer_id else "draft", "author": author,
              "reviewer": str(reviewer_id) if reviewer_id else None}
    raw = {
        "code": payload.code, "reference_solution": payload.reference_solution,
        "tests": [t.model_dump() for t in payload.tests],
        "mutants": [m.model_dump() for m in payload.mutants],
        "limits": payload.limits,
        "exercise": {"summary": payload.summary, "starter_code": payload.starter_code,
                     "hint": payload.hint or None},
        "debug": {**payload.debug, "review": review} if payload.debug else None,
        "skills": {"tags": payload.skills, "review": review} if payload.skills else None,
        "review": review,
    }
    return ExerciseContent.model_validate(raw)


async def _validation_errors(row: ExerciseDraft) -> tuple[ExerciseContent | None, list[str]]:
    payload = DraftPayload.model_validate(row.payload)
    try:
        content = _content(payload, row.author_user_id or 0, row.reviewer_user_id)
    except ValidationError as exc:
        return None, [".".join(str(part) for part in e["loc"]) + ": " + e["msg"] for e in exc.errors()]
    return content, await validate_content(content, payload.kind, payload.starter_code)


async def _advance(db: AsyncSession, row: ExerciseDraft, expected_revision: int,
                   expected_status: str, next_status: str, **values: object) -> None:
    result = await db.execute(update(ExerciseDraft).where(
        ExerciseDraft.id == row.id, ExerciseDraft.revision == expected_revision,
        ExerciseDraft.status == expected_status,
    ).values(status=next_status, revision=expected_revision + 1,
             updated_at=service.now_utc(), **values))
    if result.rowcount != 1:
        await db.rollback()
        raise _conflict()
    await db.refresh(row)


@router.get("")
async def list_exercises(response: Response, _: Principal = Depends(ready_admin), db: AsyncSession = Depends(get_db),
                         q: str = Query("", max_length=100),
                         status: Literal["draft", "review", "approved", "published"] | None = None,
                         level: Literal["fresher", "junior", "senior"] | None = None,
                         kind: Literal["implement", "debug"] | None = None,
                         limit: int = Query(50, ge=1, le=100),
                         offset: int = Query(0, ge=0)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    # Select metadata only; avoid loading solutions, mutants and hidden tests for a list page.
    existing = select(
        Exercise.code.label("code"),
        func.coalesce(ExerciseDraft.payload["title"].as_string(), Exercise.title).label("title"),
        func.coalesce(ExerciseDraft.payload["difficulty"].as_string(), Exercise.difficulty).label("difficulty"),
        func.coalesce(ExerciseDraft.payload["level"].as_string(), Exercise.level).label("level"),
        func.coalesce(ExerciseDraft.payload["kind"].as_string(), Exercise.kind).label("kind"),
        func.coalesce(ExerciseDraft.status, "published").label("status"),
        ExerciseDraft.revision.label("revision"),
        func.coalesce(ExerciseDraft.updated_at, Exercise.created_at).label("updated_at"),
    ).outerjoin(ExerciseDraft, ExerciseDraft.code == Exercise.code)
    unpublished = select(
        ExerciseDraft.code, ExerciseDraft.payload["title"].as_string(),
        ExerciseDraft.payload["difficulty"].as_string(), ExerciseDraft.payload["level"].as_string(),
        ExerciseDraft.payload["kind"].as_string(), ExerciseDraft.status,
        ExerciseDraft.revision, ExerciseDraft.updated_at,
    ).outerjoin(Exercise, Exercise.code == ExerciseDraft.code).where(Exercise.id.is_(None))
    rows = union_all(existing, unpublished).subquery()
    query = select(rows)
    if q.strip():
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.where(rows.c.code.ilike(pattern, escape="\\") |
                            rows.c.title.ilike(pattern, escape="\\"))
    if status:
        query = query.where(rows.c.status == status)
    if level:
        query = query.where(rows.c.level == level)
    if kind:
        query = query.where(rows.c.kind == kind)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    items = (await db.execute(query.order_by(rows.c.code).limit(limit).offset(offset))).mappings().all()
    return {"total": total, "items": [dict(item) for item in items]}


@router.post("/drafts", status_code=201)
async def create_draft(payload: DraftPayload, request: Request,
                       principal: Principal = Depends(ready_admin), db: AsyncSession = Depends(get_db)) -> dict:
    service.require_frontend_origin(request)
    if await _exercise(db, payload.code) or (await db.execute(select(ExerciseDraft.id).where(
            ExerciseDraft.code == payload.code))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Exercise code already exists; open its detail to create a revision")
    row = ExerciseDraft(code=payload.code, payload=payload.model_dump(mode="json"), status="draft",
                        revision=1, author_user_id=principal.user.id)
    db.add(row)
    try:
        await db.flush()
        service.log(db, "exercise_draft_created", principal.user.id, None, "revision 1", payload.code)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Exercise code already exists") from exc
    await db.refresh(row)
    return _public_row(row)


@router.put("/drafts/{code}")
async def save_draft(code: str, data: SaveDraftIn, request: Request,
                     principal: Principal = Depends(ready_admin), db: AsyncSession = Depends(get_db)) -> dict:
    service.require_frontend_origin(request)
    row = await _draft(db, code)
    if row.code != data.payload.code:
        raise HTTPException(status_code=422, detail="Exercise code cannot change")
    if row.status not in ("draft", "published"):
        raise _conflict()
    if row.revision != data.expected_revision:
        raise _conflict()
    changed_fields = [key for key, value in data.payload.model_dump(mode="json").items()
                      if row.payload.get(key) != value]
    if not changed_fields:
        return _public_row(row)
    await _advance(db, row, data.expected_revision, row.status, "draft",
                   payload=data.payload.model_dump(mode="json"), author_user_id=principal.user.id,
                   reviewer_user_id=None)
    service.log(db, "exercise_draft_updated", principal.user.id, None,
                f"revision {row.revision}; fields: {', '.join(changed_fields)}"[:255], row.code)
    await db.commit()
    return _public_row(row)


@router.post("/{code}/draft", status_code=201)
async def start_revision(code: str, request: Request, principal: Principal = Depends(ready_admin),
                         db: AsyncSession = Depends(get_db)) -> dict:
    service.require_frontend_origin(request)
    ex = await _exercise(db, code)
    if ex is None:
        raise HTTPException(status_code=404, detail="Published exercise not found")
    if (await db.execute(select(ExerciseDraft.id).where(ExerciseDraft.code == ex.code))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A draft already exists; open it instead")
    payload = await _snapshot(db, ex)
    row = ExerciseDraft(code=ex.code, payload=payload.model_dump(mode="json"), status="draft",
                        revision=1, author_user_id=principal.user.id)
    db.add(row)
    try:
        await db.flush()
        service.log(db, "exercise_draft_created", principal.user.id, None, "revision 1", ex.code)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A draft already exists") from exc
    await db.refresh(row)
    return _public_row(row)


@router.post("/drafts/{code}/validate")
async def validate_draft(code: str, data: RevisionIn, request: Request,
                         principal: Principal = Depends(ready_admin), db: AsyncSession = Depends(get_db)) -> dict:
    service.require_frontend_origin(request)
    rate_limit.enforce(f"admin-content-validate:{principal.user.id}", 10, 60)
    row = await _draft(db, code)
    if row.revision != data.expected_revision:
        raise _conflict()
    _, errors = await _validation_errors(row)
    return {"code": row.code, "revision": row.revision, "valid": not errors, "errors": errors}


@router.post("/drafts/{code}/submit")
async def submit_draft(code: str, data: RevisionIn, request: Request,
                       principal: Principal = Depends(ready_admin), db: AsyncSession = Depends(get_db)) -> dict:
    service.require_frontend_origin(request)
    rate_limit.enforce(f"admin-content-submit:{principal.user.id}", 10, 60)
    row = await _draft(db, code)
    if row.status != "draft" or row.revision != data.expected_revision:
        raise _conflict()
    _, errors = await _validation_errors(row)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})
    await _advance(db, row, data.expected_revision, "draft", "review")
    service.log(db, "exercise_submitted", principal.user.id, None, f"revision {row.revision}", row.code)
    await db.commit()
    return _public_row(row)


@router.post("/drafts/{code}/approve")
async def approve_draft(code: str, data: RevisionIn, request: Request,
                        principal: Principal = Depends(ready_admin), db: AsyncSession = Depends(get_db)) -> dict:
    service.require_frontend_origin(request)
    row = await _draft(db, code)
    if row.status != "review" or row.revision != data.expected_revision:
        raise _conflict()
    if row.author_user_id is None or row.author_user_id == principal.user.id:
        raise HTTPException(status_code=403, detail="A different admin must approve this draft")
    await _advance(db, row, data.expected_revision, "review", "approved",
                   reviewer_user_id=principal.user.id)
    service.log(db, "exercise_approved", principal.user.id, None, f"revision {row.revision}", row.code)
    await db.commit()
    return _public_row(row)


@router.post("/drafts/{code}/reject")
async def reject_draft(code: str, data: RevisionIn, request: Request,
                       principal: Principal = Depends(ready_admin), db: AsyncSession = Depends(get_db)) -> dict:
    service.require_frontend_origin(request)
    row = await _draft(db, code)
    if row.status != "review" or row.revision != data.expected_revision:
        raise _conflict()
    if row.author_user_id == principal.user.id:
        raise HTTPException(status_code=403, detail="A different admin must review this draft")
    await _advance(db, row, data.expected_revision, "review", "draft", reviewer_user_id=None)
    service.log(db, "exercise_rejected", principal.user.id, None, f"revision {row.revision}", row.code)
    await db.commit()
    return _public_row(row)


@router.post("/drafts/{code}/publish")
async def publish_draft(code: str, data: RevisionIn, request: Request,
                        principal: Principal = Depends(ready_admin), db: AsyncSession = Depends(get_db)) -> dict:
    service.require_frontend_origin(request)
    rate_limit.enforce(f"admin-content-publish:{principal.user.id}", 10, 60)
    row = await _draft(db, code)
    if row.status != "approved" or row.revision != data.expected_revision:
        raise _conflict()
    if row.author_user_id is None or row.reviewer_user_id is None or row.author_user_id == row.reviewer_user_id:
        raise HTTPException(status_code=403, detail="Independent review required")
    reviewer = await db.get(User, row.reviewer_user_id)
    if reviewer is None or not reviewer.is_active or reviewer.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Reviewer account is unavailable")
    content, errors = await _validation_errors(row)
    if errors or content is None:
        raise HTTPException(status_code=422, detail={"errors": errors})
    await _advance(db, row, data.expected_revision, "approved", "published")
    payload = DraftPayload.model_validate(row.payload)
    ex = await _exercise(db, row.code)
    if ex is None:
        ex = Exercise(code=row.code, title=payload.title, difficulty=payload.difficulty,
                      category=payload.category, level=payload.level, kind=payload.kind,
                      language=payload.language, description=payload.description,
                      learning_objective=payload.learning_objective, domain_keywords=payload.domain_keywords,
                      summary=payload.summary, starter_code=payload.starter_code, hint=payload.hint,
                      content_source="admin")
        db.add(ex)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise _conflict() from exc
    ex.title = payload.title
    ex.difficulty = payload.difficulty
    ex.category = payload.category
    ex.level = payload.level
    ex.kind = payload.kind
    ex.language = payload.language
    ex.description = payload.description
    ex.learning_objective = payload.learning_objective
    ex.domain_keywords = payload.domain_keywords
    ex.summary = payload.summary
    ex.starter_code = payload.starter_code
    ex.hint = payload.hint
    ex.skills = payload.skills
    if payload.debug is None:
        ex.debug_meta = None
    ex.content_source = "admin"
    await _write(db, ex, content)
    service.log(db, "exercise_published", principal.user.id, None, f"revision {row.revision}", row.code)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _conflict() from exc
    return _public_row(row)


@router.get("/{code}")
async def get_exercise(code: str, response: Response, _: Principal = Depends(ready_admin),
                       db: AsyncSession = Depends(get_db)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    row = (await db.execute(select(ExerciseDraft).where(ExerciseDraft.code == code.upper()))).scalar_one_or_none()
    if row:
        return _public_row(row)
    ex = await _exercise(db, code)
    if ex is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    payload = await _snapshot(db, ex)
    return {"code": ex.code, "payload": payload.model_dump(mode="json"), "status": "published",
            "revision": None, "author_user_id": None, "reviewer_user_id": None,
            "updated_at": ex.created_at}
