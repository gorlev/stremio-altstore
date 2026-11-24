#!/usr/bin/env python3
"""
mirror_release.py — mirror each Stremio IPA into a GitHub Release

The JSON sources point straight at Stremio's CDN, which is the right default:
it is the upstream copy and it carries the traffic. But a URL on someone
else's CDN is also the one part of this source that can disappear without
warning — `prune_dead.py` exists precisely because builds do get pulled, and
when one does, the only remaining option is to drop the version and strand
whoever was running it.

This mirrors every listed build into a GitHub Release of this repo, so there
is a second copy of the exact bytes this source vouches for:

    v2.1.3b28
      stremio_iOS.ipa
      stremio_tvOS.ipa
      SHA256SUMS.txt

One release per version *and build* — 2.0.1 shipped as both b15 and b16, so
the version alone is not a unique name. iOS and tvOS share a release because
they share a build number upstream; a build that only exists for one platform
simply gets one IPA, and the body says the other was never published.

Two rules keep a mirror from becoming a liability of its own:

  * A version is mirrored only once the source has recorded its `sha256`.
    Publishing a file this source cannot vouch for would make the mirror less
    trustworthy than the CDN it mirrors, so `add_hashes.py` goes first.
  * The hash is recomputed from the bytes as they are downloaded and compared
    against the recorded one. A mismatch means upstream replaced the file, so
    the release is skipped and reported rather than filled with bytes that no
    client would accept (`add_hashes.py --reverify` is what resolves it).

Downloads are ~170 MB per release, so this is budgeted like the hash backfill:
a few releases per run, newest first, until the backlog is gone. Thereafter
only each new build needs a run.

Usage:
    python3 scripts/mirror_release.py                    # mirror up to the budget
    python3 scripts/mirror_release.py --budget 3         # override the per-run budget
    python3 scripts/mirror_release.py --dry-run          # show the plan, download nothing
    python3 scripts/mirror_release.py --check            # report coverage, no writes
    python3 scripts/mirror_release.py --version 2.1.3b28 # one specific build

Budget resolution: --budget arg > MIRROR_BUDGET env > default (2).

Requires the `gh` CLI, authenticated with `contents: write` on this repo.

Exit codes:
    0 — ran successfully (including "nothing to do")
    1 — --check mode and at least one build is not mirrored yet
    2 — a recorded hash did not match the bytes on the CDN
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SOURCES = {"stremio-ios.json": "iOS", "stremio-tvos.json": "tvOS"}
DEFAULT_BUDGET = 2
USER_AGENT = "stremio-altstore/mirror_release/1.0"
CHECKSUM_FILE = "SHA256SUMS.txt"
HEX64 = re.compile(r"^[0-9a-f]{64}$")

UPSTREAM_NOTE = (
    "This is an **unofficial mirror**. The IPAs here are the unmodified files "
    "Stremio publishes on `dl.strem.io`, byte for byte — this repo does not "
    "build, repackage or re-sign anything. Stremio holds all rights to the app; "
    "if you represent them and want a build removed, open an issue and it will be."
)


# ---------------------------------------------------------------------------
# Planning — pure functions, no network and no `gh`
# ---------------------------------------------------------------------------

def tag_for(version: str, build: str) -> str:
    return f"v{version}b{build}"


def _version_key(version: str, build: str) -> tuple:
    parts = [int(c) if str(c).isdigit() else -1 for c in str(version).split(".")]
    try:
        b = int(build)
    except (TypeError, ValueError):
        b = 0
    return (parts, b)


def _has_valid_hash(v: dict) -> bool:
    h = v.get("sha256")
    return isinstance(h, str) and bool(HEX64.match(h))


def plan(sources: dict[str, dict]) -> list[dict]:
    """Group every listed version into one mirrorable release per version+build.

    Returns a list of releases, newest first. `assets` holds one entry per
    platform that upstream actually published for that build; `blocked` names
    the versions that cannot be mirrored yet (no recorded hash), so the caller
    can say why rather than silently skipping them.
    """
    by_tag: dict[str, dict] = {}

    for fname, platform in SOURCES.items():
        data = sources.get(fname) or {}
        for app in data.get("apps", []):
            for v in app.get("versions", []):
                version, build = v.get("version"), v.get("buildVersion")
                url = v.get("downloadURL")
                if not version or not build or not url:
                    continue
                tag = tag_for(version, build)
                entry = by_tag.setdefault(tag, {
                    "tag": tag,
                    "version": version,
                    "build": str(build),
                    "date": v.get("date") or "",
                    "assets": [],
                    "blocked": [],
                    "changelog": "",
                    "_key": _version_key(version, build),
                })
                # The newest date seen for the build labels the release.
                if (v.get("date") or "") > entry["date"]:
                    entry["date"] = v.get("date") or ""
                # iOS wins for the changelog because it is listed first; tvOS
                # fills in when a build is tvOS-only.
                if not entry["changelog"] and v.get("localizedDescription"):
                    entry["changelog"] = v["localizedDescription"]

                if not _has_valid_hash(v):
                    entry["blocked"].append(platform)
                    continue
                entry["assets"].append({
                    "platform": platform,
                    "name": url.rsplit("/", 1)[-1],
                    "url": url,
                    "size": v.get("size"),
                    "sha256": v["sha256"],
                    "minOSVersion": v.get("minOSVersion"),
                })

    releases = sorted(by_tag.values(), key=lambda e: e["_key"], reverse=True)
    for e in releases:
        e["assets"].sort(key=lambda a: a["platform"])
    return releases


def checksums_text(assets: list[dict]) -> str:
    """A `shasum -a 256 -c`-compatible manifest of the release's IPAs."""
    return "".join(f"{a['sha256']}  {a['name']}\n" for a in assets)


