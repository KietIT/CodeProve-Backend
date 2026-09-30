"""Schema of the per-exercise content files in content/exercises/<CODE>.json."""
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from app.features.content.skills import MAX_SKILLS, TAXONOMY

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


class ExerciseOverrides(BaseModel):
    """Replacements for the exercise's own fields, for exercises whose seeded
    statement cannot be tested fairly. Reviewed like the rest of the file."""

    summary: str | None = Field(default=None, min_length=1)
    starter_code: CodeText | None = None
    hint: str | None = Field(default=None, min_length=1)

    def fields_set(self) -> list[str]:
        return [name for name in ("summary", "starter_code", "hint") if getattr(self, name) is not None]


class ContentReview(BaseModel):
    status: Literal["draft", "approved"]
    author: str = Field(min_length=1)
    reviewer: str | None = None

    @property
    def approved(self) -> bool:
        return self.status == "approved" and bool(self.reviewer) and self.reviewer != self.author


class ContentDebug(BaseModel):
    """Where the bug of a debug exercise is and how to explain it (P2.2).

    `regions` (1-based lines of the starter as served, comments stripped)
    overrides the regions derived from the starter/reference diff when that
    diff does not match the bug. It has its own review so adding it does not
    un-approve the rest of the file."""

    regions: list[list[Annotated[int, Field(ge=1)]]] | None = None
    explanation_vi: str = Field(min_length=1, max_length=400)
    explanation_en: str = Field(min_length=1, max_length=400)
    hint_vi: str = Field(min_length=1, max_length=120)
    hint_en: str = Field(min_length=1, max_length=120)
    review: ContentReview


class ContentSkills(BaseModel):
    """The skills an exercise practises (P3.2), keys of skills.TAXONOMY.

    Own review, like the debug block: tagging does not un-approve the file."""

    tags: list[str] = Field(min_length=1, max_length=MAX_SKILLS)
    review: ContentReview

    @field_validator("tags")
    @classmethod
    def _known_and_unique(cls, tags: list[str]) -> list[str]:
        unknown = [t for t in tags if t not in TAXONOMY]
        if unknown:
            raise ValueError(f"unknown skill(s) {unknown}; allowed: {sorted(TAXONOMY)}")
        if len(set(tags)) != len(tags):
            raise ValueError("skills must not repeat")
        return tags


class ExerciseContent(BaseModel):
    code: str = Field(pattern=r"^CP-\d{3}$")
    reference_solution: CodeText
    tests: list[ContentTest] = Field(min_length=1)
    mutants: list[ContentMutant]
    limits: ContentLimits | None = None
    exercise: ExerciseOverrides | None = None
    debug: ContentDebug | None = None
    skills: ContentSkills | None = None
    review: ContentReview

    def starter_for(self, current_starter: str) -> str:
        """The starter the exercise will have once this file is synced."""
        if self.exercise and self.exercise.starter_code is not None:
            return self.exercise.starter_code
        return current_starter

    @property
    def is_approved(self) -> bool:
        """Workflow marker, NOT an authorization control.

        Anyone who can push can write these strings, and `main` does not
        require an approving review, so review is a team convention. The
        enforced gate is the operator: only people with EC2 access can run
        the sync, and its dry run prints each file's reviewer to check before
        --apply. This check just stops drafts from being synced by accident.
        Content code runs in the same hardened sandbox as student code.
        """
        return self.review.approved


def load_content_file(path: Path) -> ExerciseContent:
    content = ExerciseContent.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if path.stem != content.code:
        raise ValueError(f"{path.name}: file name must match its code {content.code}")
    return content
