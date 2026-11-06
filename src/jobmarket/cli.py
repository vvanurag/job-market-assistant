"""Command-line entry point: ``jobmarket <command>``."""

from __future__ import annotations

from datetime import UTC
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
