"""Daily batch pipeline for the Job Market Assistant (Phase 3, FR-ORC-01 to FR-ORC-04).

collect -> load Bronze -> dbt seeds -> one task per dbt model (build = run + its tests)
-> freshness check -> refresh the retrieval index -> record the run

- Each dbt model is its own task, retried on its own (FR-ORC-02). Tasks and their
  dependencies come from dbt's manifest.json, so new models appear automatically.
- `dbt build --select <model>` runs the model's tests; a failing test fails the task,
  and the index refresh (which "publishes" Gold to the assistant) needs every model
  task to succeed (FR-ORC-03).
- Any failed task raises an alert (FR-ORC-04); the freshness check alerts on stale
  sources (NFR-01).
- A failed collection doesn't stop the rest: what was already in Bronze is still
  transformed and published (NFR-16).

Commands run in the project's own virtual environment (/opt/jobmarket-venv), kept
separate from Airflow's so dbt and Airflow dependencies can't conflict.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

PROJECT = Path("/opt/jobmarket")
VENV_BIN = "/opt/jobmarket-venv/bin"
MANIFEST = PROJECT / "transform" / "target" / "manifest.json"
DBT = f"cd {PROJECT}/transform && {VENV_BIN}/dbt"
JOBMARKET = f"cd {PROJECT} && {VENV_BIN}/jobmarket"


def alert_on_failure(context) -> None:
    ti = context["task_instance"]
    message = f"{ti.dag_id}.{ti.task_id} failed (run {context['run_id']}, try {ti.try_number})"
    subprocess.run(
        [f"{VENV_BIN}/jobmarket", "ops", "alert", message, "--kind", "task_failed"], cwd=PROJECT, check=False
    )


def dbt_models() -> dict[str, list[str]]:
    """{model: [upstream models]} from the dbt manifest; empty if dbt hasn't parsed yet."""
    if not MANIFEST.exists():
        return {}
    nodes = json.loads(MANIFEST.read_text())["nodes"]
    models = {k: v for k, v in nodes.items() if v["resource_type"] == "model"}
    return {v["name"]: [models[d]["name"] for d in v["depends_on"]["nodes"] if d in models] for v in models.values()}


with DAG(
    dag_id="jobmarket_daily",
    description="Collect, load, transform, test and index job postings",
    schedule="30 0 * * *",  # 00:30 UTC = 06:00 IST
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
        "retry_exponential_backoff": True,
        "on_failure_callback": alert_on_failure,
    },
    tags=["jobmarket"],
) as dag:
    collect = BashOperator(task_id="collect_greenhouse", bash_command=f"{JOBMARKET} collect greenhouse", retries=3)
    load = BashOperator(
        task_id="load_bronze",
        bash_command=f"{JOBMARKET} bronze load",
        trigger_rule="all_done",  # a failed collection still lets existing data through (NFR-16)
    )
    seeds = BashOperator(task_id="dbt_seed", bash_command=f"{DBT} seed --target dev")
    collect >> load >> seeds

    models = dbt_models()
    model_tasks = {
        name: BashOperator(task_id=f"dbt_{name}", bash_command=f"{DBT} build --select {name} --target dev")
        for name in models
    }
    for name, task in model_tasks.items():
        upstream = [model_tasks[u] for u in models[name] if u in model_tasks]
        (upstream or [seeds]) >> task
    if not model_tasks:  # first start, before dbt has produced a manifest
        model_tasks["all"] = BashOperator(task_id="dbt_build_all", bash_command=f"{DBT} build --target dev")
        seeds >> model_tasks["all"]

    fresh = BashOperator(task_id="check_freshness", bash_command=f"{JOBMARKET} ops freshness", retries=0)
    index = BashOperator(task_id="refresh_index", bash_command=f"{JOBMARKET} index build")
    record = BashOperator(
        task_id="record_run",
        bash_command=f"{JOBMARKET} ops record-run {{{{ run_id }}}}",
        trigger_rule="all_done",  # record failed runs too (FR-OBS-01)
        retries=0,
    )
    list(model_tasks.values()) >> index
    load >> fresh
    [index, fresh] >> record
