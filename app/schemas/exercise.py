from pydantic import BaseModel

RUBRIC: list[list[str]] = [
    ["Understanding", "25%"], ["Hypothesis", "22%"], ["Prompting", "18%"],
    ["Verification", "15%"], ["Testing", "10%"], ["Debugging", "10%"],
]


class ExerciseSummary(BaseModel):
    id: int
    code: str
    title: str
    difficulty: str
    acceptance: float
    topics: list[str]
    level: str


class ExerciseDetail(ExerciseSummary):
    summary: str
    language: str
    starter: str
    hint: str
    tests: list[str]
    rubric: list[list[str]] = RUBRIC


class LevelGroup(BaseModel):
    level: str
    name: str
    exercises: list[ExerciseSummary]
