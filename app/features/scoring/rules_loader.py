from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

_RULES_DIR = Path(__file__).resolve().parent.parent.parent / "rules"


@dataclass
class Rule:
    id: str
    axis: str
    thresholds: dict = field(default_factory=dict)
    effect: dict = field(default_factory=dict)
    severity: str = "low"


@lru_cache
def load_rules() -> dict[str, list[Rule]]:
    out: dict[str, list[Rule]] = {}
    for path in sorted(_RULES_DIR.glob("*.yaml")):
        items = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        for item in items:
            rule = Rule(
                id=item["id"],
                axis=item["axis"],
                thresholds=item.get("thresholds", {}),
                effect=item.get("effect", {}),
                severity=item.get("severity", "low"),
            )
            out.setdefault(rule.axis, []).append(rule)
    return out


def get_rule(rules: list[Rule], rule_id: str) -> Rule:
    for r in rules:
        if r.id == rule_id:
            return r
    raise KeyError(rule_id)
