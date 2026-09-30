"""P3.2: skill tags in content files, validated, synced and exposed."""
import json

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.features.content.schema import CONTENT_DIR, ContentSkills, load_content_file
from app.features.content.skills import MAX_SKILLS, TAXONOMY
from app.features.content.sync import sync_content
from tests.test_content_sync import APPROVED, _exercise
from tests.test_content_validate import DEBUG, _content

DRAFT = {"status": "draft", "author": "claude", "reviewer": None}


def test_every_label_exists_in_both_languages():
    assert all(set(labels) == {"vi", "en"} and all(labels.values()) for labels in TAXONOMY.values())


@pytest.mark.parametrize("path", sorted(CONTENT_DIR.glob("CP-*.json")), ids=lambda p: p.stem)
def test_every_exercise_has_1_to_3_known_skills(path):
    skills = load_content_file(path).skills
    assert skills is not None and 1 <= len(skills.tags) <= MAX_SKILLS


@pytest.mark.parametrize("tags", [[], ["no-such-skill"], ["hash-map", "hash-map"],
                                  ["hash-map", "graph", "recursion", "caching"]])
def test_empty_unknown_repeated_or_too_many_skills_are_rejected(tags):
    with pytest.raises(ValidationError):
        ContentSkills.model_validate({"tags": tags, "review": DRAFT})


def _write(tmp_path, skills_review):
    raw = json.loads(_content(review=APPROVED, debug=DEBUG,
                              skills={"tags": ["control-flow"], "review": skills_review}).model_dump_json())
    p = tmp_path / "CP-004.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    return p


@pytest.mark.asyncio
async def test_draft_skills_are_not_written_and_approved_ones_are(db_session, tmp_path):
    from app.models import Exercise

    await _exercise(db_session)
    draft = await sync_content(db_session, [_write(tmp_path, DRAFT)], apply=True)
    assert draft[0]["skills"] == "draft" and draft[0]["skill_tags"] == ["control-flow"]
    ex = (await db_session.execute(select(Exercise))).scalar_one()
    assert ex.skills == []

    approved = await sync_content(db_session, [_write(tmp_path, APPROVED)], apply=True)
    assert approved[0]["skills"] == "approved" and approved[0]["skills_reviewer"] == "an"
    await db_session.refresh(ex)
    assert ex.skills == ["control-flow"]

    await sync_content(db_session, [_write(tmp_path, DRAFT)], apply=True)  # a later draft keeps them
    await db_session.refresh(ex)
    assert ex.skills == ["control-flow"]


@pytest.mark.asyncio
async def test_exercise_api_lists_skills_with_labels(client, db_session, auth_headers):
    from app.models import Exercise

    db_session.add(Exercise(code="CP-001", title="t", difficulty="Easy", category="c", level="fresher",
                            language="python", summary="s", starter_code="def f(): pass", hint="h",
                            domain_keywords=[], skills=["hash-map", "retired-skill"]))
    await db_session.commit()
    expected = [{"key": "hash-map", **TAXONOMY["hash-map"]}]  # unknown keys are dropped
    detail = (await client.get("/api/exercises/CP-001", headers=auth_headers)).json()
    assert detail["skills"] == expected
    groups = (await client.get("/api/exercises", headers=auth_headers)).json()
    assert groups[0]["exercises"][0]["skills"] == expected
