#!/usr/bin/env bash
# FR-EVL-03 guard: a change to retrieval, prompts or models must come with a new
# evaluation run in eval/results/. The full evaluation needs the local data and
# models, so it runs locally (make eval); CI enforces that it was run.
set -euo pipefail
base="${1:-}"
if [[ -z "$base" || "$base" =~ ^0+$ ]] || ! git cat-file -e "$base" 2>/dev/null; then
  echo "No base commit to compare with; skipping."; exit 0
fi
changed=$(git diff --name-only "$base" HEAD)
sensitive=$(echo "$changed" | grep -E '^(src/jobmarket/(index/|llm\.py|api/assistant\.py|api/metrics\.py)|eval/eval_set_)' || true)
if [[ -z "$sensitive" ]]; then
  echo "No retrieval, prompt or model changes."; exit 0
fi
if echo "$changed" | grep -qE '^eval/results/.+\.json$'; then
  echo "Retrieval/prompt/model changes come with an evaluation run:"; echo "$sensitive"; exit 0
fi
echo "These files affect answer quality, but no evaluation run was committed:"
echo "$sensitive"
echo "Run 'make eval', compare with 'jobmarket eval compare <run> ', and commit eval/results/."
exit 1
