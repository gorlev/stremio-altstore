#!/usr/bin/env python3
"""
test_updater_logic.py — the discovery and merge logic behind the source

Covers the pure logic in stremio-updater.py, i.e. everything that decides
*which* builds we look for and *how* an entry is written. Two of these guard
bugs that already reached users once:

  * 2.0.6b21 shipped and five scheduled runs never even requested its URL,
    because candidate versions came from a hand-written list. There is now a
    regression test for exactly that build.
  * The hash backfill and the updater both write to the same entries. If
    merge_version ever rebuilt a version object instead of updating it in
    place, every sha256 would silently disappear on the next run.

Run:
    python3 scripts/test_updater_logic.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import ipa_plist  # noqa: E402  (HttpResp, for faking the CDN)

# The module filename has a hyphen, so it cannot be imported by name.
_spec = importlib.util.spec_from_file_location("stremio_updater", REPO / "stremio-updater.py")
updater = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(updater)


class VersionTags(unittest.TestCase):
    def test_parses_a_tag(self):
        self.assertEqual(updater.parse_version_tag("2.0.2b17"), ("2.0.2", 17))

    def test_rejects_nonsense(self):
        for bad in ("2.0.2", "b17", "2.0.2-17", "", "v2.0.2b17"):
            self.assertIsNone(updater.parse_version_tag(bad), bad)


class SemverCandidates(unittest.TestCase):
    """What the scanner will actually probe next."""

    def test_finds_the_build_that_was_missed_in_production(self):
        # The reported bug: knowing 2.0.5, nothing ever probed 2.0.6.
        known = {"1.3.6", "2.0.0", "2.0.1", "2.0.2", "2.0.3", "2.0.4", "2.0.5"}
        cands = updater.next_semver_candidates(known)
        self.assertIn("2.0.6", cands)

    def test_reaches_several_patches_ahead(self):
        cands = updater.next_semver_candidates({"2.0.6"})
        for expected in ("2.0.7", "2.0.8", "2.0.9", "2.0.10"):
            self.assertIn(expected, cands)

    def test_reaches_the_next_minor_and_major(self):
        cands = updater.next_semver_candidates({"2.0.6"})
        self.assertIn("2.1.0", cands)
        self.assertIn("2.1.1", cands)
        self.assertIn("3.0.0", cands)

    def test_anchors_on_the_highest_version_of_each_major_line(self):
        # 1.x and 2.x both continue to be watched, from their own newest.
        cands = updater.next_semver_candidates({"1.3.6", "2.0.6"})
        self.assertIn("1.3.7", cands)
        self.assertIn("2.0.7", cands)

    def test_does_not_look_backwards(self):
        cands = updater.next_semver_candidates({"2.0.6"})
        self.assertNotIn("2.0.5", cands)
        self.assertNotIn("2.0.6", cands)

    def test_survives_junk_input(self):
        # Never raise on a malformed entry: a crash here stops all discovery.
        self.assertIsInstance(updater.next_semver_candidates({"", "abc", "1", "2.0.6"}), set)

    def test_stays_a_small_probe_set(self):
        # Each candidate becomes HEAD requests across platforms and builds.
        self.assertLess(len(updater.next_semver_candidates({"1.3.6", "2.0.6"})), 40)


def make_app(versions=None):
    return {"name": "Stremio", "bundleIdentifier": "com.stremio.pal",
            "versions": versions if versions is not None else []}


META = {"url": "https://dl.strem.io/apple/2.0.6b21/ios/stremio_iOS.ipa",
        "size": 75942223, "date": "2026-07-22"}


class MergeVersion(unittest.TestCase):
    def test_adds_a_new_version(self):
        app = make_app()
        self.assertTrue(updater.merge_version(app, "2.0.6", 21, META, None))
        self.assertEqual(len(app["versions"]), 1)
        v = app["versions"][0]
        self.assertEqual((v["version"], v["buildVersion"]), ("2.0.6", "21"))
        self.assertIsInstance(v["buildVersion"], str, "consumers compare build as text")

    def test_build_number_defaults_min_os_when_no_plist(self):
        app = make_app()
        updater.merge_version(app, "2.0.6", 21, META, None)
        self.assertEqual(app["versions"][0]["minOSVersion"], "13.0")

    def test_uses_the_real_min_os_when_the_plist_was_read(self):
        app = make_app()
        updater.merge_version(app, "2.0.6", 21, META, {"MinimumOSVersion": "15.0"})
        self.assertEqual(app["versions"][0]["minOSVersion"], "15.0")

    def test_existing_version_is_updated_in_place(self):
        app = make_app()
        updater.merge_version(app, "2.0.6", 21, META, None)
        changed = updater.merge_version(app, "2.0.6", 21, {**META, "size": 999999}, None)
        self.assertTrue(changed)
        self.assertEqual(len(app["versions"]), 1, "must refresh, not duplicate")
        self.assertEqual(app["versions"][0]["size"], 999999)

    def test_no_change_reports_false(self):
        app = make_app()
        updater.merge_version(app, "2.0.6", 21, META, None)
        self.assertFalse(updater.merge_version(app, "2.0.6", 21, META, None))

    def test_refreshing_a_version_keeps_its_sha256(self):
        # The invariant that makes the hash backfill safe: the updater runs
        # every 6 hours over the same entries and must not wipe their hashes.
        app = make_app()
        updater.merge_version(app, "2.0.6", 21, META, None)
        app["versions"][0]["sha256"] = "a" * 64
        updater.merge_version(app, "2.0.6", 21, {**META, "size": 42_000_000}, None)
        self.assertEqual(app["versions"][0]["sha256"], "a" * 64)

    def test_refreshing_a_version_keeps_its_release_notes(self):
        # Same for captured changelogs: upstream drops them from its rolling
        # window, so a wipe here would be unrecoverable.
        app = make_app()
        updater.merge_version(app, "2.0.6", 21, META, None)
        app["versions"][0]["localizedDescription"] = "feat: something real"
        updater.merge_version(app, "2.0.6", 21, {**META, "size": 42_000_000}, None)
        self.assertEqual(app["versions"][0]["localizedDescription"], "feat: something real")

    def test_versions_are_sorted_newest_first(self):
        app = make_app()
        for ver, build in (("2.0.0", 11), ("2.0.6", 21), ("2.0.1", 16), ("2.0.1", 15)):
            updater.merge_version(app, ver, build, META, None)
        order = [(v["version"], v["buildVersion"]) for v in app["versions"]]
        self.assertEqual(order[0], ("2.0.6", "21"))
        self.assertEqual(order[-1], ("2.0.0", "11"))


class ScanReach(unittest.TestCase):
    """Which URLs the scan actually asks for.

    The original miss was not a parsing bug: nothing ever requested the new
    build's URL. So these assert on the requests themselves.
    """

    def setUp(self):
        self._real = updater.http_request
        updater.upstream_release_tags.cache_clear()
        self.asked: list[str] = []

    def tearDown(self):
        updater.http_request = self._real
        updater.upstream_release_tags.cache_clear()

    def serve_upstream(self, versions, *, status=200, body=None):
        """Fake CDN: upstream source answers with `versions`, IPAs all 404."""
        payload = json.dumps({"apps": [{"versions": versions}]}).encode()

        def fake(url, *, method="GET", headers=None, timeout=15):
            if url == updater.UPSTREAM_SOURCE:
                return ipa_plist.HttpResp(status, {}, body if body is not None else payload)
            self.asked.append(url)
            return ipa_plist.HttpResp(404, {}, None)

        updater.http_request = fake

    def probed_tags(self) -> set[str]:
        # .../apple/<tag>/<platform>/<file>
        return {u.split("/apple/")[1].split("/")[0] for u in self.asked}

    def test_probes_a_build_far_beyond_the_local_window(self):
        # The blind spot: builds are a global counter, so a jump larger than
        # BUILD_LOOKAHEAD used to be unreachable forever.
        far = str(21 + updater.BUILD_LOOKAHEAD + 14)
        self.serve_upstream([{"version": "2.1.0", "buildVersion": far}])
        updater.scan_cdn({"2.0.6b21"})
        self.assertIn(f"2.1.0b{far}", self.probed_tags())

    def test_still_probes_the_derived_window(self):
        self.serve_upstream([{"version": "2.0.6", "buildVersion": "21"}])
        updater.scan_cdn({"2.0.6b21"})
        tags = self.probed_tags()
        self.assertIn("2.0.7b22", tags)
        self.assertIn("2.1.0b22", tags)

    def test_probes_both_platforms(self):
        self.serve_upstream([{"version": "2.0.6", "buildVersion": "21"}])
        updater.scan_cdn({"2.0.6b21"})
        self.assertTrue(any("/ios/" in u for u in self.asked))
        self.assertTrue(any("/tvos/" in u for u in self.asked))

    def test_probes_only_the_platforms_it_was_given(self):
        # The scan used to be called once per platform while probing both
        # every time, so half of each run's requests were discarded unread.
        self.serve_upstream([{"version": "2.0.6", "buildVersion": "21"}])
        updater.scan_cdn({"2.0.6b21"}, platforms=["ios"])
        self.assertTrue(any("/ios/" in u for u in self.asked))
        self.assertFalse(any("/tvos/" in u for u in self.asked))

    def test_an_unknown_platform_is_refused(self):
        # Silently probing nothing would look like "no new versions".
        self.serve_upstream([{"version": "2.0.6", "buildVersion": "21"}])
        with self.assertRaises(ValueError):
            updater.scan_cdn({"2.0.6b21"}, platforms=["ipados"])

    def test_results_are_keyed_only_by_the_requested_platforms(self):
        self.serve_upstream([{"version": "2.0.6", "buildVersion": "21"}])
        found = updater.scan_cdn({"2.0.6b21"}, platforms=["tvos"])
        self.assertEqual(set(found), {"tvos"})

    def test_unreachable_upstream_does_not_stop_the_scan(self):
        # Discovery must survive on its own if Stremio's source is down.
        self.serve_upstream([], status=503)
        updater.scan_cdn({"2.0.6b21"})
        self.assertIn("2.0.7b22", self.probed_tags())

    def test_malformed_upstream_does_not_raise(self):
        self.serve_upstream([], body=b"<html>not json</html>")
        updater.scan_cdn({"2.0.6b21"})
        self.assertIn("2.0.7b22", self.probed_tags())

    def test_probe_count_stays_bounded(self):
        # Every candidate is a HEAD request against someone else's CDN.
        self.serve_upstream([{"version": "2.0.6", "buildVersion": "21"}])
        updater.scan_cdn({"1.3.6b7", "2.0.6b21"})
        self.assertLess(len(self.asked), 600, "scan should not hammer the CDN")


class HttpDateParsing(unittest.TestCase):
    def test_rfc1123(self):
        self.assertEqual(updater.parse_http_date("Wed, 22 Jul 2026 02:26:01 GMT"), "2026-07-22")

    def test_garbage_is_empty_not_an_exception(self):
        self.assertEqual(updater.parse_http_date("not a date"), "")
        self.assertEqual(updater.parse_http_date(""), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
