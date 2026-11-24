#!/usr/bin/env python3
"""
test_derived_data.py — the scripts that rewrite files from data we already have

render_readme, sync_legacy_fields, fetch_release_notes and add_hashes all edit
published files in place. Their failure mode is quiet: a bad marker match eats
part of the README, a sloppy sanitiser puts raw control bytes in front of
users, a rebuilt version object drops the sha256 that took a 70 MB download to
compute. None of that raises an exception, so only assertions catch it.

Run:
    python3 scripts/test_derived_data.py
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
import add_hashes  # noqa: E402
import build_news  # noqa: E402
import fetch_release_notes as notes  # noqa: E402
import render_readme  # noqa: E402
import sync_legacy_fields as legacy  # noqa: E402


def version(ver, build, **extra):
    v = {"version": ver, "buildVersion": build, "date": "2026-07-22",
         "localizedDescription": f"Stremio {ver} (build {build}).",
         "downloadURL": f"https://dl.strem.io/apple/{ver}b{build}/ios/stremio_iOS.ipa",
         "size": 75942223, "minOSVersion": "13.0"}
    v.update(extra)
    return v


def doc(versions):
    return {"name": "Stremio iOS", "identifier": "x",
            "sourceURL": "https://example.com/stremio-ios.json",
            "apps": [{"name": "Stremio", "bundleIdentifier": "com.stremio.pal",
                      "versions": versions}]}


# --------------------------------------------------------------------------
# render_readme
# --------------------------------------------------------------------------

TEMPLATE = """# Title

