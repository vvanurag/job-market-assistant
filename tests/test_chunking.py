from jobmarket.index.chunking import chunk_posting, is_heading, split_sections

DESCRIPTION = """We build data platforms for banks.
Responsibilities:
Design batch and streaming pipelines with Kafka and Spark.
Own data quality with dbt tests.
Requirements
5+ years of data engineering experience.
Strong SQL.
Equal Opportunity Employer
We do not discriminate on any basis."""


def test_headings_are_recognised():
    assert is_heading("Responsibilities:")
    assert is_heading("What you'll bring")
    assert not is_heading("Design batch and streaming pipelines with Kafka and Spark.")


def test_sections_split_at_headings_with_overview_first():
    names = [name for name, _ in split_sections(DESCRIPTION)]
    assert names == ["Overview", "Responsibilities", "Requirements", "Equal Opportunity Employer"]


def test_boilerplate_is_dropped_and_every_chunk_names_the_job():
    chunks = chunk_posting("Data Engineer", "Acme", "Hyderabad", DESCRIPTION)
    text = "\n".join(c.text for c in chunks)
    assert "discriminate" not in text
    assert "Kafka" in text and "5+ years" in text
    assert all(c.text.startswith("Data Engineer at Acme (Hyderabad)") for c in chunks)


def test_long_sections_split_within_limit_with_overlap():
    long = "Responsibilities:\n" + " ".join(f"Task number {i} is important." for i in range(300))
    chunks = chunk_posting("T", "C", "Bengaluru", long, max_chars=600, overlap_chars=100)
    assert len(chunks) > 5
    assert all(len(c.text) <= 600 for c in chunks)
    first_body, second_body = (c.text.split("\n", 2)[2] for c in chunks[:2])
    assert first_body[-40:].split()[-1] in second_body  # overlap repeats the end of the previous chunk


def test_unbroken_text_is_still_split():
    chunks = chunk_posting("T", "C", "Bengaluru", "x" * 5000, max_chars=600)
    assert all(len(c.text) <= 600 for c in chunks)


def test_empty_description_still_gives_one_chunk():
    assert [c.text for c in chunk_posting("T", "C", "Hyderabad", "")] == ["T at C (Hyderabad)"]
