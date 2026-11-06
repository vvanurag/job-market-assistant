import json

import httpx
import pytest

from jobmarket.ingestion import greenhouse
from jobmarket.ingestion.greenhouse import Board, collect, in_target_city


def job(job_id, title, location, offices=()):
    return {
        "id": job_id,
        "title": title,
        "location": {"name": location},
        "offices": [{"name": o, "location": None} for o in offices],
        "content": "&lt;p&gt;Build pipelines&lt;/p&gt;",
        "absolute_url": f"https://example.com/jobs/{job_id}",
        "updated_at": "2026-11-01T10:00:00-04:00",
    }


BOARDS = {
    "acme": [
        job(1, "Data Engineer", "Bengaluru, India"),
        job(2, "Account Executive", "London"),
        job(3, "ML Engineer", "Remote", offices=["Hyderabad"]),
    ],
    "globex": [job(10, "Analytics Engineer", "Bangalore")],
}


def transport(fail_once: set[str] = frozenset(), missing: set[str] = frozenset()):
    calls: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        token = request.url.path.split("/")[3]
        calls[token] = calls.get(token, 0) + 1
        assert request.url.params["content"] == "true"
        if token in missing:
            return httpx.Response(404)
        if token in fail_once and calls[token] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"jobs": BOARDS.get(token, [])})

    return httpx.MockTransport(handler), calls


def run(tmp_path, boards, **kw):
    mock, calls = transport(**kw)
    results = collect(tmp_path, "b1", boards, client=httpx.Client(transport=mock), sleep=lambda s: None)
    return results, calls, tmp_path / "greenhouse" / "b1"


def test_keeps_only_jobs_in_target_cities(tmp_path):
    results, _, batch = run(tmp_path, [Board("acme", "Acme")])
    assert (results[0].jobs_total, results[0].jobs_kept) == (3, 2)
    assert sorted(p.stem for p in (batch / "postings").glob("*.json")) == ["1", "3"]


def test_office_location_counts_as_target_city():
    assert in_target_city(job(3, "x", "Remote", offices=["Hyderabad"]), greenhouse.city_pattern())
    assert not in_target_city(job(4, "x", "Remote", offices=["Berlin"]), greenhouse.city_pattern())


def test_record_keeps_raw_job_and_adds_metadata(tmp_path):
    _, _, batch = run(tmp_path, [Board("acme", "Acme")])
    record = json.loads((batch / "postings" / "1.json").read_text())
    assert record["source_posting_id"] == "1"
    assert (record["board_token"], record["company_name"]) == ("acme", "Acme")
    assert record["job"] == BOARDS["acme"][0]
    assert "collected_at" in record


def test_failed_board_is_recorded_and_others_continue(tmp_path):
    results, _, batch = run(tmp_path, [Board("missing", "Missing Co"), Board("globex", "Globex")], missing={"missing"})
    by_token = {r.token: r for r in results}
    assert by_token["missing"].status == "failed"
    assert "404" in by_token["missing"].error
    assert by_token["globex"].jobs_kept == 1
    summary = json.loads((batch / "_run.json").read_text())
    assert [b["status"] for b in summary["boards"]] == ["failed", "ok"]


def test_transient_error_is_retried(tmp_path):
    results, calls, _ = run(tmp_path, [Board("acme", "Acme")], fail_once={"acme"})
    assert results[0].status == "ok"
    assert calls["acme"] == 2


def test_rerunning_a_batch_does_not_duplicate_files(tmp_path):
    run(tmp_path, [Board("acme", "Acme")])
    _, _, batch = run(tmp_path, [Board("acme", "Acme")])
    assert len(list((batch / "postings").glob("*.json"))) == 2
    assert not list(batch.rglob("*.tmp"))


@pytest.mark.parametrize("location", ["Bengaluru, Karnataka, India", "Bangalore", "Hyderabad, Telangana", "Gachibowli"])
def test_city_aliases_match_common_spellings(location):
    assert greenhouse.city_pattern().search(location)


@pytest.mark.parametrize("location", ["Remote - India", "Remote, India, APAC", "India (Remote)"])
def test_remote_roles_open_to_india_are_kept(location):
    assert greenhouse.city_pattern().search(location)


@pytest.mark.parametrize("location", ["Remote - Indiana, USA", "Remote - Berlin", "Indianapolis"])
def test_aliases_match_whole_words_only(location):
    assert not greenhouse.city_pattern().search(location)