def _human(n) -> str:
    try:
        # Decimal MB, matching how Apple and the CDN report IPA sizes.
        return f"{int(n) / 1_000_000:.1f} MB"
    except (TypeError, ValueError):
        return "?"


def release_body(entry: dict) -> str:
    """The release description: what it is, what is in it, how to verify it."""
    lines = [
        f"Mirror of Stremio **{entry['version']}** (build {entry['build']})"
        + (f", published {entry['date']}." if entry["date"] else "."),
        "",
        UPSTREAM_NOTE,
        "",
        "### Files",
        "",
        "| Platform | File | Size | Minimum OS |",
        "| --- | --- | --- | --- |",
    ]
    for a in entry["assets"]:
        lines.append(
            f"| {a['platform']} | `{a['name']}` | {_human(a['size'])} | "
            f"{a.get('minOSVersion') or '?'} |"
        )

    missing = [p for p in SOURCES.values() if p not in {a["platform"] for a in entry["assets"]}]
    if missing:
        lines += ["", "Upstream published no "
                  + " or ".join(missing) + f" build for {entry['version']}b{entry['build']}."]

    lines += [
        "",
        "### Verify your download",
        "",
        "```",
        f"shasum -a 256 -c {CHECKSUM_FILE}",
        "```",
        "",
        "These are the same hashes the JSON sources carry, so a signing app that "
        "verifies integrity accepts either copy.",
        "",
        "### Upstream originals",
        "",
    ]
    lines += [f"- {a['platform']}: {a['url']}" for a in entry["assets"]]

    if entry["changelog"]:
        lines += ["", "### Upstream release notes", "", entry["changelog"].strip()]

    lines += [
        "",
        "---",
        "",
        "Installing: add the source to your signing app instead of downloading by hand — "
        "see the [README](https://github.com/gorlev/stremio-altstore#quick-start). "
        "These assets exist so a build stays reachable even if it is pulled from the CDN.",
    ]
    return "\n".join(lines) + "\n"


