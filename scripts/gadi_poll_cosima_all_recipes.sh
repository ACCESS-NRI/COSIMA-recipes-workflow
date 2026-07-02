#!/usr/bin/env bash
# Poll for all COSIMA Recipes PBS-array result JSON files on Gadi.
set -euo pipefail

if [[ $# -ne 6 ]]; then
  echo "usage: $0 RUN_DIR SUMMARY_JSON NOTEBOOK_COUNT TIMEOUT_MINUTES INTERVAL_SECONDS JOB_ID_CSV" >&2
  exit 2
fi

RUN_DIR=$1
SUMMARY_JSON=$2
NOTEBOOK_COUNT=$3
TIMEOUT_MINUTES=$4
INTERVAL_SECONDS=$5
JOB_ID_CSV=$6
RESULTS_DIR="$RUN_DIR/results"
DEADLINE=$(( $(date +%s) + TIMEOUT_MINUTES * 60 ))

IFS=',' read -r -a JOB_IDS <<< "$JOB_ID_CSV"

aggregate_results() {
  local status_override=${1:-}
  STATUS_OVERRIDE="$status_override" RUN_DIR="$RUN_DIR" SUMMARY_JSON="$SUMMARY_JSON" NOTEBOOK_COUNT="$NOTEBOOK_COUNT" JOB_ID_CSV="$JOB_ID_CSV" python3 - <<'PY'
from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timezone

run_dir = os.environ["RUN_DIR"]
summary_json = os.environ["SUMMARY_JSON"]
expected = int(os.environ["NOTEBOOK_COUNT"])
job_ids = [value for value in os.environ.get("JOB_ID_CSV", "").split(",") if value]
status_override = os.environ.get("STATUS_OVERRIDE", "")
results_dir = os.path.join(run_dir, "results")
results = []
for path in sorted(glob.glob(os.path.join(results_dir, "*.result.json"))):
    try:
        with open(path, encoding="utf-8") as handle:
            results.append(json.load(handle))
    except Exception as exc:  # pragma: no cover - defensive runtime reporting
        results.append({"status": "invalid-result", "result_json": path, "error": str(exc)})

passed = [item for item in results if item.get("status") == "passed"]
failed = [item for item in results if item.get("status") != "passed"]
first_result = results[0] if results else {}
missing_count = max(expected - len(results), 0)
if status_override:
    status = status_override
elif missing_count:
    status = "incomplete"
elif failed:
    status = "failed"
else:
    status = "passed"

summary = {
    "status": status,
    "pbs_job_id": os.environ.get("JOB_ID_CSV", ""),
    "pbs_job_ids": job_ids,
    "run_dir": run_dir,
    "summary_json": summary_json,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "conda_module": first_result.get("conda_module", ""),
    "module_base_path": first_result.get("module_base_path", ""),
    "recipes_commit": first_result.get("recipes_commit", ""),
    "expected_count": expected,
    "completed_count": len(results),
    "passed_count": len(passed),
    "failed_count": len(failed),
    "missing_count": missing_count,
    "results": results,
    "failed_notebooks": [
        {
            "notebook_path": item.get("notebook_path", "unknown"),
            "status": item.get("status", "unknown"),
            "exit_code": item.get("exit_code", ""),
            "log_path": item.get("log_path", ""),
        }
        for item in failed
    ],
}
with open(summary_json, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, sort_keys=True)
    handle.write("\n")
print(json.dumps(summary, sort_keys=True))
PY
}

while [[ $(date +%s) -le $DEADLINE ]]; do
  completed=$(find "$RESULTS_DIR" -maxdepth 1 -type f -name '*.result.json' 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$completed" -ge "$NOTEBOOK_COUNT" ]]; then
    aggregate_results
    exit 0
  fi
  if command -v qstat >/dev/null 2>&1; then
    all_finished=true
    for job_id in "${JOB_IDS[@]}"; do
      [[ -n "$job_id" ]] || continue
      if qstat "$job_id" >/dev/null 2>&1; then
        all_finished=false
        break
      fi
    done
    if [[ "$all_finished" == true ]]; then
      sleep "$INTERVAL_SECONDS"
      completed=$(find "$RESULTS_DIR" -maxdepth 1 -type f -name '*.result.json' 2>/dev/null | wc -l | tr -d ' ')
      if [[ "$completed" -ge "$NOTEBOOK_COUNT" ]]; then
        aggregate_results
        exit 0
      fi
      aggregate_results missing-result
      exit 4
    fi
  fi
  sleep "$INTERVAL_SECONDS"
done

aggregate_results timeout
exit 124
