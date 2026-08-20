"""Startup materialisation and reuse tests for the SQLite paper index."""

from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path

from papervault.services.papers import PaperRepository


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def _paper(title: str, *, year: int = 2026) -> dict:
    return {
        "conf": f"ICLR {year}",
        "paper_name": title,
        "paper_authors": ["Alice Adams"],
        "paper_url": f"https://example.org/{title.lower().replace(' ', '-')}",
        "paper_abstract": f"An abstract for {title}.",
        "paper_code": None,
    }


def test_first_load_materialises_versioned_sqlite_index(tmp_path: Path):
    cache = tmp_path / "cache.jsonl.gz"
    _write_rows(cache, [_paper("First Paper"), _paper("Second Paper")])

    repo = PaperRepository(cache_path=cache, refresh_on_load=False)
    repo.ensure_loaded()

    assert repo.database_path == tmp_path / "papers.sqlite3"
    assert repo.database_path.is_file()
    assert repo.paper_count() == 2
    with sqlite3.connect(repo.database_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"papers", "paper_fts", "metadata"}.issubset(names)


def test_unchanged_cache_reuses_existing_database(tmp_path: Path, monkeypatch):
    cache = tmp_path / "cache.jsonl.gz"
    _write_rows(cache, [_paper("Stable Paper")])
    first = PaperRepository(cache_path=cache, refresh_on_load=False)
    first.ensure_loaded()
    original_mtime = first.database_path.stat().st_mtime_ns

    second = PaperRepository(cache_path=cache, refresh_on_load=False)

    def fail_build(*_args, **_kwargs):
        raise AssertionError("unchanged cache should not rebuild SQLite")

    monkeypatch.setattr(second, "_build_database", fail_build)
    second.ensure_loaded()

    assert second.paper_count() == 1
    assert second.database_path.stat().st_mtime_ns == original_mtime


def test_changed_cache_rebuilds_database(tmp_path: Path):
    cache = tmp_path / "cache.jsonl.gz"
    _write_rows(cache, [_paper("Original Paper")])
    first = PaperRepository(cache_path=cache, refresh_on_load=False)
    first.ensure_loaded()
    original_inode = first.database_path.stat().st_ino

    _write_rows(cache, [_paper("Original Paper"), _paper("New Paper", year=2025)])
    second = PaperRepository(cache_path=cache, refresh_on_load=False)
    second.ensure_loaded()

    assert second.paper_count() == 2
    assert second.database_path.stat().st_ino != original_inode
    assert {paper.title for paper in second.all_papers()} == {
        "Original Paper",
        "New Paper",
    }


def test_missing_cache_builds_valid_empty_database(tmp_path: Path):
    cache = tmp_path / "missing" / "cache.jsonl.gz"
    repo = PaperRepository(cache_path=cache, refresh_on_load=False)

    repo.ensure_loaded()

    assert repo.paper_count() == 0
    assert repo.conference_count() == 0
