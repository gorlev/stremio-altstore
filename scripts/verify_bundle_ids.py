#!/usr/bin/env python3
"""
verify_bundle_ids.py — Standalone IPA Info.plist verifier

For every IPA reference in the JSON sources, this script downloads only the
Info.plist portion via HTTP Range, reads the real bundle identifier, version,
build, and minOS values, and compares them against the JSON entries.

Usage:
    python3 scripts/verify_bundle_ids.py                      # Both JSONs
    python3 scripts/verify_bundle_ids.py stremio-ios.json      # Single file
    python3 scripts/verify_bundle_ids.py --verbose             # Detailed output
    python3 scripts/verify_bundle_ids.py --fix                 # Correct minOSVersion

--fix only rewrites `minOSVersion`, where the IPA is unambiguously the
authority and the field merely advertises compatibility. A wrong bundle
identifier, version or build defines the entry's identity, so those stay
reported-only and need a human.

This reads ~25 IPAs over the network, so "could not read it" and "the
metadata is wrong" are kept apart, the way prune_dead.py separates "gone"
from "unreachable". An IPA that will not load is retried and then reported
as a warning; a single flaky request must not raise an audit issue claiming
the sources have drifted. Only a real mismatch does that — or so many
unreadable IPAs that the run cannot vouch for anything.

Exit codes:
    0 — every value that could be checked matches
    1 — a genuine mismatch, or a source file is missing: needs a human
    2 — inconclusive: too many IPAs could not be read to trust the result
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import ipa_plist  # noqa: E402
from ipa_plist import get_main_app_info_plist  # noqa: E402

ipa_plist.USER_AGENT = "stremio-altstore/verify_bundle_ids/1.0"

# Re-reads before an IPA counts as unreadable. The parser makes several Range
# requests per IPA, so a transient failure is likelier here than on a HEAD.
DEFAULT_RETRIES = 2
# Above this share of unreadable IPAs the run proves nothing: report it as
# inconclusive rather than quietly passing on the few that did load.
UNREADABLE_TOLERANCE = 1 / 3


def read_plist(url: str, retries: int = DEFAULT_RETRIES) -> dict:
    """get_main_app_info_plist, retried — a dropped Range request is not a verdict."""
    result: dict = {}
    for _ in range(retries + 1):
        result = get_main_app_info_plist(url)
        if result.get("ok"):
            return result
    return result


def verify(json_paths: list[Path], verbose: bool = False, fix: bool = False) -> int:
    total = 0
    passed = 0
    mismatches = 0
    unreadable: list[str] = []
    missing_files = 0
    fixed = 0

    for json_path in json_paths:
        if not json_path.exists():
            print(f"[ERR] {json_path} not found")
            missing_files += 1
            continue

        data = json.loads(json_path.read_text(encoding="utf-8"))
        file_fixed = 0
        print(f"\n=== {json_path.name} — {data.get('name', '?')} ===")

        for app in data.get("apps", []):
            bundle = app.get("bundleIdentifier", "?")
            print(f"\n  App: {app.get('name')} ({bundle})")

            for v in app.get("versions", []):
                total += 1
                url = v.get("downloadURL")
                if not url:
                    print(f"    [SKIP] no downloadURL for version {v.get('version')}")
                    continue

                info = read_plist(url)
                if not info.get("ok"):
                    # Not drift: we never got to see the metadata. Warn, and
                    # let the tolerance check below decide whether the run as
                    # a whole still means anything.
                    print(f"    [????] {v.get('version')} (build {v.get('buildVersion')}): "
                          f"could not read IPA ({info.get('error')}) — not counted as a mismatch")
                    unreadable.append(f"{json_path.name}: {app.get('name')} "
                                      f"{v.get('version')} build {v.get('buildVersion')} "
                                      f"({info.get('error')})")
                    continue

                plist = info["plist"]                                            
                ipa_bundle = plist.get("CFBundleIdentifier", "?")
                ipa_ver = plist.get("CFBundleShortVersionString", "?")
                ipa_build = plist.get("CFBundleVersion", "?")
                ipa_minos = plist.get("MinimumOSVersion", "?")

                json_ver = v.get("version")
                json_build = v.get("buildVersion")
                json_minos = v.get("minOSVersion")

                ok = True
                if ipa_bundle != bundle:
                    print(f"    [DIFF] bundleId: json={bundle!r} ipa={ipa_bundle!r}")
                    ok = False
                if str(ipa_ver) != str(json_ver):
                    print(f"    [DIFF] version: json={json_ver!r} ipa={ipa_ver!r}")
                    ok = False
                if str(ipa_build) != str(json_build):
                    print(f"    [DIFF] build: json={json_build!r} ipa={ipa_build!r}")
                    ok = False
                if str(ipa_minos) != str(json_minos):
                    print(f"    [DIFF] minOS: json={json_minos!r} ipa={ipa_minos!r}")
                    # minOSVersion is safe to correct automatically: the IPA is
                    # the authority and the field only advertises compatibility.
                    # bundleId / version / build are deliberately NOT auto-fixed —
                    # those define the entry's identity, so they need a human.
                    if fix and ipa_minos != "?":
                        v["minOSVersion"] = str(ipa_minos)
                        fixed += 1
                        file_fixed += 1
                        print(f"    [FIX ] minOS -> {ipa_minos!r}")
                    else:
                        ok = False

                if ok:
                    passed += 1
                    mark = "✓"
                    if verbose:
                        print(f"    [{mark}] {ipa_ver} (build {ipa_build}) bundle={ipa_bundle} minOS={ipa_minos}")
                    else:
                        print(f"    [{mark}] {ipa_ver} build {ipa_build}")
                else:
                    mismatches += 1

        if fix and file_fixed:
            json_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"\n[WRITE] {json_path.name} updated ({file_fixed} minOS value(s) corrected)")

    print("\n=== Summary ===")
    print(f"Total: {total}, matching: {passed}, mismatches: {mismatches}, "
          f"unreadable: {len(unreadable)}, corrected: {fixed}")

    for u in unreadable:
        print(f"[WARN] Could not read, left untouched — {u}")

    if missing_files:
        print(f"\n[ERROR] {missing_files} source file(s) missing.")
        return 1
    if mismatches:
        print(f"\n[ERROR] {mismatches} entr(ies) disagree with their IPA's own Info.plist.")
        return 1

    # Nothing is wrong, but say so honestly: if most IPAs would not load, this
    # run checked almost nothing and should not read as a clean bill of health.
    checked = total - len(unreadable)
    if unreadable and (checked == 0 or len(unreadable) > total * UNREADABLE_TOLERANCE):
        print(f"\n[INCONCLUSIVE] {len(unreadable)} of {total} IPAs could not be read "
              f"(over the {UNREADABLE_TOLERANCE:.0%} tolerance). Nothing looks drifted, "
              f"but this run cannot vouch for the metadata.")
        return 2
    if unreadable:
        print(f"\nOK — {checked}/{total} verified. "
              f"{len(unreadable)} IPA(s) were unreachable this run and will be re-checked.")
        return 0
    return 0


def main() -> int:
    args = sys.argv[1:]
    verbose = "--verbose" in args or "-v" in args
    fix = "--fix" in args
    args = [a for a in args if a not in ("--verbose", "-v", "--fix")]

    here = Path(__file__).parent.parent
    if not args:
        paths = [here / "stremio-ios.json", here / "stremio-tvos.json"]
    else:
        paths = [Path(a) for a in args]

    paths = [p if p.is_absolute() else here / p for p in paths]
    return verify(paths, verbose=verbose, fix=fix)


if __name__ == "__main__":
    sys.exit(main())
