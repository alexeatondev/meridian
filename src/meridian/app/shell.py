"""Shared application shell for every Meridian page (UX, 2026-11-11).

- One app bar on every page: product, primary navigation filtered by role, My work inbox, Help, user menu.
- Shared feedback: typed toasts (errors stay until dismissed), in-page dialogs instead of browser prompts,
  busy state on the button that started a request, session-expired dialog, reason-length counters.
- Accessibility: skip link, visible focus, keyboard navigation for tab bars, live regions.
- My work: one inbox across modules (trade lists, glide-path requests, obligations, exceptions).
- Help: the user guide (doc 06) served in the app, with links from each page to its section.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select

from .. import REPO_ROOT
from . import auth

router = APIRouter()

PAGES = [  # key, label, href, roles that see it
    ("console", "Console", "/runs/latest", None),
    ("trading", "Trading", "/trading", ("portfolio_manager", "analyst", "risk", "compliance", "audit", "admin", "leadership")),
    ("policy", "Policy", "/policy", ("portfolio_manager", "risk", "analyst", "manager_selection", "leadership", "compliance", "audit", "admin")),
    ("regulations", "Regulations", "/regulations", ("compliance", "audit", "admin", "leadership", "portfolio_manager", "risk", "analyst")),
    ("admin", "User access", "/admin", ("admin", "audit", "compliance")),
]
HELP_SECTION = {"console": "1", "trading": "10", "regulations": "12", "admin": "11", "policy": "13"}  # user guide (doc 06) section numbers
PERMISSION_LABELS = {"investment_committee": "Investment Committee", "chief_compliance_officer": "CCO",
                     "route_manager": "Route manager", "approver": "Approver"}


def nav_for(user: dict, current: str) -> dict:
    roles = set(user.get("roles", []))
    links = [{"key": k, "label": lab, "href": href} for k, lab, href, need in PAGES
             if need is None or roles & set(need)]
    return {"user": {"name": user.get("name", ""), "email": user.get("email", ""),
                     "roles": sorted(r for r in roles if r not in PERMISSION_LABELS),
                     "permissions": [PERMISSION_LABELS[r] for r in sorted(roles) if r in PERMISSION_LABELS]},
            "current": current, "links": links, "help": "/help#" + help_anchor(current), "brand": brand_info()}


def brand_info() -> dict:
    from .. import branding
    t = branding.active()
    return {"key": t["key"], "product": t.get("product") or "Meridian", "company": t.get("company") or "",
            "logo": "/brand/logo" if branding.logo_path(t) else ""}


def help_anchor(page: str) -> str:
    """The heading id of the guide section for a page (ids come from the headings, so look them up)."""
    num = HELP_SECTION.get(page)
    try:
        ids = re.findall(r'<h2 id="([^"]+)"', _guide_html())
    except Exception:  # guide not packaged
        return "contents"
    return next((i for i in ids if num and i.startswith(num + "-")), "contents")


@lru_cache(maxsize=1)
def _assets() -> str:
    from .. import hierarchy
    tree = json.dumps(dict(hierarchy.load(), market=hierarchy.market())).replace("</", "<\\/")
    from .. import glossary
    info = json.dumps(glossary.load()).replace("</", "<\\/")
    return ((files("meridian.app") / "shell.html").read_text()
            + f"<script>window.MHIER_CFG={tree};</script><script>{(files('meridian.app') / 'hier.js').read_text()}</script>"
            + f"<script>window.MINFO={info};</script><script>{(files('meridian.app') / 'info.js').read_text()}</script>")


def wrap(html: str, user: dict, current: str) -> str:
    """Insert the shared shell into a page: assets before </head>, the nav data right after <body…>."""
    from .. import branding
    data = json.dumps(nav_for(user, current)).replace("</", "<\\/")
    brand = "" if 'id="meridian-brand"' in html else branding.theme_css()
    html = html.replace("</head>", _assets() + brand + "</head>", 1)
    return re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + f'<script>window.MERIDIAN_NAV={data};</script>', html, count=1)


@router.get("/brand/logo")
def brand_logo():
    """The active theme's logo file (config/brand/<file>), if the company supplied one."""
    from fastapi import HTTPException
    from .. import branding
    p = branding.logo_path()
    if not p:
        raise HTTPException(404, "No logo configured")
    return FileResponse(p, headers={"Cache-Control": "public, max-age=3600"})


# ---------------------------------------------------------------------------------------------- My work
def _item(kind, title, detail, link, *, due="", severity="info", go=None):
    return {"kind": kind, "title": title, "detail": detail, "link": link, "due": due, "severity": severity,
            "go": go or {}}


