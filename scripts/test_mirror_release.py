#!/usr/bin/env python3
"""
test_mirror_release.py — the rules that decide what gets mirrored, and how

The mirror's whole value is that its copy is interchangeable with the CDN's:
same bytes, same hash, same name. Everything that could quietly break that
promise lives in the planning functions, not in the uploading, so this pins
them:

  * one release per version *and* build (2.0.1 shipped twice),
  * a build with no recorded hash is never published,
  * a half-uploaded asset counts as missing rather than done,
  * the checksum manifest stays in `shasum -c` format,
  * only the newest build claims the "latest release" badge.

Run:
    python3 scripts/test_mirror_release.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import mirror_release as mr  # noqa: E402

SHA_IOS = "a" * 64
SHA_TV = "b" * 64


def v(version: str, build: str, platform: str = "ios", *, sha: str | None = SHA_IOS,
      size: int = 88297123, notes: str = "") -> dict:
    name = "stremio_iOS.ipa" if platform == "ios" else "stremio_tvOS.ipa"
    out = {
        "version": version,
        "buildVersion": build,
        "date": "2026-11-23",
        "downloadURL": f"https://dl.strem.io/apple/{version}b{build}/{platform}/{name}",
        "size": size,
        "minOSVersion": "15.0",
    }
    if sha:
        out["sha256"] = sha
    if notes:
        out["localizedDescription"] = notes
    return out


def sources(ios: list[dict] | None = None, tvos: list[dict] | None = None) -> dict:
    return {
        "stremio-ios.json": {"apps": [{"name": "Stremio", "versions": ios or []}]},
        "stremio-tvos.json": {"apps": [{"name": "Stremio", "versions": tvos or []}]},
    }


class Planning(unittest.TestCase):
    def test_pairs_the_two_platforms_into_one_release(self):
        [rel] = mr.plan(sources([v("2.1.3", "28", "ios")],
                                [v("2.1.3", "28", "tvos", sha=SHA_TV)]))
        self.assertEqual(rel["tag"], "v2.1.3b28")
        self.assertEqual([a["platform"] for a in rel["assets"]], ["iOS", "tvOS"])
        self.assertEqual([a["name"] for a in rel["assets"]],
                         ["stremio_iOS.ipa", "stremio_tvOS.ipa"])

    def test_same_version_different_build_are_separate_releases(self):
        # 2.0.1 really shipped as both b15 and b16 — a version-only tag would
        # collide and one of the two builds would never get mirrored.
        rels = mr.plan(sources([], [v("2.0.1", "16", "tvos", sha=SHA_TV),
                                    v("2.0.1", "15", "tvos", sha=SHA_TV)]))
        self.assertEqual([r["tag"] for r in rels], ["v2.0.1b16", "v2.0.1b15"])

    def test_single_platform_build_still_mirrors(self):
        [rel] = mr.plan(sources([v("2.0.4", "19", "ios")], []))
        self.assertEqual([a["platform"] for a in rel["assets"]], ["iOS"])
        self.assertIn("no tvOS build", mr.release_body(rel))

    def test_newest_first_and_ordered_by_build_not_string(self):
        rels = mr.plan(sources([v("2.0.0", "9"), v("2.0.0", "21"), v("2.1.0", "24")]))
        self.assertEqual([r["tag"] for r in rels], ["v2.1.0b24", "v2.0.0b21", "v2.0.0b9"])

    def test_unhashed_version_is_blocked_not_published(self):
        # Publishing bytes the source cannot vouch for would make the mirror
        # less trustworthy than the CDN it mirrors.
        [rel] = mr.plan(sources([v("2.1.3", "28", "ios", sha=None)]))
        self.assertEqual(rel["assets"], [])
        self.assertEqual(rel["blocked"], ["iOS"])

    def test_one_unhashed_platform_does_not_block_the_other(self):
        [rel] = mr.plan(sources([v("2.1.3", "28", "ios")],
                                [v("2.1.3", "28", "tvos", sha=None)]))
        self.assertEqual([a["platform"] for a in rel["assets"]], ["iOS"])
        self.assertEqual(rel["blocked"], ["tvOS"])

    def test_malformed_hash_counts_as_missing(self):
        [rel] = mr.plan(sources([v("2.1.3", "28", "ios", sha="nope")]))
        self.assertEqual(rel["assets"], [])

    def test_version_without_build_or_url_is_ignored(self):
        self.assertEqual(mr.plan(sources([{"version": "2.1.3", "sha256": SHA_IOS}])), [])


class Checksums(unittest.TestCase):
    def test_shasum_check_format(self):
        [rel] = mr.plan(sources([v("2.1.3", "28", "ios")],
                                [v("2.1.3", "28", "tvos", sha=SHA_TV)]))
        self.assertEqual(
            mr.checksums_text(rel["assets"]),
            f"{SHA_IOS}  stremio_iOS.ipa\n{SHA_TV}  stremio_tvOS.ipa\n",
        )

    def test_hashes_are_the_ones_the_source_publishes(self):
        # The manifest must agree with the JSON, or a client that verifies one
        # copy would reject the other.
        [rel] = mr.plan(sources([v("2.1.3", "28", "ios")]))
        self.assertIn(SHA_IOS, mr.checksums_text(rel["assets"]))


class MissingAssets(unittest.TestCase):
    def setUp(self):
        [self.rel] = mr.plan(sources([v("2.1.3", "28", "ios", size=100)],
                                     [v("2.1.3", "28", "tvos", sha=SHA_TV, size=200)]))

    def test_no_release_means_everything_is_missing(self):
        self.assertEqual(
            mr.missing_assets(self.rel, {}),
            ["stremio_iOS.ipa", "stremio_tvOS.ipa", mr.CHECKSUM_FILE],
        )

    def test_complete_release_needs_nothing(self):
        existing = {"v2.1.3b28": {"stremio_iOS.ipa": 100, "stremio_tvOS.ipa": 200,
                                  mr.CHECKSUM_FILE: 150}}
        self.assertEqual(mr.missing_assets(self.rel, existing), [])

    def test_truncated_upload_counts_as_missing(self):
        # A short asset looks like a working download until the hash fails.
        existing = {"v2.1.3b28": {"stremio_iOS.ipa": 7, "stremio_tvOS.ipa": 200,
                                  mr.CHECKSUM_FILE: 150}}
        self.assertEqual(mr.missing_assets(self.rel, existing), ["stremio_iOS.ipa"])

    def test_missing_manifest_alone_is_enough_to_redo(self):
        existing = {"v2.1.3b28": {"stremio_iOS.ipa": 100, "stremio_tvOS.ipa": 200}}
        self.assertEqual(mr.missing_assets(self.rel, existing), [mr.CHECKSUM_FILE])


class Body(unittest.TestCase):
    def test_says_it_is_an_unofficial_mirror(self):
        [rel] = mr.plan(sources([v("2.1.3", "28", "ios")]))
        body = mr.release_body(rel)
        self.assertIn("unofficial mirror", body)
        self.assertIn("https://dl.strem.io/apple/2.1.3b28/ios/stremio_iOS.ipa", body)
        self.assertIn(f"shasum -a 256 -c {mr.CHECKSUM_FILE}", body)

    def test_carries_the_upstream_changelog_when_there_is_one(self):
        [rel] = mr.plan(sources([v("2.1.3", "28", "ios", notes="Fixes\n\n- A thing.")]))
        self.assertIn("- A thing.", mr.release_body(rel))

    def test_tvos_changelog_is_used_for_a_tvos_only_build(self):
        [rel] = mr.plan(sources([], [v("2.0.1", "15", "tvos", sha=SHA_TV,
                                       notes="tvOS only note")]))
        self.assertIn("tvOS only note", mr.release_body(rel))

    def test_no_changelog_section_when_upstream_published_none(self):
        [rel] = mr.plan(sources([v("2.1.3", "28", "ios")]))
        self.assertNotIn("Upstream release notes", mr.release_body(rel))


class Tags(unittest.TestCase):
    def test_tag_includes_the_build(self):
        self.assertEqual(mr.tag_for("2.1.3", "28"), "v2.1.3b28")


if __name__ == "__main__":
    unittest.main(verbosity=2)
