"""Entity profiles: select one or more operating-entity types and derive the effective regime.

The effective regime drives which compliance rules are on, record retention, required human
roles, approval chains and required reports. Changing the selection re-configures the system
without code changes.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import REPO_ROOT

REGIMES_PATH = REPO_ROOT / "regimes" / "regimes.yaml"
PROFILE_PATH = REPO_ROOT / "config" / "entity_profile.yaml"


@dataclass
class EffectiveRegime:
    selected: list[str]
    firm_name: str
    retention_years: int
    obligations: list[dict]
    rule_patterns: list[str]
    reports: list[str]
    required_roles: list[str]
    human_roles: dict[str, str | dict | None]   # name, or {name, placeholder: true} for a fictional stand-in
    approval_overrides: dict[str, list[str]] = field(default_factory=dict)
    operating_mode: str = "shadow"
    autonomy_level: str = "L3"

    def rule_enabled(self, rule_id: str, applies_to: list[str] | str | None = None) -> bool:
        if applies_to not in (None, "any"):
            if not set(applies_to) & set(self.selected):
                return False
            return True  # explicitly scoped rules are on when their regime is selected
        return any(fnmatch.fnmatch(rule_id, p) for p in self.rule_patterns)

    def role_holder(self, role: str) -> tuple[str | None, bool]:
        """(name, is_placeholder). A placeholder is a fictional stand-in used for testing; it never fills the role."""
        v = self.human_roles.get(role)
        if isinstance(v, dict):
            return v.get("name"), bool(v.get("placeholder"))
        return v, False

    def holder_label(self, role: str) -> str:
        name, ph = self.role_holder(role)
        return "— unfilled —" if not name else (f"{name} (fictional placeholder — role still unfilled)" if ph else name)

    @property
    def unfilled_roles(self) -> list[str]:
        return [r for r in self.required_roles if not self.role_holder(r)[0] or self.role_holder(r)[1]]

    @property
    def production_blockers(self) -> list[str]:
        out = [f"Required human role unfilled: {r}" + (f" (placeholder: {self.role_holder(r)[0]})" if self.role_holder(r)[1] else "")
               for r in self.unfilled_roles]
        out += ["Regime pack needs counsel/CCO review: " + s for s in self.selected]
        return out


def load_packs(path: Path = REGIMES_PATH) -> dict:
    return yaml.safe_load(path.read_text())["packs"]


def load_profile(path: Path = PROFILE_PATH) -> dict:
    return yaml.safe_load(path.read_text())


def resolve(selected: list[str] | None = None, profile: dict | None = None,
            packs: dict | None = None) -> EffectiveRegime:
    packs = packs or load_packs()
    profile = profile or load_profile()
    selected = selected or profile["selected_entities"]
    unknown = [s for s in selected if s not in packs]
    if unknown:
        raise ValueError(f"Unknown entity type(s): {unknown}. Choose from {sorted(packs)}")

    obligations, seen, rules, reports, roles = [], set(), [], [], []
    approval: dict[str, list[str]] = {}
    retention = 0
    for s in selected:
        p = packs[s]
        retention = max(retention, int(p.get("retention_years", 0)))
        for o in p.get("obligations", []):
            if o["id"] not in seen:
                seen.add(o["id"])
                obligations.append({**o, "regime": s})
        rules += [r for r in p.get("rules", []) if r not in rules]
        reports += [r for r in p.get("reports", []) if r not in reports]
        roles += [r for r in p.get("required_human_roles", []) if r not in roles]
        for k, v in (p.get("approval_overrides") or {}).items():
            approval[k] = sorted(set(approval.get(k, [])) | set(v))
    return EffectiveRegime(
        selected=list(selected), firm_name=profile.get("firm_name", ""), retention_years=retention,
        obligations=obligations, rule_patterns=rules, reports=reports, required_roles=roles,
        human_roles=profile.get("human_roles", {}) or {}, approval_overrides=approval,
        operating_mode=profile.get("operating_mode", "shadow"),
        autonomy_level=profile.get("autonomy_level", "L3"),
    )


def save_selection(selected: list[str], path: Path = PROFILE_PATH) -> None:
    load_packs()  # validates file exists
    resolve(selected)  # validates names
    prof = load_profile(path)
    prof["selected_entities"] = list(selected)
    path.write_text(yaml.safe_dump(prof, sort_keys=False))
