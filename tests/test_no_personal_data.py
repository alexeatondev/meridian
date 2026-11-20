"""The repository is public: no personal email addresses or AWS identifiers in tracked files (doc 19 G-7).
Personal contacts live in GitHub Actions secrets (COST_GUARD_EMAIL, SEC_USER_AGENT)."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERSONAL = re.compile(r"[A-Za-z0-9._%+-]+@(?:gmail|googlemail|hotmail|outlook|live|yahoo|icloud|aol|proton(?:mail)?)\.(?:com|me)", re.I)
AWS_IDS = re.compile(r"\b\d{12}\b(?=[/:.-]|\s|$)|\bo-[a-z0-9]{10,32}\b|\bus-east-2_[A-Za-z0-9]{9}\b")


def _tracked() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception:  # not a git checkout (e.g. the container image)
        return []
    skip = (".png", ".jpg", ".xlsx", ".parquet", ".pdf")
    return [ROOT / f for f in out.splitlines() if not f.endswith(skip) and not f.startswith("data/cache/")]


def test_no_personal_email_addresses():
    hits = [f"{p.relative_to(ROOT)}:{m.group(0)[:3]}…" for p in _tracked() if p.is_file()
            for m in PERSONAL.finditer(p.read_text(errors="ignore"))]
    assert not hits, f"personal email addresses in the public repository: {hits}"


def test_no_aws_account_or_pool_ids():
    hits = []
    for p in _tracked():
        if p.is_file() and p.suffix in (".md", ".py", ".yaml", ".yml", ".json", ".toml"):
            for m in AWS_IDS.finditer(p.read_text(errors="ignore")):
                hits.append(f"{p.relative_to(ROOT)}:{m.group(0)[:4]}…")
    assert not hits, f"AWS identifiers in the public repository: {hits}"
