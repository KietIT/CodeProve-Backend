import io
import tokenize


def strip_python_comments(code: str) -> str:
    """Remove `#` comments from Python source without changing its line count.

    `buggy_line` is a 1-indexed line number into the code, so every line is
    kept: a trailing comment is cut off, and a comment-only line becomes an
    empty line. Uses `tokenize` so a `#` inside a string literal (including
    triple-quoted strings) is not mistaken for a comment.

    Raises ValueError if the code cannot be tokenized.
    """
    # readlines() splits exactly the way tokenize's readline does, so token
    # rows map 1:1 onto these physical lines.
    lines = io.StringIO(code).readlines()
    try:
        comments = [
            tok.start
            for tok in tokenize.generate_tokens(io.StringIO(code).readline)
            if tok.type == tokenize.COMMENT
        ]
    except (tokenize.TokenError, IndentationError) as exc:
        raise ValueError(f"Code could not be tokenized: {exc}") from exc

    for row, col in comments:
        line = lines[row - 1]
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        lines[row - 1] = body[:col].rstrip() + ending
    return "".join(lines)
