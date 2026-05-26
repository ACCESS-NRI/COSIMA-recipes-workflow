#!/usr/bin/env bash
# Poll for the result JSON from one COSIMA Recipes PBS job on Gadi.
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 RESULT_JSON TIMEOUT_MINUTES INTERVAL_SECONDS JOB_ID" >&2
  exit 2
fi

RESULT_JSON=$1
TIMEOUT_MINUTES=$2
INTERVAL_SECONDS=$3
JOB_ID=$4
DEADLINE=$(( $(date +%s) + TIMEOUT_MINUTES * 60 ))

while [[ $(date +%s) -le $DEADLINE ]]; do
  if [[ -s "$RESULT_JSON" ]]; then
    cat "$RESULT_JSON"
    exit 0
  fi
  if command -v qstat >/dev/null 2>&1 && ! qstat "$JOB_ID" >/dev/null 2>&1; then
    # The job has left the queue but the result was not written. Wait one more
    # interval for filesystem visibility, then report an actionable failure.
    sleep "$INTERVAL_SECONDS"
    if [[ -s "$RESULT_JSON" ]]; then
      cat "$RESULT_JSON"
      exit 0
    fi
    printf '{"status":"missing-result","pbs_job_id":"%s","result_json":"%s"}\n' "$JOB_ID" "$RESULT_JSON"
    exit 4
  fi
  sleep "$INTERVAL_SECONDS"
done

printf '{"status":"timeout","pbs_job_id":"%s","result_json":"%s","timeout_minutes":%s}\n' "$JOB_ID" "$RESULT_JSON" "$TIMEOUT_MINUTES"
exit 124
