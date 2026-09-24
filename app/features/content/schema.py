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
        """Workflow marker, NOT an authorization control.

        Anyone who can push can write these strings, and `main` does not
        require an approving review, so review is a team convention. The
        enforced gate is the operator: only people with EC2 access can run
        the sync, and its dry run prints each file's reviewer to check before
        --apply. This check just stops drafts from being synced by accident.
        Content code runs in the same hardened sandbox as student code.
        """
        r = self.review
        return r.status == "approved" and bool(r.reviewer) and r.reviewer != r.author


def load_content_file(path: Path) -> ExerciseContent:
    content = ExerciseContent.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if path.stem != content.code:
        raise ValueError(f"{path.name}: file name must match its code {content.code}")
    return content