@router.get("/api/my-work")
def my_work(request: Request):
    """Everything waiting for the signed-in person, across modules, most urgent first."""
    user = auth.require_user(request)
    roles = set(user["roles"])
    me = user.get("name", "")
    today = date.today().isoformat()
    soon = (date.today() + timedelta(days=14)).isoformat()
    items = []
    from . import oversight, regulations, trading
    with trading._store().Session() as s:
        if roles & {"portfolio_manager", "analyst"}:
            for t in s.execute(select(trading.TradeList).where(trading.TradeList.status.in_(("draft", "exported")))).scalars():
                b = t.body
                if b["status"] == "draft" and "portfolio_manager" in roles and auth.APPROVER in roles:
                    items.append(_item("Trade list", f"Approve {b['id']}", f"{b['strategy_name']} · {b['order_count']} orders"
                                       + (" · blocked" if b["blocked_funds"] else ""), "/trading",
                                       severity="warn" if b["blocked_funds"] else "info",
                                       go={"tr_tab": "trades", "tr_tl": b["id"]}))
                elif b["status"] == "exported":
                    items.append(_item("Trade list", f"Record fills for {b['id']}", "Exported for Charles River, not fully filled",
                                       "/trading", go={"tr_tab": "trades", "tr_tl": b["id"]}))
        gs = s.get(trading.TradingSetting, "glidepath")
        if gs and "investment_committee" in roles:
            for r in gs.body.get("requests", []):
                if r.get("status") == "pending" and (r.get("requested_by") or {}).get("name") != me:
                    items.append(_item("Glide path", f"Committee decision on {r['id']}",
                                       f"{r.get('scope_label', '')} · requested by {(r.get('requested_by') or {}).get('name', '')}",
                                       "/trading", severity="warn", go={"tr_tab": "bulk"}))
    from . import policy_admin as PA
    if roles & {PA.IC, PA.CCO}:
        with PA._store().Session() as s:
            for v in s.execute(select(PA.IpsVersion).where(PA.IpsVersion.status == "pending")).scalars():
                b = v.body
                need = [x for x, perm in (("ic", PA.IC), ("cco", PA.CCO)) if perm in roles
                        and not any(a["as"] == x for a in b["approvals"])]
                if need and not PA._same(b["drafted_by"], user) and not any(PA._same(a["by"], user) for a in b["approvals"]):
                    items.append(_item("IPS", f"Approve IPS version {v.version}", f"{b['summary'][:80]} · drafted by {b['drafted_by']['name']}",
                                       "/policy", severity="warn", go={"po_tab": "ips", "po_ver": str(v.version)}))
            if PA.IC in roles:
                for r in PA._gp_state(s)["requests"]:
                    if r["status"] == "pending" and not PA._same(r["requested_by"], user):
                        items.append(_item("Glide path", f"Committee decision on {r['id']}", f"{r['label']} · requested by {r['requested_by']['name']}",
                                           "/policy", severity="warn", go={"po_tab": "paths"}))
    if roles & {"compliance", "risk", "leadership", "portfolio_manager"}:
        with regulations._store().Session() as s:
            for t in s.execute(select(regulations.ComplianceTask).where(
                    regulations.ComplianceTask.status.in_(("open", "in_progress")))).scalars():
                b = t.body
                owner = (b.get("owner") or "").lower()
                mine = owner in {me.lower(), (user.get("email") or "").lower()} if owner else \
                    (b["owner_role"] in roles or "compliance" in roles)
                if mine and b["due"] <= soon:
                    sev = "crit" if b["due"] < today else "warn" if b["due"] <= (date.today() + timedelta(days=3)).isoformat() else "info"
                    items.append(_item("Obligation", b["title"], f"{b['fund_id']} · {b['regulation']} · {b.get('period', '')}",
                                       "/regulations", due=b["due"], severity=sev, go={"rg_tab": "tasks", "rg_task": b["id"]}))
    if roles & {"compliance", "risk", "audit", "leadership", "portfolio_manager"}:
        for c in oversight.list_cases():
            if c["status"] not in ("open", "in_progress"):
                continue
            owner = (c.get("owner") or "").lower()
            od = bool(c.get("due")) and c["due"] < today
            if (owner and owner in {me.lower(), (user.get("email") or "").lower()}) or ("compliance" in roles and od):
                items.append(_item("Exception", c["title"], f"{c['id']} · {c['status']}", "/runs/latest",
                                   due=c.get("due") or "", severity="crit" if od else "warn",
                                   go={"mer_tab": "exceptions", "mer_exc": c["id"]}))
    order = {"crit": 0, "warn": 1, "info": 2}
    items.sort(key=lambda x: (order[x["severity"]], x["due"] or "9999"))
    return {"items": items[:50], "count": len(items)}


# ---------------------------------------------------------------------------------------------- Help
def _guide_path() -> Path:
    return REPO_ROOT / "docs" / "06-user-guides.md"


