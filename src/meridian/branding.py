"""Brand themes (look and feel) from config/brand.yaml.

Every page uses the same CSS variables (--bg, --surface, --accent, ...). `theme_css()` returns a <style>
block that sets them for the active theme and is injected after each page's own styles, so a theme
change needs no page edits. Add a company by adding a theme to the YAML; switch with `active:` or the
MERIDIAN_BRAND environment variable.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import yaml

from . import REPO_ROOT

BRAND_PATH = REPO_ROOT / "config" / "brand.yaml"
TOKENS = ["bg", "surface", "surface-2", "line", "line-strong", "text", "text-2", "muted", "accent", "accent-hover",
          "accent-ink", "ok", "ok-bg", "warn", "warn-bg", "crit", "crit-bg", "info-bg", "focus"]
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@lru_cache(maxsize=4)
def _load(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text()) or {}


def themes(path: Path = BRAND_PATH) -> dict:
    return (_load(str(path)).get("themes") or {})


def active_name(path: Path = BRAND_PATH) -> str:
    name = os.getenv("MERIDIAN_BRAND") or _load(str(path)).get("active") or "meridian"
    return name if name in themes(path) else "meridian"


def active(path: Path = BRAND_PATH) -> dict:
    t = dict(themes(path).get(active_name(path)) or {})
    t["key"] = active_name(path)
    return t


def _vars(colors: dict, t: dict, dark: bool = False) -> str:
    out = [f"--{k}:{v}" for k, v in colors.items()]
    if "heading" not in colors and not dark:
        out.append("--heading:var(--text)")
    # console aliases: good = ok, info = accent, tilts pos/neg, neutral chip background
    derived = {"good": "var(--ok)", "good-bg": "var(--ok-bg)", "info": "var(--accent)", "off-bg": "var(--surface-2)",
               "pos": "var(--s1)", "neg": "var(--s2)", "mid": "var(--line-strong)"}
    if not dark:
        out += [f"--{k}:{v}" for k, v in derived.items() if k not in colors]
    if not dark:
        f, r, ab = t.get("fonts") or {}, t.get("radius") or {}, t.get("appbar") or {}
        out += [f"--font:{f.get('body', 'system-ui, sans-serif')}", f"--font-mono:{f.get('mono', 'ui-monospace, monospace')}",
                f"--radius-lg:{r.get('lg', '12px')}", f"--radius:{r.get('lg', '12px')}", f"--radius-sm:{r.get('sm', '8px')}"]
        out += [f"--appbar-{k}:{v}" for k, v in ab.items()]
        out += [f"--s{i + 1}:{c}" for i, c in enumerate(t.get("charts") or [])]
    return ";".join(out)


def theme_css(t: dict | None = None) -> str:
    """<style> for the theme: tokens for light and dark mode plus a few brand rules every page shares."""
    t = t or active()
    font_link = f'<link rel="stylesheet" href="{t["fonts"]["css"]}">' if (t.get("fonts") or {}).get("css") else ""
    # :root:root outranks the :root blocks in each page's own stylesheet, wherever they sit
    css = f":root:root{{{_vars(t.get('colors') or {}, t)}}}"
    if t.get("dark"):
        css += f"@media (prefers-color-scheme:dark){{:root:root{{{_vars(t['dark'], t, dark=True)}}}}}"
    css += ("body,button,input,select,textarea{font-family:var(--font)}"
            ".mono,code,pre,kbd{font-family:var(--font-mono)}"
            "h1,h2{color:var(--heading)}"
            ".btn.primary:hover,.mb.p:hover{background:var(--accent-hover);border-color:var(--accent-hover)}")
    return f'{font_link}<style id="meridian-brand" data-brand="{t.get("key", "")}">{css}</style>'


def logo_path(t: dict | None = None) -> Path | None:
    t = t or active()
    name = (t.get("logo") or "").strip()
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    p = REPO_ROOT / "config" / "brand" / name
    return p if p.is_file() else None


# ------------------------------------------------------------------ checks
def _lum(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


PAIRS = [("text", "surface"), ("text", "bg"), ("text-2", "surface"), ("muted", "surface"), ("accent", "surface"),
         ("accent-ink", "accent"), ("ok", "ok-bg"), ("warn", "warn-bg"), ("crit", "crit-bg"), ("crit", "surface"),
         ("text", "surface-2"), ("text", "info-bg")]


def check(t: dict) -> list[str]:
    """Problems with a theme: missing or malformed tokens, and text/background pairs below WCAG AA (4.5:1)."""
    problems = []
    for mode in ("colors", "dark"):
        c = t.get(mode)
        if c is None:
            if mode == "colors":
                problems.append("colors: missing")
            continue
        missing = [k for k in TOKENS if k not in c]
        if missing:
            problems.append(f"{mode}: missing {', '.join(missing)}")
        bad = [k for k, v in c.items() if not _HEX.match(str(v))]
        if bad:
            problems.append(f"{mode}: not #RRGGBB: {', '.join(bad)}")
        for fg, bg in PAIRS:
            if fg in c and bg in c and _HEX.match(str(c[fg])) and _HEX.match(str(c[bg])):
                r = contrast(c[fg], c[bg])
                if r < 4.5:
                    problems.append(f"{mode}: {fg} on {bg} contrast {r:.2f} < 4.5")
    ab = t.get("appbar") or {}
    for k in ("text", "muted"):
        if _HEX.match(str(ab.get(k, ""))) and _HEX.match(str(ab.get("bg", ""))) and contrast(ab[k], ab["bg"]) < 4.5:
            problems.append(f"appbar: {k} on bg contrast {contrast(ab[k], ab['bg']):.2f} < 4.5")
    return problems
