import json
from pathlib import Path

import duckdb
import pytest

from jobmarket.bronze.loader import discover_batches, load_all


def write_posting(root: Path, source: str, batch: str, name: str, content: str) -> None:
    folder = root / source / batch / "postings"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(content)


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "bronze"
    db = tmp_path / "dev.duckdb"
    write_posting(root, "demo", "b1", "100", json.dumps({"job_id": "100", "title": "Data Engineer"}))
    write_posting(root, "demo", "b1", "101", json.dumps({"job_id": "101", "title": "ML Engineer"}))
    write_posting(root, "demo", "b1", "bad", "{not valid json")
    write_posting(root, "demo", "b1", "noid", json.dumps({"title": "No identifier"}))
    return root, db


def rows(db: Path, sql: str):
    with duckdb.connect(str(db)) as con:
        return con.execute(sql).fetchall()


def test_discover_batches_finds_source_and_batch(env):
    root, _ = env
    write_posting(root, "other", "b9", "1", json.dumps({"id": "1"}))
    found = {(b.source_id, b.batch_id) for b in discover_batches(root)}
    assert found == {("demo", "b1"), ("other", "b9")}
    assert [b.source_id for b in discover_batches(root, source_id="other")] == ["other"]


def test_first_load_inserts_valid_rows_and_counts_invalid(env):
    root, db = env
    (result,) = load_all(db, root)
    assert (result.files_seen, result.rows_inserted, result.rows_invalid) == (4, 2, 2)
    assert result.status == "succeeded_with_warnings"
    assert rows(db, "select source_posting_id from bronze.raw_postings order by 1") == [("100",), ("101",)]


def test_payload_is_stored_unchanged_with_metadata(env):
    root, db = env
    load_all(db, root)
    (payload, file_name, record_hash, source, batch) = rows(
        db,
        "select payload::varchar, file_name, record_hash, source_id, batch_id "
        "from bronze.raw_postings where source_posting_id = '100'",
    )[0]
    assert json.loads(payload) == {"job_id": "100", "title": "Data Engineer"}
    assert file_name == "demo/b1/postings/100.json"
    assert len(record_hash) == 64
    assert (source, batch) == ("demo", "b1")


def test_reloading_the_same_batch_adds_nothing(env):
    root, db = env
    load_all(db, root)
    (again,) = load_all(db, root)
    assert (again.rows_inserted, again.rows_unchanged, again.rows_conflicting) == (0, 2, 0)
    assert rows(db, "select count(*) from bronze.raw_postings") == [(2,)]


def test_changed_content_is_reported_and_original_kept(env):
    root, db = env
    load_all(db, root)
    write_posting(root, "demo", "b1", "100", json.dumps({"job_id": "100", "title": "CHANGED"}))
    (again,) = load_all(db, root)
    assert (again.rows_inserted, again.rows_conflicting) == (0, 1)
    assert rows(db, "select payload->>'title' from bronze.raw_postings where source_posting_id = '100'") == [
        ("Data Engineer",)
    ]


def test_new_batch_loads_alongside_existing(env):
    root, db = env
    load_all(db, root)
    write_posting(root, "demo", "b2", "100", json.dumps({"job_id": "100", "title": "Data Engineer"}))
    results = {r.batch_id: r for r in load_all(db, root)}
    assert results["b2"].rows_inserted == 1
    assert rows(db, "select batch_id, count(*) from bronze.raw_postings group by 1 order by 1") == [
        ("b1", 2),
        ("b2", 1),
    ]


def test_every_load_is_recorded_in_load_runs(env):
    root, db = env
    load_all(db, root)
    load_all(db, root)
    runs = rows(db, "select rows_inserted, rows_unchanged, status from bronze.load_runs order by started_at")
    assert runs == [(2, 0, "succeeded_with_warnings"), (0, 2, "succeeded_with_warnings")]


def test_empty_batch_is_recorded_not_failed(tmp_path):
    root = tmp_path / "bronze"
    (root / "demo" / "b1" / "postings").mkdir(parents=True)
    (result,) = load_all(tmp_path / "dev.duckdb", root)
    assert (result.files_seen, result.status) == (0, "empty")
