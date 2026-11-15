"""Search query parsing, aliases and JSON storage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alfred_plex import filters
from alfred_plex.store import Alias, AliasEntry, ItemsFile, Store, read_json, write_json

ALIAS = Alias([AliasEntry("lt", "libtype"), AliasEntry("af", "advancedFilters"), AliasEntry("ge", "genre"),
               AliasEntry("sv", "server"), AliasEntry("sc", "section"), AliasEntry("wa", "watchlist"),
               AliasEntry("so", "sort"), AliasEntry("tl", "title"), AliasEntry("de", "decade")], enabled=True)


class TestParse:
    def test_plain_text(self):
        query = filters.parse("matrix", ALIAS)
        assert query.text == "matrix" and query.mediatype is None and not query.is_filter

    def test_media_type_suffix(self):
        query = filters.parse("matrix/movie", ALIAS)
        assert (query.text, query.mediatype) == ("matrix", "movie")

    def test_slash_in_title_is_not_a_media_type(self):
        # v2 searched "AC" with the media type "DC".
        assert filters.parse("AC/DC", ALIAS).text == "AC/DC"

    def test_filters_with_aliases_and_long_names(self):
        query = filters.parse("lt=movie/genre=12/de=1980", ALIAS)
        assert query.filters == {"libtype": "movie", "genre": 12, "decade": 1980}
        assert query.libtype == "movie"

    def test_advanced_filters(self):
        query = filters.parse("lt=episode/af={'show.title': 'one piece', 'episode.index': '1'}", ALIAS)
        assert query.advanced == {"show.title": "one piece", "episode.index": "1"}
        assert query.search_kwargs(10) == {"libtype": "episode", "maxresults": 10, "filters": query.advanced}

    def test_slash_inside_a_value_is_kept(self):
        query = filters.parse("lt=artist/af={'artist.title': 'AC/DC'}", ALIAS)
        assert query.advanced == {"artist.title": "AC/DC"}

    def test_workflow_keys(self):
        query = filters.parse("lt=movie/sv=Home, NAS/sc=Movies/wa=1", ALIAS)
        assert query.servers == {"home", "nas"}
        assert query.sections == {"movies"}
        assert query.watchlist == 1
        assert query.filters == {"libtype": "movie"}
        assert query.accepts_server("HOME") and not query.accepts_server("other")

    def test_sections_are_matched_with_the_libtype(self):
        query = filters.parse("lt=episode", ALIAS)
        assert query.accepts_section("TV", "show")
        assert not query.accepts_section("Movies", "movie")
        assert filters.parse("tl=x", ALIAS).accepts_section("Movies", "movie")

    @pytest.mark.parametrize("text", ["zz=1", "lt=movie/af=[1, 2]", "lt=movie/af={oops", "=movie"])
    def test_invalid_filters(self, text):
        with pytest.raises(filters.FilterError):
            filters.parse(text, ALIAS)

    def test_advanced_filters_are_never_evaluated(self):
        with pytest.raises(filters.FilterError):
            filters.parse("lt=movie/af=__import__('os').getcwd()", ALIAS)

    def test_default_view(self):
        query = filters.default_view({"sort": "addedAt:desc", "server": "Home", "watchlist": True})
        assert query.filters == {"sort": "addedAt:desc"}
        assert query.servers == {"home"} and query.watchlist == 1

    def test_to_text_respects_alias_mode(self):
        pairs = [("libtype", "movie"), ("genre", 12)]
        assert filters.to_text(ALIAS, pairs) == "lt=movie/ge=12"
        assert filters.to_text(Alias(ALIAS.entries, enabled=False), pairs) == "libtype=movie/genre=12"


class TestAlias:
    def test_resolve_accepts_both_forms(self):
        assert ALIAS.resolve("lt") == "libtype"
        assert ALIAS.resolve("libtype") == "libtype"
        assert ALIAS.resolve(" lt ") == "libtype"
        assert ALIAS.resolve("nope") is None

    def test_display(self):
        assert ALIAS.display("libtype") == "lt"
        assert ALIAS.display("unknownKey") == "unknownKey"
        assert Alias(ALIAS.entries, enabled=False).display("libtype") == "libtype"


class TestStore:
    def test_atomic_write_and_read(self, tmp_path: Path):
        path = tmp_path / "a" / "file.json"
        write_json(path, {"items": [1]})
        assert read_json(path, None) == {"items": [1]}
        assert not list(path.parent.glob(".*.tmp"))

    def test_read_corrupted_file(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("{oops")
        assert read_json(path, {"items": []}) == {"items": []}

    def test_items_file_upsert_remove(self, tmp_path: Path):
        file = ItemsFile(tmp_path / "servers.json", "machineIdentifier")
        assert file.upsert({"machineIdentifier": "a", "title": "A"}) is False
        assert file.upsert({"machineIdentifier": "a", "title": "A2"}) is True
        file.upsert({"machineIdentifier": "b", "account_uuid": "u"})
        file.save()
        reloaded = ItemsFile(tmp_path / "servers.json", "machineIdentifier")
        assert reloaded.get("a")["title"] == "A2"
        assert reloaded.remove("u", field="account_uuid")[0]["machineIdentifier"] == "b"
        assert [i["machineIdentifier"] for i in reloaded.items] == ["a"]

    def test_v2_files_are_still_readable(self, ctx, saved):
        assert ctx.store.accounts.items[0]["uuid"] == "acc-uuid-1"
        assert ctx.store.server("mid-home")["friendlyName"] == "Home Server"

    def test_presets_are_seeded(self, ctx):
        titles = [p["title"] for p in ctx.store.presets.items]
        assert "80's French Movies" in titles
        assert (ctx.settings.data_dir / "presets.json").exists()

    def test_alias_file_is_created_and_merged(self, ctx):
        # a user file from an older version, with a custom alias and a missing key
        ctx.store.alias_path.parent.mkdir(parents=True, exist_ok=True)
        ctx.store.alias_path.write_text(json.dumps([{"short_key": "type", "long_key": "libtype"}]))
        store = Store(ctx.settings)
        assert store.alias.resolve("type") == "libtype"  # custom alias kept
        assert store.alias.resolve("af") == "advancedFilters"  # new default merged
        saved = json.loads(store.alias_path.read_text())
        assert {"short_key": "type", "long_key": "libtype"} in saved
        assert not any(e["short_key"] == "lt" for e in saved)  # no duplicate for libtype

    def test_reset_alias(self, ctx):
        ctx.store.alias_path.parent.mkdir(parents=True, exist_ok=True)
        ctx.store.alias_path.write_text("[]")
        ctx.store.reset_alias()
        assert ctx.store.alias.resolve("lt") == "libtype"


def test_a_slash_without_key_stays_in_the_value():
    # "/" only starts a new filter when followed by "name=": titles with "/" are safe.
    assert filters.parse("tl=AC/DC", ALIAS).filters == {"title": "AC/DC"}
