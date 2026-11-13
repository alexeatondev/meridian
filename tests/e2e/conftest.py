"""Browser tests of the Meridian Console, one file per role (docs: UAT scripts).

The app runs locally on a free port with development sign-in (no Cognito), a throw-away SQLite
database and one offline pipeline run published through the real ingest API. Nothing touches AWS.

Run:  pip install -e ".[dev,app,e2e]" && python -m playwright install chromium
      MERIDIAN_OFFLINE=1 pytest tests/e2e            (add --headed to watch, --slowmo 300 to slow down)
"""
from __future__ import annotations

import io
import os
import socket
import tarfile
import threading
import time

import pytest


INGEST_TOKEN = "e2e-ingest-token"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _bundle(run_dir) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for f in ("results.json", "ledger.jsonl", "board_memo.md", "compliance_report.md"):
            tf.add(run_dir / f, arcname=f"{run_dir.name}/{f}")
    return buf.getvalue()


@pytest.fixture(scope="session")
def app_url(tmp_path_factory):
    """Start the hosted app locally and publish one pipeline run into it."""
    import httpx
    import uvicorn

    tmp = tmp_path_factory.mktemp("e2e")
    os.environ.update({"MERIDIAN_AUTH": "dev", "MERIDIAN_DB_URL": f"sqlite:///{tmp}/app.db",
                       "INGEST_TOKEN": INGEST_TOKEN, "SESSION_SECRET": "e2e-session-secret",
                       "MERIDIAN_LLM": "off"})
    from meridian.pipelines.target_date import run
    prev_dir = run(as_of="2026-09-30", out_root=tmp / "runs-prev").out_dir     # for "Changes since last run"
    run_dir = run(out_root=tmp / "runs").out_dir

    import meridian.app.main as m
    m._store = None
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(m.app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(base + "/healthz", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    for d in (prev_dir, run_dir):
        r = httpx.post(base + "/api/ingest", headers={"Authorization": f"Bearer {INGEST_TOKEN}"},
                       files={"bundle": ("run.tgz", _bundle(d))}, timeout=60)
        assert r.status_code == 200, r.text
    yield base
    server.should_exit = True
    t.join(timeout=5)


@pytest.fixture()
def sign_in(page, app_url):
    """sign_in("Name", "role", ...) signs in through the dev sign-in page and opens the latest run."""
    def _go(name: str, *roles: str):
        page.context.clear_cookies()
        page.goto(app_url + "/login")
        page.fill("input[name=name]", name)
        for r in roles:
            page.check(f"input[name=roles][value={r}]")
        page.click("button[type=submit]")
        page.wait_for_selector("#nav button")
        return page
    return _go


def open_tab(page, label: str):
    page.click(f"#nav button:text-is('{label}')")
    page.wait_for_selector(f"#nav button.active:text-is('{label}')")


def switch_workspace(page, console_role: str):
    page.select_option("#role", console_role)
    page.wait_for_selector("#nav button")


def tabs(page) -> list[str]:
    return [b.inner_text() for b in page.query_selector_all("#nav button")]


def toast_text(page, timeout: int = 5000) -> str:
    page.wait_for_selector("#mtoasts .mtoast", state="visible", timeout=timeout)
    return page.inner_text("#mtoasts .mtoast:last-child")


# ---- Trading → New trade builder (task tiles → setup → impact → draft) ----
def trading_tab(page, label: str):
    page.click(f".tabs button:text-is('{label}')")
    page.wait_for_selector(f".tabs button.active:text-is('{label}')")


def trade_setup(page, task: str, strat: str | None = None, fund: str | None = None):
    """Open New trade, pick a task tile, optionally a strategy (invest/rebalance) or a fund (security/exit)."""
    trading_tab(page, "New trade")
    page.click(f"[data-task='{task}']")
    if strat:
        page.click(f"label.tile:has(input[name=ntStrat][value='{strat}'])")
        page.wait_for_selector(f"input[name=ntStrat][value='{strat}']:checked")
    if fund:
        page.select_option("#ntFund", fund)
        page.wait_for_selector("#ntQ" if task == "security" else "#ntPrev")


def trade_preview(page):
    """Click 'See the impact' and wait for the now-vs-after panel."""
    page.click("#ntPrev")
    page.wait_for_selector("#ntCreate")


def trade_create(page, reason: str):
    """Fill the reason and create the draft; lands on Trade lists with the new list open."""
    page.fill("#ntReason", reason)
    page.click("#ntCreate")
    page.wait_for_selector(".tabs button.active:text-is('Trade lists')")
    page.wait_for_selector("#tlDetail h2")
