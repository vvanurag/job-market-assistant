import hashlib

from jobmarket import streaming


def record(
    title="Senior Data Engineer", location="Bengaluru, India", content="<p>Build Kafka &amp; dbt pipelines.</p>"
):
    return {
        "source_posting_id": "123",
        "company_name": "Acme",
        "job": {
            "id": 123,
            "title": title,
            "location": {"name": location},
            "content": content,
            "first_published": "2026-11-06T08:00:00Z",
            "absolute_url": "https://x/123",
        },
    }


def test_posting_key_matches_the_warehouse_formula():
    assert streaming.posting_key("greenhouse", "123") == hashlib.md5(b"greenhouse|123").hexdigest()


def test_provisional_document_applies_the_warehouse_rules():
    doc = streaming.provisional_document(record())
    assert doc["city"] == "Bengaluru" and doc["seniority"] == "senior"
    assert doc["skills"] == "Apache Kafka|dbt"
    assert doc["description_text"] == "Build Kafka & dbt pipelines."
    assert doc["document_hash"].startswith("provisional:")  # so the batch version always replaces it


def test_out_of_scope_postings_are_skipped():
    assert streaming.provisional_document(record(title="Account Executive")) is None
    assert streaming.provisional_document(record(location="Remote - Indiana, USA")) is None


def test_remote_india_and_work_mode():
    doc = streaming.provisional_document(record(location="Remote - India"))
    assert doc["city"] == "Remote (India)" and doc["work_mode"] == "remote" and doc["is_remote_india"]


def test_personal_data_is_removed_before_indexing():
    doc = streaming.provisional_document(record(content="Mail jane.doe@acme.com or call +91 98765 43210. Data role."))
    assert "jane.doe" not in doc["description_text"] and "98765" not in doc["description_text"]


def test_stream_records_land_in_bronze_in_collector_format(tmp_path):
    from jobmarket.settings import Settings

    settings = Settings(_env_file=None, bronze_root=tmp_path)
    event = {"detected_at": "2026-11-06T10:00:00+00:00", "record": record()}
    path = streaming.land_in_bronze(settings, event)
    assert path == tmp_path / "greenhouse" / "stream-2026-11-06" / "postings" / "123.json"
