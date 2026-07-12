#!/usr/bin/env python3
"""
render_readme.py — regenerate the "Available versions" tables in README.md

Reads stremio-ios.json and stremio-tvos.json and rewrites ONLY the block
between the markers:

    <!-- BEGIN:AVAILABLE_VERSIONS ... -->
    <!-- END:AVAILABLE_VERSIONS -->

Everything else in README.md is left untouched. No network access — the
tables are built purely from the JSON sources, so the output is fully
deterministic and safe to run in CI.

Usage:
    python3 scripts/render_readme.py           # rewrite README.md in place
    python3 scripts/render_readme.py --check    # exit 1 if README is stale (no write)

Exit codes:
    0 — README already up to date (or was updated successfully)
    1 — --check mode and README is stale
    2 — markers missing / malformed README (nothing written)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BEGIN = "<!-- BEGIN:AVAILABLE_VERSIONS -->"
END = "<!-- END:AVAILABLE_VERSIONS -->"

REPO = Path(__file__).resolve().parent.parent

# Platform sources in display order. `badge` is the label used in the
# shields.io count badge at the top of the README (e.g. iOS-7%20versions).
PLATFORMS = [
    {"json": "stremio-ios.json", "heading": "iOS / iPadOS", "badge": "iOS"},
    {"json": "stremio-tvos.json", "heading": "tvOS", "badge": "tvOS"},
]

# Human labels appended after the app name, keyed by bundle identifier.
# Unknown bundles simply get no annotation (graceful fallback).
BUNDLE_ANNOTATION = {
    "com.stremio.pal": "(PAL, full-featured)",
    "com.stremio.ios": "(legacy)",
}


def _version_key(v: dict) -> tuple:
    """Sort key: newest first by (version tuple desc, build desc)."""
    parts = []
    for chunk in str(v.get("version", "")).split("."):
        parts.append(int(chunk) if chunk.isdigit() else -1)
    try:
        build = int(v.get("buildVersion", 0))
    except (TypeError, ValueError):
        build = 0
    return (parts, build)


def _mb(size_bytes) -> str:
    try:
        n = int(size_bytes)
    except (TypeError, ValueError):
        return "?"
    if n <= 0:
        return "?"
    # Floor to match the updater's own logging convention (size // 1024 // 1024).
    return f"{n // 1024 // 1024} MB"


def _app_table(app: dict) -> str:
    rows = [
        "| Version | Build | Date | Size | Download |",
        "|---|---|---|---|---|",
    ]
    versions = sorted(app.get("versions", []), key=_version_key, reverse=True)
    for v in versions:
        version = v.get("version", "?")
        build = v.get("buildVersion", "?")
        date = v.get("date", "?")
        size = _mb(v.get("size"))
        url = v.get("downloadURL", "")
        download = f"[IPA]({url})" if url else "—"
        rows.append(f"| {version} | {build} | {date} | {size} | {download} |")
    return "\n".join(rows)


def _load(plat: dict) -> dict:
    return json.loads((REPO / plat["json"]).read_text(encoding="utf-8"))


def build_block() -> str:
    sections: list[str] = []
    for plat in PLATFORMS:
        data = _load(plat)
        sections.append(f"### {plat['heading']} — `{plat['json']}`")
        for app in data.get("apps", []):
            name = app.get("name", "App")
            bundle = app.get("bundleIdentifier", "")
            annotation = BUNDLE_ANNOTATION.get(bundle, "")
            header = f"#### {name} {annotation}".rstrip()
            if bundle:
                header += f" — `{bundle}`"
            sections.append(header)
            sections.append(_app_table(app))
    return "\n\n".join(sections)


def update_badges(text: str) -> str:
    """Sync the shields.io version-count badges at the top of the README.

    Targets only the `img.shields.io/badge/{LABEL}-{N}%20versions` URLs, so
    it never touches other badges. If a badge is absent, it's a no-op.
    """
    for plat in PLATFORMS:
        data = _load(plat)
        total = sum(len(app.get("versions", [])) for app in data.get("apps", []))
        pattern = re.compile(
            r"(img\.shields\.io/badge/" + re.escape(plat["badge"]) + r"-)\d+(%20versions)"
        )
        text = pattern.sub(rf"\g<1>{total}\g<2>", text)
    return text


def render(check: bool) -> int:
    readme_path = REPO / "README.md"
    text = readme_path.read_text(encoding="utf-8")

    if BEGIN not in text or END not in text:
        print(f"[ERR] markers not found in README.md ({BEGIN} / {END})", file=sys.stderr)
        return 2
    if text.index(BEGIN) > text.index(END):
        print("[ERR] BEGIN marker appears after END marker", file=sys.stderr)
        return 2

    pre, rest = text.split(BEGIN, 1)
    _old_block, post = rest.split(END, 1)

    block = build_block()
    new_text = f"{pre}{BEGIN}\n\n{block}\n\n{END}{post}"
    new_text = update_badges(new_text)

    if new_text == text:
        print("[OK] README.md already up to date.")
        return 0

    if check:
        print("[STALE] README.md 'Available versions' block is out of date. "
              "Run: python3 scripts/render_readme.py", file=sys.stderr)
        return 1

    readme_path.write_text(new_text, encoding="utf-8")
    print("[OK] README.md 'Available versions' block regenerated.")
    return 0


def main() -> int:
    check = "--check" in sys.argv[1:]
    return render(check=check)


if __name__ == "__main__":
    sys.exit(main())
