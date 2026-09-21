from pydantic import BaseModel


class TraceIn(BaseModel):
    source_code: str
    # When set, the backend traces the code against this exercise's first
    # visible test-case input. `call` overrides it with an explicit invocation.
    exercise_code: str | None = None
    call: str | None = None
