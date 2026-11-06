"""Immutable, hash-chained decision ledger (see docs/05-decision-record-audit-spec.md).

Pilot storage: append-only JSONL per run. Production: append-only Postgres table + WORM object storage.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def _hash(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev = GENESIS
        if self.path.exists():
            lines = self.path.read_text().strip().splitlines()
            if lines:
                self._prev = json.loads(lines[-1])["record_hash"]

    def record(self, *, dr_type: str, run_id: str, step: str, actor: dict, summary: str,
               inputs: list | None = None, output: dict | None = None, rationale: str = "",
               alternatives: list | None = None, constraints_checked: list | None = None,
               dissent: list | None = None, approvals: list | None = None,
               portfolio_scope: list | None = None, policy_version: str = "", data_flags: dict | None = None) -> str:
        body = {
            "dr_id": "dr_" + uuid.uuid4().hex[:20], "dr_type": dr_type, "run_id": run_id, "step": step,
            "actor": actor, "portfolio_scope": portfolio_scope or [], "inputs": inputs or [],
            "policy_version": policy_version, "output": output or {}, "summary": summary,
            "rationale": rationale, "alternatives_considered": alternatives or [],
            "constraints_checked": constraints_checked or [], "dissent": dissent or [],
            "approvals": approvals or [], "data_flags": data_flags or {},
            "created_at": datetime.now(timezone.utc).isoformat(), "prev_hash": self._prev,
        }
        body["record_hash"] = _hash(body)
        with self.path.open("a") as f:
            f.write(json.dumps(body, default=str) + "\n")
        self._prev = body["record_hash"]
        return body["dr_id"]

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text().splitlines() if x.strip()]


def verify(path: Path) -> tuple[bool, str]:
    prev = GENESIS
    recs = Ledger(path).records()
    for i, rec in enumerate(recs):
        h = rec.pop("record_hash")
        if rec["prev_hash"] != prev:
            return False, f"chain broken at record {i} ({rec['dr_id']})"
        if _hash(rec) != h:
            return False, f"record {i} ({rec['dr_id']}) content altered"
        prev = h
    return True, f"verified {len(recs)} records; head {prev[:12]}"
