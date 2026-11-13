"""The price list. Prices live here, never in the request: the client only names a plan code."""
from dataclasses import dataclass

FREE = "free"


@dataclass(frozen=True)
class Plan:
    code: str
    tier: str  # plus | pro
    period: str  # monthly | yearly
    amount: int  # VND
    days: int


PLANS: dict[str, Plan] = {
    p.code: p
    for p in (
        Plan("plus_monthly", "plus", "monthly", 49_000, 30),
        Plan("plus_yearly", "plus", "yearly", 490_000, 365),
        Plan("pro_monthly", "pro", "monthly", 99_000, 30),
        Plan("pro_yearly", "pro", "yearly", 990_000, 365),
    )
}
