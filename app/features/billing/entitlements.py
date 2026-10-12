"""What each tier may do. Every gate in the backend asks here, so the pricing page and the code agree.

Numbers come from settings (CIEL_PER_DAY*, FREE_SUBMITS_PER_MONTH), so they can be tuned without a deploy of code.
"""
from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class Entitlements:
    tier: str
    ciel_per_day: int
    # Submitted attempts per calendar month; None = unlimited.
    monthly_submits: int | None
    # Flags for features whose gating is not wired yet (see docs/superpowers/plans/2026-10-09-payments.md).
    detailed_analysis: bool  # per-axis analysis beyond the basic radar
    learning_path: bool  # personalised learning path (learner recommendations)


def for_tier(tier: str, settings: Settings | None = None) -> Entitlements:
    s = settings or get_settings()
    if tier == "pro":
        return Entitlements("pro", s.ciel_per_day_pro, None, detailed_analysis=True, learning_path=True)
    if tier == "plus":
        return Entitlements("plus", s.ciel_per_day_plus, None, detailed_analysis=True, learning_path=False)
    return Entitlements("free", s.ciel_per_day, s.free_submits_per_month, detailed_analysis=False,
                        learning_path=False)
