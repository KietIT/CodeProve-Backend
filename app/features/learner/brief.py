"""The learner brief (P3.3): a short, deterministic summary of a LearnerProfile.

Meant for Ciel's context (P3.5) and the progress page, so it stays small and
never contains code, chat text, names or emails, only ratings, levels and the
team-reviewed `practice` phrases of the feedback templates.
"""
from app.features.feedback.templates import TEMPLATES
from app.features.learner.profile import LearnerProfile, SkillRating

MIN_SKILL_ATTEMPTS = 2  # approved: a skill is named strong/weak only after 2 scored attempts
MAX_NAMED_SKILLS = 2
MAX_ISSUES = 3
GOOD, WEAK = 1050.0, 950.0  # rating words around the 1000 start

AXIS_NAMES = {
    "vi": {"understanding": "Thấu hiểu", "hypothesis": "Giả thuyết", "prompting": "Prompting",
           "verification": "Kiểm chứng", "testing": "Testing", "debugging": "Debug"},
    "en": {"understanding": "Understanding", "hypothesis": "Hypothesis", "prompting": "Prompting",
           "verification": "Verification", "testing": "Testing", "debugging": "Debugging"},
}
TEXT = {
    "vi": {
        "empty": "Chưa có bài nào được chấm.",
        "count": "Học viên đã có {n} bài được chấm.",
        "too_little": "Chưa đủ dữ liệu để đánh giá kỹ năng (cần ít nhất {m} bài cho mỗi kỹ năng).",
        "strong": "Kỹ năng mạnh: {skills}.",
        "weak": "Kỹ năng cần luyện: {skills}.",
        "axes": "Trong {w} bài gần nhất, trục mạnh nhất là {best} ({best_level}/3), yếu nhất là {worst} ({worst_level}/3).",
        "issues": "Nên luyện thêm (lặp lại trong {w} bài gần nhất): {issues}.",
        "issue": "{practice} ({n}/{w} bài)",
        "words": ("tốt", "trung bình", "cần luyện"),
    },
    "en": {
        "empty": "No scored exercise yet.",
        "count": "The learner has {n} scored exercise(s).",
        "too_little": "Not enough data to rate skills yet (at least {m} exercises per skill).",
        "strong": "Strongest skills: {skills}.",
        "weak": "Skills to practise: {skills}.",
        "axes": "Over the last {w} exercise(s), the strongest axis is {best} ({best_level}/3), the weakest {worst} ({worst_level}/3).",
        "issues": "To practise (recurring over the last {w} exercise(s)): {issues}.",
        "issue": "{practice} ({n}/{w})",
        "words": ("good", "average", "needs practice"),
    },
}


def strong_and_weak(skills: list[SkillRating]) -> tuple[list[SkillRating], list[SkillRating]]:
    """Up to 2 strongest and 2 weakest (weakest first) of the rated skills; never both.
    Shared with the recommendation (P3.4) so both name the same weak skills."""
    rated = sorted((s for s in skills if s.attempts >= MIN_SKILL_ATTEMPTS), key=lambda s: (-s.rating, s.key))
    strong = rated[:MAX_NAMED_SKILLS]
    return strong, [s for s in reversed(rated) if s not in strong][:MAX_NAMED_SKILLS]


def _word(rating: float, locale: str) -> str:
    good, average, weak = TEXT[locale]["words"]
    return good if rating >= GOOD else weak if rating < WEAK else average


def _skills(skills: list[SkillRating], locale: str) -> str:
    return "; ".join(f"{getattr(s, locale)} ({s.rating:.0f}, {_word(s.rating, locale)})" for s in skills)


def learner_brief(p: LearnerProfile, locale: str = "vi") -> str:
    locale = locale if locale in TEXT else "vi"
    t = TEXT[locale]
    if p.scored_attempts == 0:
        return t["empty"]
    lines = [t["count"].format(n=p.scored_attempts)]

    strong, weak = strong_and_weak(p.skills)
    if not strong:
        lines.append(t["too_little"].format(m=MIN_SKILL_ATTEMPTS))
    else:
        lines.append(t["strong"].format(skills=_skills(strong, locale)))
        if weak:
            lines.append(t["weak"].format(skills=_skills(weak, locale)))

    known = {axis: level for axis, level in p.axes.items() if level is not None}
    if len(known) >= 2 and max(known.values()) > min(known.values()):
        best, worst = max(known, key=known.get), min(known, key=known.get)
        names = AXIS_NAMES[locale]
        lines.append(t["axes"].format(w=p.window, best=names[best], best_level=f"{known[best]:.1f}",
                                      worst=names[worst], worst_level=f"{known[worst]:.1f}"))

    issues = [t["issue"].format(practice=TEMPLATES[i.code][locale]["practice"], n=i.count, w=p.window)
              for i in p.recurring if i.code in TEMPLATES][:MAX_ISSUES]
    if issues:
        lines.append(t["issues"].format(w=p.window, issues="; ".join(issues)))
    return "\n".join(lines)
