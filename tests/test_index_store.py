from datetime import date

from jobmarket.index.store import Filters, schema_for, vector_literal


def test_schema_per_embedding_model():
    assert schema_for("ollama:nomic-embed-text") == "idx_nomic_embed_text"
    assert schema_for("gemini:gemini-embedding-001") == "idx_gemini_embedding_001"


def test_default_filter_returns_open_postings_only():
    where, params = Filters().where()
    assert where == "p.status = 'open'" and params == []


def test_filters_are_parameterised_never_interpolated():
    where, params = Filters(
        cities=["Hyderabad"], skills_all=["dbt"], company="O'Brien; drop table x", posted_since=date(2026, 1, 1)
    ).where()
    assert "O'Brien" not in where and "drop" not in where
    assert params == [["Hyderabad"], ["dbt"], "%O'Brien; drop table x%", date(2026, 1, 1)]


def test_vector_literal():
    assert vector_literal([0.5, -1.0, 1e-9]) == "[0.5,-1,1e-09]"