def missing_assets(entry: dict, existing: dict[str, dict[str, int]]) -> list[str]:
    """Which of this release's files are absent or the wrong size on GitHub.

    `existing` maps tag → {asset name: size}. A size mismatch counts as
    missing: a half-finished upload is worse than no mirror at all, because
    it looks like a working download until the hash check fails.
    """
    if entry["tag"] not in existing:
        return [a["name"] for a in entry["assets"]] + [CHECKSUM_FILE]

    have = existing[entry["tag"]]
    wanted = []
    for a in entry["assets"]:
        size = have.get(a["name"])
        if size is None or (a["size"] and size != a["size"]):
            wanted.append(a["name"])
    if CHECKSUM_FILE not in have:
        wanted.append(CHECKSUM_FILE)
    return wanted


# ---------------------------------------------------------------------------
# GitHub side
# ---------------------------------------------------------------------------

def _gh(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def repo_slug() -> str:
    slug = os.environ.get("GITHUB_REPOSITORY")
    if slug:
        return slug
    out = _gh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    return out.stdout.strip()


def existing_releases(slug: str) -> dict[str, dict[str, int]]:
    """Every release of the repo as {tag: {asset name: size}}."""
    found: dict[str, dict[str, int]] = {}
    page = 1
    while True:
        out = _gh(["api", f"/repos/{slug}/releases?per_page=100&page={page}"])
        batch = json.loads(out.stdout or "[]")
        if not batch:
            break
        for rel in batch:
            found[rel["tagName"] if "tagName" in rel else rel["tag_name"]] = {
                a["name"]: a.get("size", 0) for a in rel.get("assets", [])
            }
        if len(batch) < 100:
            break
        page += 1
    return found


def _download(url: str, dest: Path, *, expected_sha: str, timeout: int = 180,
              chunk: int = 1 << 20) -> dict:
    """Stream the IPA to disk, hashing as it goes, and refuse a mismatch."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    h = hashlib.sha256()
    total = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if getattr(r, "status", 200) != 200:
                return {"ok": False, "error": f"HTTP {getattr(r, 'status', '?')}"}
            with dest.open("wb") as fh:
                while True:
                    buf = r.read(chunk)
                    if not buf:
                        break
                    h.update(buf)
                    fh.write(buf)
                    total += len(buf)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"ok": False, "error": str(e)}
    if total == 0:
        return {"ok": False, "error": "empty body"}
    digest = h.hexdigest()
    if digest != expected_sha:
        return {"ok": False, "mismatch": True, "sha256": digest, "bytes": total,
                "error": f"sha256 mismatch: source says {expected_sha}, CDN served {digest}"}
    return {"ok": True, "sha256": digest, "bytes": total}


def mirror(entry: dict, slug: str, *, is_newest: bool, existing: dict[str, dict[str, int]]) -> dict:
    """Download the build's IPAs and upload them to its release."""
    work = Path(tempfile.mkdtemp(prefix="mirror-"))
    try:
        files: list[Path] = []
        for a in entry["assets"]:
            dest = work / a["name"]
            print(f"  [GET ] {a['platform']}: {a['url']}")
            res = _download(a["url"], dest, expected_sha=a["sha256"])
            if not res["ok"]:
                print(f"  [FAIL] {res['error']}")
                return {"ok": False, "mismatch": bool(res.get("mismatch"))}
            print(f"  [ok  ] {res['bytes']} bytes, sha256 verified")
            files.append(dest)

        manifest = work / CHECKSUM_FILE
        manifest.write_text(checksums_text(entry["assets"]), encoding="utf-8")
        files.append(manifest)

        notes = work / "notes.md"
        notes.write_text(release_body(entry), encoding="utf-8")

        if entry["tag"] in existing:
            print(f"  [EDIT] refreshing notes on {entry['tag']}")
            _gh(["release", "edit", entry["tag"], "--repo", slug,
                 "--title", f"Stremio {entry['version']} (build {entry['build']})",
                 "--notes-file", str(notes)])
        else:
            print(f"  [NEW ] creating release {entry['tag']}")
            _gh(["release", "create", entry["tag"], "--repo", slug,
                 "--title", f"Stremio {entry['version']} (build {entry['build']})",
                 "--notes-file", str(notes),
                 # Releases are filled newest-first, but the backlog is filled
                 # afterwards; without this an old build uploaded today would
                 # claim the "latest release" badge and the /latest URLs.
                 "--latest" if is_newest else "--latest=false"])

        print(f"  [PUT ] uploading {len(files)} asset(s)")
        _gh(["release", "upload", entry["tag"], *[str(f) for f in files],
             "--repo", slug, "--clobber"])
        return {"ok": True}
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--budget", type=int, default=None,
                    help="Max releases to mirror this run (default: MIRROR_BUDGET env or 2)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be mirrored, download and upload nothing")
    ap.add_argument("--check", action="store_true",
                    help="Report mirror coverage only; exit 1 if anything is unmirrored")
    ap.add_argument("--version", metavar="X.Y.ZbN", default=None,
                    help="Mirror one specific build (ignores the budget)")
    args = ap.parse_args()

    sources = {f: json.loads((REPO / f).read_text(encoding="utf-8")) for f in SOURCES}
    releases = plan(sources)

    blocked = [e for e in releases if e["blocked"]]
    for e in blocked:
        print(f"[WAIT] {e['tag']}: no recorded sha256 for "
              f"{', '.join(e['blocked'])} yet — add_hashes.py runs first")

    mirrorable = [e for e in releases if e["assets"]]
    if args.version:
        wanted = args.version if args.version.startswith("v") else f"v{args.version}"
        mirrorable = [e for e in mirrorable if e["tag"] == wanted]
        if not mirrorable:
            print(f"[ERROR] No mirrorable build matches {args.version}.")
            return 1

    if shutil.which("gh") is None:
        print("[ERROR] The `gh` CLI is required. See https://cli.github.com")
        return 1

    slug = repo_slug()
    if not slug:
        print("[ERROR] Could not determine the repository. Set GITHUB_REPOSITORY.")
        return 1
    existing = existing_releases(slug)

    todo = [e for e in mirrorable if missing_assets(e, existing)]
    done_count = len(mirrorable) - len(todo)
    print(f"[INFO] {slug}: {done_count}/{len(mirrorable)} build(s) mirrored, "
          f"{len(todo)} to go.")

    if args.check:
        for e in todo:
            print(f"  [MISSING] {e['tag']} → {', '.join(missing_assets(e, existing))}")
        return 1 if (todo or blocked) else 0

    if not todo:
        print("[OK] Every hashed build is mirrored. Nothing to do.")
        return 0

    if args.version:
        batch = todo
    else:
        budget = args.budget if args.budget is not None \
            else int(os.environ.get("MIRROR_BUDGET", DEFAULT_BUDGET))
        batch = todo[:max(0, budget)]

    if args.dry_run:
        print(f"[DRY-RUN] Would mirror {len(batch)} release(s):")
        for e in batch:
            total = sum(a["size"] or 0 for a in e["assets"])
            print(f"  - {e['tag']}: {', '.join(a['name'] for a in e['assets'])} "
                  f"+ {CHECKSUM_FILE} ({_human(total)})")
        return 0

    newest_tag = mirrorable[0]["tag"] if mirrorable else None
    mirrored = 0
    mismatches = 0
    for e in batch:
        print(f"[MIRROR] {e['tag']} — {e['version']} build {e['build']}")
        res = mirror(e, slug, is_newest=(e["tag"] == newest_tag), existing=existing)
        if res["ok"]:
            mirrored += 1
            print(f"  [DONE] https://github.com/{slug}/releases/tag/{e['tag']}")
        else:
            mismatches += int(res["mismatch"])
            print("  [SKIP] left unmirrored — will retry on the next run")

    remaining = len(todo) - mirrored
    print(f"[DONE] Mirrored {mirrored} release(s) this run. {remaining} still to go.")
    if mismatches:
        print(f"[ERROR] {mismatches} build(s) no longer match their recorded hash. "
              f"Run `python3 scripts/add_hashes.py --reverify` — upstream replaced the IPA.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
