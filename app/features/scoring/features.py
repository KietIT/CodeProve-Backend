from dataclasses import dataclass, field

from app.features.scoring.text_utils import cluster_near_duplicates

_CONSTRAINT_HINTS = (
    "return", "format", "complexity", "o(", "constraint", "edge", "must", "should",
    "ràng buộc", "định dạng",
)


@dataclass
class AxisFeatures:
    first_prompt_delay_ms: int | None = None
    problem_read_ratio: float = 1.0
    u2_hits: int = 0
    explain_score: float = 0.0
    h1_count: int = 0
    h2_count: int = 0
    hypothesis_count: int = 0
    has_hypothesis_before_code: bool = False
    code_edits: int = 0
    chars_added: int = 0
    p1_hits: int = 0
    p1_ratio: float = 0.0
    p2_clusters: int = 0
    p3_hits: int = 0
    p4_hits: int = 0
    prompt_count: int = 0
    has_v1: bool = False
    has_v1b: bool = False
    v2_count: int = 0
    has_v3: bool = False
    t1_count: int = 0
    best_coverage: float = 0.0
    has_test_run: bool = False
    d1_count: int = 0
    d2_count: int = 0
    paste_flags: int = 0
    focus_lost: int = 0
    tab_hidden: int = 0
    window_blur: int = 0
    fullscreen_exits: int = 0
    copy_count: int = 0
    cut_count: int = 0
    paste_count: int = 0
    integrity_flag_total: int = field(default=0)