[![Stremio iOS versions](https://img.shields.io/badge/iOS-99%20versions-7055D9)](stremio-ios.json)

Intro paragraph that must survive.

## Available versions

<!-- BEGIN:AVAILABLE_VERSIONS -->
stale content
<!-- END:AVAILABLE_VERSIONS -->

## Footer that must also survive
"""


class RenderReadme(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self._orig = (render_readme.REPO, render_readme.PLATFORMS)
        render_readme.REPO = self.dir
        render_readme.PLATFORMS = [{"json": "stremio-ios.json", "heading": "iOS / iPadOS",
                                    "badge": "iOS"}]
        (self.dir / "stremio-ios.json").write_text(
            json.dumps(doc([version("2.0.6", "21"), version("2.0.0", "11")])), encoding="utf-8")
        (self.dir / "README.md").write_text(TEMPLATE, encoding="utf-8")

    def tearDown(self):
        render_readme.REPO, render_readme.PLATFORMS = self._orig
        self._tmp.cleanup()

    def readme(self) -> str:
        return (self.dir / "README.md").read_text(encoding="utf-8")

    def render(self, check: bool = False) -> int:
        """Run the renderer without letting its logging into the test report."""
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return render_readme.render(check=check)

    def test_only_the_marked_block_is_replaced(self):
        self.assertEqual(self.render(check=False), 0)
        out = self.readme()
        self.assertIn("Intro paragraph that must survive.", out)
        self.assertIn("## Footer that must also survive", out)
        self.assertNotIn("stale content", out)
        self.assertIn("2.0.6", out)

    def test_badge_count_is_synced(self):
        self.render(check=False)
        self.assertIn("iOS-2%20versions", self.readme())
        self.assertNotIn("iOS-99%20versions", self.readme())

    def test_is_idempotent(self):
        self.render(check=False)
        once = self.readme()
        self.assertEqual(self.render(check=False), 0)
        self.assertEqual(self.readme(), once)

    def test_check_reports_stale_without_writing(self):
        before = self.readme()
        self.assertEqual(self.render(check=True), 1)
        self.assertEqual(self.readme(), before)

    def test_check_passes_once_rendered(self):
        self.render(check=False)
        self.assertEqual(self.render(check=True), 0)

    def test_missing_markers_refuses_to_touch_the_file(self):
        # Better to fail loudly than to guess where the block belongs.
        (self.dir / "README.md").write_text("# No markers here\n", encoding="utf-8")
        self.assertEqual(self.render(check=False), 2)
        self.assertEqual(self.readme(), "# No markers here\n")


# --------------------------------------------------------------------------
# sync_legacy_fields
# --------------------------------------------------------------------------

class LegacyMirror(unittest.TestCase):
    def test_newest_version_wins_on_build_not_just_semver(self):
        app = {"versions": [version("2.0.1", "15"), version("2.0.1", "16"),
                            version("2.0.0", "14")]}
        self.assertEqual(legacy.newest_version(app)["buildVersion"], "16")

    def test_double_digit_builds_sort_numerically(self):
        app = {"versions": [version("2.0.0", "9"), version("2.0.0", "21")]}
        self.assertEqual(legacy.newest_version(app)["buildVersion"], "21")

    def test_app_without_versions_has_no_newest(self):
        self.assertIsNone(legacy.newest_version({"versions": []}))

    def test_mirror_copies_the_newest_build_up(self):
        app = {"name": "Stremio", "versions": [version("2.0.6", "21",
                                                       localizedDescription="feat: real notes")]}
        changed = legacy.sync_app(app)
        self.assertIn("versionDescription", changed)
        self.assertEqual(app["version"], "2.0.6")
        self.assertEqual(app["versionDescription"], "feat: real notes")
        self.assertEqual(app["downloadURL"], app["versions"][0]["downloadURL"])

    def test_mirror_is_idempotent(self):
        app = {"name": "Stremio", "versions": [version("2.0.6", "21")]}
        legacy.sync_app(app)
        self.assertEqual(legacy.sync_app(app), [], "second run should change nothing")

    def test_screenshots_are_flattened_for_legacy_clients(self):
        # The modern field is device-keyed and may hold objects; the legacy
        # one is a plain URL list, so copying it across would be malformed.
        app = {"name": "Stremio", "versions": [version("2.0.6", "21")],
               "screenshots": {"iphone": ["https://cdn/a.jpg"],
                               "ipad": [{"imageURL": "https://cdn/b.jpg",
                                         "width": 2048, "height": 2732}]}}
        legacy.sync_app(app)
        self.assertEqual(app["screenshotURLs"], ["https://cdn/a.jpg", "https://cdn/b.jpg"])

    def test_flattening_a_plain_list_is_a_passthrough(self):
        self.assertEqual(legacy.flatten_screenshots(["https://cdn/a.jpg"]),
                         ["https://cdn/a.jpg"])

    def test_flattening_is_stable_across_runs(self):
        # Dict order must not make the bot rewrite the file on every run.
        shots = {"ipad": [{"imageURL": "https://cdn/b.jpg"}], "iphone": ["https://cdn/a.jpg"]}
        self.assertEqual(legacy.flatten_screenshots(shots),
                         legacy.flatten_screenshots(dict(reversed(list(shots.items())))))

    def test_flattening_ignores_junk(self):
        self.assertEqual(legacy.flatten_screenshots({"iphone": [42, None, {"nope": 1}]}), [])
        self.assertEqual(legacy.flatten_screenshots(None), [])

    def test_mirror_follows_a_newly_added_build(self):
        app = {"name": "Stremio", "versions": [version("2.0.5", "20")]}
        legacy.sync_app(app)
        app["versions"].insert(0, version("2.0.6", "21"))
        self.assertTrue(legacy.sync_app(app))
        self.assertEqual(app["version"], "2.0.6")


# --------------------------------------------------------------------------
# build_news — changelogs into an in-app feed
# --------------------------------------------------------------------------

from datetime import date, timedelta  # noqa: E402


class NewsFeed(unittest.TestCase):
    TODAY = date(2026, 7, 30)

    def src(self, versions):
        d = doc(versions)
        d["apps"][0]["iconURL"] = "https://cdn.example.com/icon.png"
        return d

    def build(self, versions, today=None):
        return build_news.build_items(self.src(versions), "iPhone & iPad",
                                      today=today or self.TODAY)

    def test_only_releases_with_a_real_changelog_appear(self):
        items = self.build([
            version("2.0.6", "21", localizedDescription="feat: real thing"),
            version("2.0.5", "20"),  # placeholder
        ])
        self.assertEqual([i["title"] for i in items], ["Stremio 2.0.6"])

    def test_identifiers_are_stable_across_runs(self):
        # An identifier that moves would make clients re-notify for old news.
        vs = [version("2.0.6", "21", localizedDescription="feat: x")]
        first = [i["identifier"] for i in self.build(vs)]
        later = [i["identifier"] for i in self.build(vs, today=self.TODAY + timedelta(days=90))]
        self.assertEqual(first, later)

    def test_at_most_one_item_notifies(self):
        items = self.build([
            version("2.0.6", "21", date="2026-07-29", localizedDescription="feat: a"),
            version("2.0.5", "20", date="2026-07-28", localizedDescription="feat: b"),
            version("2.0.4", "19", date="2026-07-27", localizedDescription="feat: c"),
        ])
        self.assertEqual(sum(1 for i in items if i["notify"]), 1)
        self.assertTrue(items[0]["notify"], "only the newest may notify")

    def test_a_stale_release_never_notifies(self):
        # Publishing the feed for the first time must not wake anyone about a
        # build they already have.
        items = self.build([version("2.0.6", "21", date="2026-06-01",
                                    localizedDescription="feat: old news")])
        self.assertFalse(items[0]["notify"])

    def test_feed_is_capped(self):
        vs = [version("2.0.%d" % i, str(i), localizedDescription="feat: %d" % i)
              for i in range(30)]
        self.assertLessEqual(len(self.build(vs)), build_news.MAX_ITEMS)

    def test_caption_is_the_first_line_and_bounded(self):
        items = self.build([version("2.0.6", "21",
                                    localizedDescription="feat: headline\n\nfix: detail")])
        self.assertEqual(items[0]["caption"], "feat: headline")
        long = self.build([version("2.0.6", "21", localizedDescription="x" * 500)])
        self.assertLessEqual(len(long[0]["caption"]), build_news.MAX_CAPTION)

    def test_item_links_back_to_the_app(self):
        items = self.build([version("2.0.6", "21", localizedDescription="feat: x")])
        self.assertEqual(items[0]["appID"], "com.stremio.pal")
        self.assertEqual(items[0]["imageURL"], "https://cdn.example.com/icon.png")

    def test_platforms_get_distinct_identifiers(self):
        vs = [version("2.0.6", "21", localizedDescription="feat: x")]
        ios = build_news.build_items(self.src(vs), "iPhone & iPad", today=self.TODAY)
        tv = build_news.build_items(self.src(vs), "Apple TV", today=self.TODAY)
        self.assertNotEqual(ios[0]["identifier"], tv[0]["identifier"])


# --------------------------------------------------------------------------
# fetch_release_notes — sanitising third-party text
# --------------------------------------------------------------------------

class Sanitising(unittest.TestCase):
    def test_keeps_changelog_line_structure(self):
        self.assertEqual(notes.sanitize("feat: a\nfix: b"), "feat: a\nfix: b")

    def test_normalises_windows_line_endings(self):
        self.assertEqual(notes.sanitize("feat: a\r\nfix: b"), "feat: a\nfix: b")

    def test_strips_control_characters(self):
        self.assertEqual(notes.sanitize("feat: a\x00\x07b"), "feat: ab")

    def test_collapses_runs_of_blank_lines(self):
        self.assertEqual(notes.sanitize("a\n\n\n\n\nb"), "a\n\nb")

    def test_caps_length(self):
        out = notes.sanitize("x" * 10000)
        self.assertLessEqual(len(out), notes.MAX_LEN + len("\n\n(truncated)"))
        self.assertTrue(out.endswith("(truncated)"))

    def test_empty_and_non_string_become_none(self):
        for bad in ("", "   \n\n ", None, 42, {"a": 1}):
            self.assertIsNone(notes.sanitize(bad), repr(bad))

    def test_placeholder_is_recognised(self):
        self.assertTrue(notes.is_placeholder("Stremio 2.0.4 (build 19)."))
        self.assertTrue(notes.is_placeholder("Stremio Lite 1.3.6 (build 7)."))
        self.assertTrue(notes.is_placeholder(""))
        self.assertTrue(notes.is_placeholder(None))

    def test_real_notes_are_not_mistaken_for_a_placeholder(self):
        self.assertFalse(notes.is_placeholder("feat: new desktop like UI for player"))
        self.assertFalse(notes.is_placeholder("fix: crash on launch\nfix: seek bar"))


class ArchiveRecovery(unittest.TestCase):
    """Precedence between the live source and Internet Archive captures."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self._orig = (notes.REPO, notes.SOURCES,
                      notes.fetch_upstream_notes, notes.fetch_archived_notes)
        notes.REPO = self.dir
        notes.SOURCES = ["stremio-ios.json"]

    def tearDown(self):
        (notes.REPO, notes.SOURCES,
         notes.fetch_upstream_notes, notes.fetch_archived_notes) = self._orig
        self._tmp.cleanup()

    def write(self, description):
        d = doc([version("2.0.2", "17", localizedDescription=description)])
        (self.dir / "stremio-ios.json").write_text(json.dumps(d), encoding="utf-8")

    def read_desc(self):
        d = json.loads((self.dir / "stremio-ios.json").read_text(encoding="utf-8"))
        return d["apps"][0]["versions"][0]["localizedDescription"]

    def run_main(self, *argv, live=None, archived=None):
        notes.fetch_upstream_notes = lambda: live or {}
        notes.fetch_archived_notes = lambda: archived or {}
        old = sys.argv
        sys.argv = ["fetch_release_notes.py", *argv]
        try:
            with contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                return notes.main()
        finally:
            sys.argv = old

    def test_archive_fills_a_placeholder(self):
        self.write("Stremio 2.0.2 (build 17).")
        self.run_main("--include-archive", archived={("2.0.2", "17"): "fix: a real thing"})
        self.assertEqual(self.read_desc(), "fix: a real thing")

    def test_archive_never_overwrites_a_note_we_already_have(self):
        # A stale capture must not clobber a better note.
        self.write("fix: the note we already captured")
        self.run_main("--include-archive", archived={("2.0.2", "17"): "fix: older wording"})
        self.assertEqual(self.read_desc(), "fix: the note we already captured")

    def test_live_upstream_still_refreshes_wording(self):
        self.write("fix: old wording")
        self.run_main(live={("2.0.2", "17"): "fix: corrected wording"})
        self.assertEqual(self.read_desc(), "fix: corrected wording")

    def test_live_wins_over_the_archive(self):
        self.write("Stremio 2.0.2 (build 17).")
        self.run_main("--include-archive",
                      live={("2.0.2", "17"): "from upstream"},
                      archived={("2.0.2", "17"): "from archive"})
        self.assertEqual(self.read_desc(), "from upstream")

    def test_archive_is_not_consulted_without_the_flag(self):
        self.write("Stremio 2.0.2 (build 17).")
        self.run_main(archived={("2.0.2", "17"): "fix: a real thing"})
        self.assertEqual(self.read_desc(), "Stremio 2.0.2 (build 17).")

    def test_placeholders_are_not_harvested_as_notes(self):
        src = doc([version("2.0.2", "17", localizedDescription="Stremio 2.0.2 (build 17).")])
        self.assertEqual(notes._notes_from_source(src), {})

    def test_junk_document_yields_nothing(self):
        for junk in (None, [], "nope", {"apps": "no"}):
            self.assertEqual(notes._notes_from_source(junk), {})


# --------------------------------------------------------------------------
# add_hashes
# --------------------------------------------------------------------------

class Hashes(unittest.TestCase):
    def test_valid_hash_recognised(self):
        self.assertTrue(add_hashes._has_valid_hash({"sha256": "a" * 64}))

    def test_bad_hashes_rejected(self):
        for bad in ("A" * 64, "abc", "", None, "g" * 64, "a" * 63):
            self.assertFalse(add_hashes._has_valid_hash({"sha256": bad}), repr(bad))
        self.assertFalse(add_hashes._has_valid_hash({}))

    def test_hash_is_inserted_right_after_size(self):
        # Purely for diff stability: the bot rewrites these files constantly.
        v = version("2.0.6", "21")
        add_hashes._set_sha256(v, "b" * 64)
        keys = list(v.keys())
        self.assertEqual(keys[keys.index("size") + 1], "sha256")

    def test_setting_a_hash_twice_does_not_duplicate_or_reorder(self):
        v = version("2.0.6", "21")
        add_hashes._set_sha256(v, "b" * 64)
        first = list(v.keys())
        add_hashes._set_sha256(v, "c" * 64)
        self.assertEqual(list(v.keys()), first)
        self.assertEqual(v["sha256"], "c" * 64)

    def test_newest_versions_are_hashed_first(self):
        sources = {"stremio-ios.json": doc([version("2.0.0", "11"), version("2.0.6", "21")])}
        missing = add_hashes._missing(sources)
        self.assertEqual(missing[0]["version"], "2.0.6")

    def test_already_hashed_versions_are_not_revisited(self):
        sources = {"stremio-ios.json": doc([version("2.0.6", "21", sha256="d" * 64),
                                            version("2.0.0", "11")])}
        missing = add_hashes._missing(sources)
        self.assertEqual([m["version"] for m in missing], ["2.0.0"])


class HashReverification(unittest.TestCase):
    """A hash that no longer matches the file is worse than no hash at all.

    Clients that verify sha256 refuse the download outright, so a stale hash
    is a self-inflicted outage. Nothing used to look at a hash again once it
    was written.
    """

    def _serve(self, length, status=200):
        def fake(url, *, method="GET", headers=None, timeout=15):
            return type("R", (), {"status": status,
                                  "headers": {"Content-Length": str(length)},
                                  "body": None})()
        add_hashes.http_request = fake

    def setUp(self):
        self._real = add_hashes.http_request

    def tearDown(self):
        add_hashes.http_request = self._real

    def _run(self, recorded, live, **kw):
        sources = {"stremio-ios.json": doc(
            [version("2.0.6", "21", sha256="d" * 64, size=recorded)])}
        self._serve(live)
        with contextlib.redirect_stdout(io.StringIO()):
            stale, changed = add_hashes._reverify(sources, **kw)
        return stale, changed, sources["stremio-ios.json"]["apps"][0]["versions"][0]

    def test_unchanged_file_keeps_its_hash(self):
        stale, changed, v = self._run(75942223, 75942223)
        self.assertEqual(stale, 0)
        self.assertEqual(changed, set())
        self.assertEqual(v["sha256"], "d" * 64)

    def test_replaced_file_loses_its_stale_hash(self):
        stale, changed, v = self._run(75942223, 80000000)
        self.assertEqual(stale, 1)
        self.assertEqual(changed, {"stremio-ios.json"})
        self.assertNotIn("sha256", v)

    def test_replaced_file_gets_the_corrected_size(self):
        # Hash and size must describe the same file, or the next backfill
        # would warn about a mismatch it had already been told about.
        _, _, v = self._run(75942223, 80000000)
        self.assertEqual(v["size"], 80000000)

    def test_a_dropped_hash_is_queued_for_the_backfill(self):
        # Dropping the hash is only half the fix; the backfill has to pick it
        # up, otherwise the version silently stays unhashed forever.
        _, _, v = self._run(75942223, 80000000)
        queued = add_hashes._missing({"stremio-ios.json": doc([v])})
        self.assertEqual([m["version"] for m in queued], ["2.0.6"])

    def test_dry_run_reports_without_touching_the_source(self):
        stale, _, v = self._run(75942223, 80000000, dry_run=True)
        self.assertEqual(stale, 1)
        self.assertEqual(v["sha256"], "d" * 64)
        self.assertEqual(v["size"], 75942223)

    def test_an_unreachable_ipa_is_not_treated_as_replaced(self):
        # prune_dead.py owns deciding what is gone; a 503 here means nothing.
        sources = {"stremio-ios.json": doc(
            [version("2.0.6", "21", sha256="d" * 64)])}
        self._serve(0, status=503)
        with contextlib.redirect_stdout(io.StringIO()):
            stale, changed = add_hashes._reverify(sources)
        self.assertEqual(stale, 0)
        self.assertEqual(changed, set())
        self.assertEqual(
            sources["stremio-ios.json"]["apps"][0]["versions"][0]["sha256"], "d" * 64)

    def test_versions_without_a_hash_are_left_alone(self):
        sources = {"stremio-ios.json": doc([version("2.0.6", "21")])}
        self._serve(999)
        with contextlib.redirect_stdout(io.StringIO()):
            stale, changed = add_hashes._reverify(sources)
        self.assertEqual((stale, changed), (0, set()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