@lru_cache(maxsize=1)
def _guide_html() -> str:
    import markdown
    src = _guide_path().read_text()
    src = re.sub(r"^\*Image: `[^`]+`\*\n", "", src, flags=re.M)
    src = re.sub(r"Illustrated copy with every screenshot: \S+ \(this Project copy carries the image names in place of the pictures\)\.", "", src)
    src = src.replace("Image files are in the repository under `docs/img/guide/`.", "")
    body = markdown.markdown(src, extensions=["tables", "toc", "sane_lists"])
    body = body.replace('src="img/guide/', 'loading="lazy" src="/help/img/')
    toc = re.findall(r'<h([23]) id="([^"]+)">(.*?)</h[23]>', body)
    nav = "".join(f'<a href="#{i}" class="l{lv}"{" hidden" if lv == "3" else ""}>{re.sub("<[^>]+>", "", t)}</a>'
                  for lv, i, t in toc if i != "contents")
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meridian · Help</title><style>
body{{margin:0;background:var(--bg,#f4f3f0);color:var(--text,#0b0b0b);font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
.hwrap{{display:grid;grid-template-columns:260px minmax(0,1fr);max-width:1280px;margin:0 auto}}
.hnav{{position:sticky;top:var(--appbar-h,52px);align-self:start;max-height:calc(100vh - var(--appbar-h,52px));overflow:auto;padding:20px 14px;border-right:1px solid #e2e0da}}
.hnav a{{display:block;color:#52514e;text-decoration:none;padding:4px 8px;border-radius:6px;font-size:14px}}.hnav a:hover{{background:#e8eef8;color:#0b0b0b}} .hnav a.l3{{padding-left:20px;font-size:13px}} .hnav a[hidden]{{display:none}}
.hql{{display:block;font-size:12px;font-weight:600;color:#52514e;margin:0 8px 4px}} #hq{{width:calc(100% - 16px);margin:0 8px 12px;padding:7px 9px;border:1px solid #cfccc4;border-radius:8px;font:inherit}}
.hn{{font-size:13px;color:#7a7873;margin:8px}}
.hmain{{padding:24px 36px 80px;max-width:980px}} .hmain h2{{margin-top:44px;padding-top:10px;border-top:1px solid #e2e0da;scroll-margin-top:70px}} .hmain h3{{scroll-margin-top:70px}}
.hmain img{{width:100%;height:auto;border:1px solid #e2e0da;border-radius:8px;margin:8px 0 4px}} .hmain table{{border-collapse:collapse;width:100%;font-size:14px}}
.hmain th,.hmain td{{border:1px solid #e2e0da;padding:6px 9px;text-align:left;vertical-align:top}} .hmain th{{background:#f0efec}} code{{background:#e8eef8;padding:1px 5px;border-radius:4px;font-size:13px}}
@media (max-width:860px){{.hwrap{{grid-template-columns:1fr}}.hnav{{position:static;max-height:none;border-right:0}}.hmain{{padding:16px}}}}
</style></head><body><div class="hwrap"><nav class="hnav" aria-label="Help contents"><label for="hq" class="hql">Search the guide</label>
<input id="hq" type="search" placeholder="e.g. rebalance, fills, ACT 40" autocomplete="off"><div id="hlinks">{nav}</div>
<p id="hnone" class="hn" hidden>No headings match. Try another word, or use your browser's find (Ctrl/Cmd+F).</p></nav><main class="hmain" id="main">{body}</main></div><script>
(function(){{const q=document.getElementById('hq'),links=[...document.querySelectorAll('#hlinks a')],none=document.getElementById('hnone');
q.addEventListener('input',()=>{{const v=q.value.trim().toLowerCase();let n=0;
links.forEach(a=>{{const hit=!v?a.classList.contains('l2'):a.textContent.toLowerCase().includes(v);a.hidden=!hit;if(hit)n++}});none.hidden=n>0}});
q.addEventListener('keydown',e=>{{if(e.key==='Enter'){{const a=links.find(x=>!x.hidden);if(a){{location.hash=a.getAttribute('href');e.preventDefault()}}}}}});}})();
</script></body></html>"""


@router.get("/help")
def help_page(request: Request):
    user = auth.current_user(request)
    if not user:
        return RedirectResponse("/login")
    if not _guide_path().exists():
        raise HTTPException(404, "User guide not packaged")
    return HTMLResponse(wrap(_guide_html(), user, "help"))


@router.get("/help/img/{name}")
def help_image(request: Request, name: str):
    auth.require_user(request)
    if not re.fullmatch(r"[a-z0-9-]+\.png", name):
        raise HTTPException(404, "Not found")
    p = REPO_ROOT / "docs" / "img" / "guide" / name
    if not p.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(p, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