def compute_features(events: list[dict], explain_score: float | None) -> AxisFeatures:
    f = AxisFeatures(explain_score=explain_score or 0.0)
    # Work on a timestamp-ordered copy so every "first"/transition derivation is
    # order-robust regardless of append order (pure: the input list is not mutated).
    events = sorted(events, key=lambda e: e["ts"])
    open_ts = next((e["ts"] for e in events if e["type"] == "OPEN"), None)
    first_prompt = next((e for e in events if e["type"] == "PROMPT"), None)
    first_code = next((e for e in events if e["type"] == "CODE_EDIT"), None)

    if open_ts is not None and first_prompt is not None:
        f.first_prompt_delay_ms = first_prompt["ts"] - open_ts
    open_ev = next((e for e in events if e["type"] == "OPEN"), None)
    if open_ev:
        f.problem_read_ratio = float(open_ev["payload"].get("problemReadRatio", 1.0))

    prompts = [e for e in events if e["type"] == "PROMPT"]
    f.prompt_count = len(prompts)
    prompt_texts = [e["payload"].get("messageText", "") for e in prompts]
    for e in prompts:
        ml = int(e["payload"].get("messageLength", 0))
        kw = e["payload"].get("keywordsMatched", []) or []
        if 0 < ml < 30:
            f.p1_hits += 1
        if len(kw) >= 2:
            f.p3_hits += 1
        if not any(h in e["payload"].get("messageText", "").lower() for h in _CONSTRAINT_HINTS):
            f.p4_hits += 1
    f.p1_ratio = (f.p1_hits / f.prompt_count) if f.prompt_count else 0.0
    f.p3_hits = min(f.p3_hits, 4)  # +2 each, capped at +8
    f.p2_clusters = cluster_near_duplicates(prompt_texts, 0.85)

    # U2: AI replies to shallow concept prompts (short message, no matched keywords).
    replies = [e for e in events if e["type"] == "AI_REPLY"]
    f.u2_hits = min(
        sum(
            1
            for p in prompts
            if int(p["payload"].get("messageLength", 0)) < 40 and not (p["payload"].get("keywordsMatched"))
        ),
        4,
    )

    # Real-work signals: how much code the student actually typed. Used to gate
    # scores so an untouched attempt cannot earn credit for "engagement".
    code_edits = [e for e in events if e["type"] == "CODE_EDIT"]
    f.code_edits = len(code_edits)
    f.chars_added = sum(int(e["payload"].get("charsAdded", 0)) for e in code_edits)

    # Hypothesis
    hyps = [e for e in events if e["type"] == "HYPOTHESIS"]
    f.hypothesis_count = len(hyps)
    f.h1_count = sum(1 for e in hyps if e["payload"].get("proposedBy") == "user" and e["payload"].get("correct"))
    f.h2_count = sum(1 for e in hyps if e["payload"].get("proposedBy") == "ai")
    if hyps and first_code:
        f.has_hypothesis_before_code = any(h["ts"] < first_code["ts"] for h in hyps)
    elif hyps and not first_code:
        f.has_hypothesis_before_code = True

    # Verification: trap caught/missed, speed-accept, paste-blind
    submit_ts = next((e["ts"] for e in events if e["type"] == "SUBMIT"), None)
    injected = [e for e in replies if e["payload"].get("injectedError")]
    if injected:
        trap_ts = injected[0]["ts"]
        edited_after = any(
            e["type"] == "CODE_EDIT" and e["ts"] > trap_ts and (submit_ts is None or e["ts"] <= submit_ts)
            for e in events
        )
        f.has_v1 = edited_after
        f.has_v1b = not edited_after
    # V2 speed-accept: an AI reply with >=20 loc followed by the next event within 15s.
    for i, e in enumerate(events):
        if e["type"] == "AI_REPLY":
            loc = sum(c.get("loc", 0) for c in e["payload"].get("aiCode", []))
            if loc >= 20 and i + 1 < len(events) and (events[i + 1]["ts"] - e["ts"]) < 15000:
                f.v2_count += 1
    total_ai_loc = sum(sum(c.get("loc", 0) for c in e["payload"].get("aiCode", [])) for e in replies)
    if total_ai_loc >= 50:
        # paste-blind if no CODE_EDIT follows the last AI reply
        last_reply_ts = max((e["ts"] for e in replies), default=None)
        f.has_v3 = last_reply_ts is not None and not any(
            e["type"] == "CODE_EDIT" and e["ts"] > last_reply_ts for e in events
        )

    # Testing
    test_runs = [e for e in events if e["type"] == "TEST_RUN"]
    f.has_test_run = len(test_runs) > 0
    f.t1_count = min(max((int(e["payload"].get("testCount", 0)) for e in test_runs), default=0), 5)
    f.best_coverage = max((float(e["payload"].get("coverage", 0.0)) for e in test_runs), default=0.0)

    # Debugging: fail -> (edit) -> pass cycles
    runs = [e for e in events if e["type"] in ("RUN", "TEST_RUN")]
    prev_failed = False
    for e in runs:
        passed = bool(e["payload"].get("passed"))
        if prev_failed and passed:
            f.d1_count += 1
        prev_failed = not passed
    f.d1_count = min(f.d1_count, 3)
    # D2 (ai-dependent) is intentionally left 0 for the MVP: cleanly distinguishing an
    # AI-driven fix from a user fix needs richer telemetry than is collected today.

    # Integrity raw signals. A PASTE_BLOCKED event means the student *tried* to
    # paste (e.g. an answer copied from another AI) and the editor prevented it -
    # that intent is as strong a signal as a burst paste, so it counts the same.
    # FOCUS_LOST is kept for legacy sessions; new sessions emit specific
    # tab/window/fullscreen events.
    f.paste_flags = sum(
        1
        for e in events
        if e["type"] == "BURST_PASTE"
        or "BURST_PASTE" in e.get("integrity_flags", [])
        or "PASTE_BLOCKED" in e.get("integrity_flags", [])
    )
    f.focus_lost = sum(1 for e in events if e["type"] == "FOCUS_LOST")
    f.tab_hidden = sum(1 for e in events if e["type"] == "TAB_HIDDEN")
    f.window_blur = sum(1 for e in events if e["type"] == "WINDOW_BLUR")
    f.fullscreen_exits = sum(1 for e in events if e["type"] == "FULLSCREEN_EXIT")
    f.copy_count = sum(1 for e in events if e["type"] == "COPY")
    f.cut_count = sum(1 for e in events if e["type"] == "CUT")
    f.paste_count = sum(1 for e in events if e["type"] == "PASTE")
    f.integrity_flag_total = (
        f.paste_flags
        + f.focus_lost
        + f.tab_hidden
        + f.window_blur
        + f.fullscreen_exits
    )
    return f
