# ADR-0010: Running dbt from Airflow, one task per model

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-06 |
| **Deciders** | Anurag V V |

## Context

The daily pipeline must run without manual steps (FR-ORC-01). Each transformation model must be a separate, individually retryable task (FR-ORC-02), and a failed Gold test must stop publishing (FR-ORC-03).

## Options considered

1. **One `dbt build` task.** Simple, but a failure in one model reruns everything, and the run history shows one opaque task.
2. **Astronomer Cosmos.** Renders a dbt project as Airflow tasks. Adds a dependency whose versions must track both Airflow and dbt.
3. **A small manifest reader.** The DAG reads dbt's `manifest.json` and creates one `dbt build --select <model>` task per model, with the same dependencies as dbt.

## Decision

**Option 3** (`orchestration/dags/jobmarket_daily.py`), about 20 lines that stay readable and have no extra dependency. `dbt build --select <model>` runs the model **and its tests**, so a failing test fails that task, and the index refresh (the step that publishes Gold to the assistant) runs only when every model task succeeded.

The project runs in its own virtual environment inside the Airflow image (`/opt/jobmarket-venv`), so Airflow's and dbt's dependencies never conflict.

## Consequences

- New models appear as tasks automatically after the next `dbt parse` (any `make dbt-build` updates the manifest).
- If the manifest is missing, the DAG falls back to one `dbt build` task.
- dbt's parse cost is paid per task (a few seconds each). That's acceptable at about 18 models; Cosmos or `dbt build --select` groups would be worth revisiting at hundreds.
