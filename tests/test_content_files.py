"""Every file in content/exercises must parse and pass the sandbox validator.

Run before opening a content PR: pytest tests/test_content_files.py -q
"""
import pytest

from app.features.content.schema import CONTENT_DIR, load_content_file
from app.features.content.validate import validate_content
from app.seed.exercises_seed import EXERCISES

SEED = {e["code"]: e for e in EXERCISES}
FILES = sorted(CONTENT_DIR.glob("*.json"))


@pytest.mark.asyncio
@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
async def test_content_file_is_valid(path):
    content = load_content_file(path)
    assert content.code in SEED, f"{content.code} is not a known exercise"
    seed = SEED[content.code]
    starter = content.starter_for(seed["starter_code"])
    errors = await validate_content(content, seed.get("kind", "implement"), starter)
    assert errors == [], "\n".join(errors)
