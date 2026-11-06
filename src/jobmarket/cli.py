"""Command-line entry point: ``jobmarket <command>``."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import typer

from jobmarket import __version__
from jobmarket.checks import Status, run_all
from jobmarket.settings import get_settings

app = typer.Typer(help="Job Market Assistant command-line tools.", no_args_is_help=True)

_COLOURS = {
    Status.PASS: typer.colors.GREEN,
    Status.WARN: typer.colors.YELLOW,
    Status.FAIL: typer.colors.RED,
    Status.SKIP: typer.colors.BRIGHT_BLACK,
}


@app.callback()
def main() -> None:
    """Job Market Assistant command-line tools."""


@app.command()
def doctor(
    deep: bool = typer.Option(False, "--deep", help="Also call each model and API to prove it works."),
) -> None:
    """Check that the local environment meets the Phase 0 exit criteria."""
    results = run_all(get_settings(), deep=deep)
    width = max(len(r.name) for r in results)
    for r in results:
        badge = typer.style(f"{r.status.value:<4}", fg=_COLOURS[r.status], bold=True)
        typer.echo(f"  {badge}  {r.name:<{width}}  {r.detail}")

    failed = [r for r in results if r.status is Status.FAIL]
    warned = [r for r in results if r.status is Status.WARN]
    typer.echo(f"\n{len(results) - len(failed) - len(warned)} passed, {len(warned)} warnings, {len(failed)} failed")
    if failed:
        raise typer.Exit(code=1)


@app.command()
def compare() -> None:
    """Check that Silver and Gold are identical in DuckDB and Snowflake (NFR-24)."""
    from jobmarket.portability import compare as compare_engines
    from jobmarket.warehouse import duckdb_connect, snowflake_connect

    settings = get_settings()
    with duckdb_connect(settings, read_only=True) as local, snowflake_connect(settings) as cloud, cloud.cursor() as cur:
        results = compare_engines(local, cur)

    typer.echo(f"{'table':<28} {'DuckDB':>8} {'Snowflake':>10}  result")
    for r in results:
        verdict = (
            typer.style("identical", fg=typer.colors.GREEN)
            if r.identical
            else typer.style(f"DIFFERENT ({r.only_in_a} only in DuckDB, {r.only_in_b} only in Snowflake)", fg="red")
        )
        typer.echo(f"{r.table:<28} {r.rows_a:>8} {r.rows_b:>10}  {verdict}")
        for example in r.examples:
            typer.echo(f"    {example}")
    if not all(r.identical for r in results):
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


collect_app = typer.Typer(help="Collect postings from approved sources into Bronze files.", no_args_is_help=True)
app.add_typer(collect_app, name="collect")


@collect_app.command("greenhouse")
def collect_greenhouse(
    batch: str = typer.Option(None, help="Batch ID; defaults to today's UTC date."),
) -> None:
    """Fetch jobs in target cities from every board in config/greenhouse_boards.csv."""
    from datetime import datetime

    from jobmarket.ingestion.greenhouse import collect, load_boards

    batch_id = batch or datetime.now(UTC).strftime("%Y-%m-%d")
    boards = load_boards()
    typer.echo(f"Collecting {len(boards)} Greenhouse boards into batch {batch_id} ...")
    results = collect(get_settings().bronze_root, batch_id, boards)
    for r in results:
        mark = typer.style("ok    ", fg=typer.colors.GREEN) if r.status == "ok" else typer.style("FAILED", fg="red")
        typer.echo(f"  {mark} {r.company_name:<18} {r.jobs_kept:>4} kept of {r.jobs_total:>4}  {r.error or ''}")
    kept = sum(r.jobs_kept for r in results)
    failed = sum(r.status == "failed" for r in results)
    typer.echo(f"\n{kept} jobs saved from {len(results) - failed} boards; {failed} boards failed.")
    if failed == len(results):
        raise typer.Exit(code=1)


bronze_app = typer.Typer(help="Bronze layer: load and inspect raw records.", no_args_is_help=True)
app.add_typer(bronze_app, name="bronze")


@bronze_app.command("load")
def bronze_load(
    source: str = typer.Option(None, help="Only load this source."),
    batch: str = typer.Option(None, help="Only load this batch."),
    target: str = typer.Option("duckdb", help="Warehouse to load: duckdb or snowflake."),
) -> None:
    """Load raw posting files into bronze.raw_postings (safe to re-run)."""
    settings = get_settings()
    if target == "duckdb":
        from jobmarket.bronze.loader import load_all

        results = load_all(settings.duckdb_path, settings.bronze_root, source, batch)
    elif target == "snowflake":
        from jobmarket.bronze.snowflake_loader import load_all as load_all_snowflake

        results = load_all_snowflake(settings, settings.bronze_root, source, batch)
    else:
        raise typer.BadParameter("target must be duckdb or snowflake")
    if not results:
        typer.echo(f"No batches found under {settings.bronze_root}")
        raise typer.Exit(code=1)

    header = f"{'source':<20} {'batch':<12} {'files':>6} {'new':>6} {'same':>6} {'changed':>8} {'invalid':>8}"
    typer.echo(f"{header}  status")
    for r in results:
        colour = {"succeeded": typer.colors.GREEN, "failed": typer.colors.RED}.get(r.status, typer.colors.YELLOW)
        typer.echo(
            f"{r.source_id:<20} {r.batch_id:<12} {r.files_seen:>6} {r.rows_inserted:>6} {r.rows_unchanged:>6} "
            f"{r.rows_conflicting:>8} {r.rows_invalid:>8}  " + typer.style(r.status, fg=colour)
        )
        if r.error:
            typer.echo(f"  error: {r.error}")
    if any(r.status == "failed" for r in results):
        raise typer.Exit(code=1)


@bronze_app.command("status")
def bronze_status() -> None:
    """Show how many postings Bronze holds per source and batch."""
    from jobmarket.bronze.loader import bronze_summary

    rows = bronze_summary(get_settings().duckdb_path)
    if not rows:
        typer.echo("Bronze is empty. Run: jobmarket bronze load")
        return
    typer.echo(f"{'source':<20} {'batch':<12} {'postings':>9}  last loaded (UTC)")
    for source_id, batch_id, postings, last_loaded in rows:
        typer.echo(f"{source_id:<20} {batch_id:<12} {postings:>9}  {last_loaded.astimezone(UTC):%Y-%m-%d %H:%M:%S}")
    typer.echo(f"{'total':<33} {sum(r[2] for r in rows):>9}")


if __name__ == "__main__":
    app()


index_app = typer.Typer(help="Retrieval index: build it from Gold and search it.", no_args_is_help=True)
app.add_typer(index_app, name="index")


@index_app.command("build")
def index_build(
    embedding_model: str = typer.Option(None, help="e.g. ollama:nomic-embed-text; defaults to EMBEDDING_MODEL."),
    limit: int = typer.Option(None, help="Index only the first N jobs (for quick tests)."),
) -> None:
    """Embed new or changed jobs and refresh the rest (FR-IDX-04)."""
    from jobmarket.index.build import build_index
    from jobmarket.llm import get_embedder

    settings = get_settings()
    embedder = get_embedder(embedding_model, settings)
    typer.echo(f"Building index for {embedder.name} from {settings.serving_warehouse} Gold ...")
    r = build_index(settings, embedder, limit=limit, progress=typer.echo)
    typer.echo(
        f"Build {r.build_id} ({r.schema}): {r.postings_in_gold} jobs in Gold; {r.embedded} embedded "
        f"({r.chunks_written} chunks), {r.updated} refreshed, {r.removed} removed in {r.seconds:.0f}s."
    )


@index_app.command("search")
def index_search(
    query: str,
    city: Annotated[
        list[str] | None, typer.Option(help="Hyderabad, Bengaluru or 'Remote (India)'; repeatable.")
    ] = None,
    work_mode: Annotated[list[str] | None, typer.Option(help="remote, hybrid or on-site; repeatable.")] = None,
    skill: Annotated[list[str] | None, typer.Option(help="Skill that must be present, e.g. dbt; repeatable.")] = None,
    company: str = typer.Option(None),
    mode: str = typer.Option("hybrid", help="hybrid, vector or keyword."),
    limit: int = typer.Option(5),
    embedding_model: str = typer.Option(None),
) -> None:
    """Search the index from the terminal."""
    from jobmarket.index import store
    from jobmarket.llm import get_embedder

    settings = get_settings()
    embedder = get_embedder(embedding_model, settings)
    filters = store.Filters(cities=city or [], work_modes=work_mode or [], skills_all=skill or [], company=company)
    with store.connect(settings.vectordb_dsn.get_secret_value()) as con:
        hits = store.search(
            con, store.schema_for(embedder.name), query, embedder.embed_query(query), filters, limit, mode
        )
    for h in hits:
        snippet = " ".join(h.text.split("\n", 2)[-1].split())[:160]
        typer.echo(
            f"{h.score:.4f}  {h.title} — {h.company_name} ({h.city}, {h.work_mode})\n        [{h.section}] {snippet}"
        )


eval_app = typer.Typer(help="Evaluation: run the evaluation set and compare runs.", no_args_is_help=True)
app.add_typer(eval_app, name="eval")


@eval_app.command("run")
def eval_run(
    llm: str = typer.Option(None, help="groq, gemini or ollama; defaults to LLM_PROVIDER."),
    model: str = typer.Option(None, help="Model name for that provider."),
    embedding: str = typer.Option(None, help="Embedding model, e.g. ollama:nomic-embed-text."),
    judge: str = typer.Option("gemini", help="Provider of the LLM judge, or 'none'."),
    run_id: str = typer.Option(None, help="Resume an interrupted run by its id."),
    only: Annotated[list[str] | None, typer.Option(help="Only these question ids; repeatable.")] = None,
    pace: float = typer.Option(0, help="Seconds to wait between questions, to stay under free-tier quotas."),
) -> None:
    """Score routing, analytics, retrieval and answers; save eval/results/<run_id>.json."""
    from jobmarket.evaluation.runner import run
    from jobmarket.llm import get_embedder, get_llm

    settings = get_settings()
    judge_llm = None if judge == "none" else get_llm(judge, settings=settings)
    result = run(
        settings,
        get_llm(llm, model, settings),
        get_embedder(embedding, settings),
        judge_llm,
        run_id,
        only,
        typer.echo,
        pace,
    )
    typer.echo(f"\nRun {result['run_id']}")
    for k, v in result["summary"].items():
        typer.echo(f"  {k:24} {v}")


@eval_app.command("experiment")
def eval_experiment(
    baseline: str = typer.Argument(..., help="Run id of a baseline evaluation, for the router's queries and filters."),
    rebuild: bool = typer.Option(False, help="Rebuild index A (all postings) first."),
) -> None:
    """Data-quality experiment A-E: what each data engineering step adds to retrieval."""
    from jobmarket.evaluation.experiment import build_all_postings_index, run_experiment
    from jobmarket.evaluation.runner import RESULTS_DIR
    from jobmarket.llm import get_embedder

    settings = get_settings()
    embedder = get_embedder(settings=settings)
    if rebuild:
        r = build_all_postings_index(settings, embedder, typer.echo)
        typer.echo(f"Index A: {r.postings_in_gold} postings, {r.chunks_written} chunks embedded")
    result = run_experiment(settings, embedder, RESULTS_DIR / f"{baseline}.json")
    typer.echo(f"{'run':4} {'recall@5':>9} {'MRR':>6} {'dup@5':>6} {'stale@5':>8} {'recall@5 (filtered qs)':>23}")
    for name, s in result["summary"].items():
        typer.echo(
            f"{name:4} {s['recall_at_5']:>9} {s['mrr']:>6} {s['duplicate_at_5']:>6} {s['stale_at_5']:>8} "
            f"{s['recall_at_5_filtered_questions']:>23}"
        )


ops_app = typer.Typer(help="Operations: freshness checks, alerts, run records.", no_args_is_help=True)
app.add_typer(ops_app, name="ops")


@ops_app.command("freshness")
def ops_freshness() -> None:
    """Fail (exit 1) when a daily source has no load in the last 26 hours (NFR-01)."""
    from jobmarket.ops import alert, freshness

    settings = get_settings()
    stale = []
    for f in freshness(settings):
        typer.echo(
            f"{f.source_id:12} last load {f.last_loaded_at}  age {f.age_hours} h  {'fresh' if f.fresh else 'STALE'}"
        )
        if not f.fresh:
            stale.append(f"{f.source_id} ({f.age_hours} h)")
    if stale:
        alert(settings, "freshness", "Stale sources: " + ", ".join(stale))
        raise typer.Exit(1)


@ops_app.command("alert")
def ops_alert(message: str, kind: str = typer.Option("task_failed")) -> None:
    """Record an alert and send it to ALERT_WEBHOOK_URL if set (FR-ORC-04)."""
    from jobmarket.ops import alert

    typer.echo("delivered" if alert(get_settings(), kind, message) else "recorded (no webhook, or delivery failed)")


@ops_app.command("record-run")
def ops_record_run(run_id: str) -> None:
    """Store per-source counts, durations and errors for one pipeline run (FR-OBS-01)."""
    import json

    from jobmarket.ops import record_run

    typer.echo(json.dumps(record_run(get_settings(), run_id), indent=1, default=str))


stream_app = typer.Typer(
    help="Streaming path: publish new postings and index them within minutes.", no_args_is_help=True
)
app.add_typer(stream_app, name="stream")


@stream_app.command("produce")
def stream_produce(
    interval: int = typer.Option(900, help="Seconds between polls."),
    once: bool = typer.Option(False, help="Poll once and exit."),
) -> None:
    """Poll sources and publish newly detected postings to Kafka (FR-STR-01)."""
    import time as _time

    from confluent_kafka import Producer

    from jobmarket.streaming import TOPIC, produce_once

    settings = get_settings()
    producer = Producer({"bootstrap.servers": settings.kafka_bootstrap, "enable.idempotence": True})
    state = settings.bronze_root.parent / "stream" / "published_ids.json"
    while True:
        r = produce_once(settings, producer, state)
        typer.echo(
            f"{datetime.now(UTC):%H:%M:%S} polled {r.boards} boards: "
            f"{r.seen} jobs in scope, {r.published} new -> {TOPIC}"
        )
        if once:
            break
        _time.sleep(interval)


@stream_app.command("consume")
def stream_consume(
    max_events: int = typer.Option(None, help="Stop after this many events (for tests)."),
    idle_exit: int = typer.Option(None, help="Exit after this many seconds without events."),
) -> None:
    """Land streamed postings in Bronze and the index; commit after each (FR-STR-02)."""
    import json as _json
    import time as _time

    from confluent_kafka import Consumer

    from jobmarket.llm import get_embedder
    from jobmarket.streaming import TOPIC, handle_event

    settings = get_settings()
    embedder = get_embedder(settings=settings)
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap,
            "group.id": "jobmarket-indexer",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,  # commit only after the event is fully processed
        }
    )
    consumer.subscribe([TOPIC])
    handled, last_event = 0, _time.monotonic()
    try:
        while max_events is None or handled < max_events:
            msg = consumer.poll(1.0)
            if msg is None:
                if idle_exit and _time.monotonic() - last_event > idle_exit:
                    break
                continue
            if msg.error():
                typer.echo(f"kafka error: {msg.error()}")
                continue
            event = _json.loads(msg.value())
            outcome = handle_event(settings, embedder, event)
            consumer.commit(message=msg, asynchronous=False)
            handled, last_event = handled + 1, _time.monotonic()
            typer.echo(f"{event['posting_key'][:12]} {outcome}")
    finally:
        consumer.close()


# metrics where a lower value is better; everything else is better when higher
LOWER_IS_BETTER = {
    "duplicate_at_5",
    "stale_at_5",
    "false_refusal_rate",
    "latency_p50_ms",
    "latency_p95_ms",
    "tokens_per_question",
}


@eval_app.command("compare")
def eval_compare(run_id: str, against: str = typer.Option("accepted", help="Run id, or 'accepted'.")) -> None:
    """Show how a run differs from the accepted run (FR-EVL-03)."""
    import json

    from jobmarket.evaluation.runner import RESULTS_DIR

    new = json.loads((RESULTS_DIR / f"{run_id}.json").read_text())
    base = json.loads((RESULTS_DIR / f"{against}.json").read_text())
    typer.echo(f"{run_id} vs {base['run_id']}")
    worse = 0
    for metric, value in new["summary"].items():
        old = base["summary"].get(metric)
        if not isinstance(value, int | float) or not isinstance(old, int | float):
            continue
        delta = value - old
        better = delta < 0 if metric in LOWER_IS_BETTER else delta > 0
        flag = "" if abs(delta) < 1e-9 else ("better" if better else "WORSE")
        worse += flag == "WORSE" and not metric.startswith(("latency", "tokens"))
        typer.echo(f"  {metric:24} {old!s:>10} -> {value!s:<10} {flag}")
    if worse:
        typer.echo(f"{worse} quality metric(s) got worse.")


@eval_app.command("accept")
def eval_accept(run_id: str) -> None:
    """Make a run the accepted baseline that later runs are compared with."""
    import shutil

    from jobmarket.evaluation.runner import RESULTS_DIR

    shutil.copyfile(RESULTS_DIR / f"{run_id}.json", RESULTS_DIR / "accepted.json")
    typer.echo(f"{run_id} is now eval/results/accepted.json")


@eval_app.command("report")
def eval_report(run: Annotated[list[str], typer.Option(help="Run ids; the first is the accepted one.")]) -> None:
    """Write docs/evaluation/results.md from stored runs."""
    from jobmarket.evaluation.report import write_report

    typer.echo(f"wrote {write_report(run)}")


@eval_app.command("embeddings")
def eval_embeddings(
    baseline: str,
    model: Annotated[list[str], typer.Option(help="Embedding models to compare; each needs its index built.")],
) -> None:
    """Compare embedding models on retrieval over the same questions (FR-EVL-04)."""
    from jobmarket.evaluation.experiment import compare_embeddings
    from jobmarket.evaluation.runner import RESULTS_DIR
    from jobmarket.llm import get_embedder

    settings = get_settings()
    result = compare_embeddings(settings, [get_embedder(m, settings) for m in model], RESULTS_DIR / f"{baseline}.json")
    for name, s in result["summary"].items():
        typer.echo(f"{name:32} {s}")


@eval_app.command("rejudge")
def eval_rejudge(run_id: str, judge: str = typer.Option("gemini")) -> None:
    """Re-score groundedness and citation accuracy of a stored run with the current judge inputs."""
    from jobmarket.evaluation.runner import rejudge
    from jobmarket.llm import get_embedder, get_llm

    settings = get_settings()
    data = rejudge(settings, get_embedder(settings=settings), get_llm(judge, settings=settings), run_id, typer.echo)
    typer.echo({k: data["summary"][k] for k in ("groundedness", "citation_accuracy")})
