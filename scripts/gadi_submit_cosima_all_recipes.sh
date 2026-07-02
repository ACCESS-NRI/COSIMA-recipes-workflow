#!/usr/bin/env bash
# Submit all COSIMA Recipes notebooks to PBS on Gadi as an array job.
set -euo pipefail

if [[ $# -ne 14 ]]; then
  echo "usage: $0 RUN_DIR REPO_URL RECIPES_REF NOTEBOOK_ROOTS CONDA_MODULE MODULE_BASE_PATH PROJECT QUEUE WALLTIME MEMORY NCPUS STORAGE EXECUTE_TIMEOUT_SECONDS POLL_INTERVAL_SECONDS" >&2
  exit 2
fi

RUN_DIR=$1
REPO_URL=$2
RECIPES_REF=$3
NOTEBOOK_ROOTS=$4
CONDA_MODULE=$5
MODULE_BASE_PATH=$6
PROJECT=$7
QUEUE=$8
WALLTIME=$9
MEMORY=${10}
NCPUS=${11}
STORAGE=${12}
EXECUTE_TIMEOUT_SECONDS=${13}
POLL_INTERVAL_SECONDS=${14}

case "$NOTEBOOK_ROOTS" in
  /*|*..*) echo "unsafe notebook roots: $NOTEBOOK_ROOTS" >&2; exit 2 ;;
esac

safe_name() {
  local value=$1
  local safe
  safe=$(printf '%s' "$value" | sed -E 's#[^A-Za-z0-9_.-]+#-#g; s#^-+##; s#-+$##' | cut -c1-180)
  [[ -n "$safe" ]] || safe=notebook
  printf '%s' "$safe"
}

diagnose_path() {
  local path=$1
  echo "Diagnostics for $path:" >&2
  df -h "$path" >&2 || true
  df -i "$path" >&2 || true
  ls -ld "$path" >&2 || true
}

mkdir -p "$RUN_DIR" "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/outputs"
SOURCE_DIR="$RUN_DIR/source"
MANIFEST="$RUN_DIR/notebooks.tsv"
PBS_SCRIPT="$RUN_DIR/cosima-all-recipes.pbs"
SUMMARY_JSON="$RUN_DIR/results/all-recipes.summary.json"

if ! touch "$RUN_DIR/.write-test.$$" 2>/dev/null; then
  echo "run directory is not writable: $RUN_DIR" >&2
  diagnose_path "$RUN_DIR"
  exit 4
fi
rm -f "$RUN_DIR/.write-test.$$"

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
  if [[ -e "$SOURCE_DIR" ]]; then
    echo "removing incomplete source directory before clone: $SOURCE_DIR" >&2
    rm -rf "$SOURCE_DIR"
  fi
  CLONE_TMP=$(mktemp -d "$RUN_DIR/source.tmp.XXXXXX")
  trap 'rm -rf "${CLONE_TMP:-}"' EXIT
  if ! git clone --filter=blob:none "$REPO_URL" "$CLONE_TMP" >&2; then
    echo "git clone failed in temporary source directory: $CLONE_TMP" >&2
    diagnose_path "$RUN_DIR"
    exit 4
  fi
  mv "$CLONE_TMP" "$SOURCE_DIR"
  trap - EXIT
fi
git -C "$SOURCE_DIR" fetch --depth=1 origin "$RECIPES_REF" >&2
git -C "$SOURCE_DIR" checkout --detach FETCH_HEAD >&2
COMMIT=$(git -C "$SOURCE_DIR" rev-parse HEAD)

: > "$MANIFEST"
INDEX=0
IFS=':' read -r -a ROOTS <<< "$NOTEBOOK_ROOTS"
for root in "${ROOTS[@]}"; do
  [[ -n "$root" ]] || continue
  case "$root" in /*|*..*) echo "unsafe notebook root: $root" >&2; exit 2 ;; esac
  if [[ ! -d "$SOURCE_DIR/$root" ]]; then
    echo "notebook root not found at requested ref: $root" >&2
    continue
  fi
  while IFS= read -r notebook; do
    [[ -n "$notebook" ]] || continue
    case "$notebook" in /*|*..*|*.ipynb_checkpoints*) continue ;; esac
    INDEX=$((INDEX + 1))
    printf '%s\t%s\t%s\n' "$INDEX" "$notebook" "$(safe_name "$notebook")" >> "$MANIFEST"
  done < <(cd "$SOURCE_DIR" && find "$root" -type f -name '*.ipynb' | LC_ALL=C sort)
done
NOTEBOOK_COUNT=$INDEX
if [[ "$NOTEBOOK_COUNT" -eq 0 ]]; then
  echo "no notebooks found under roots: $NOTEBOOK_ROOTS" >&2
  exit 3
fi

cat > "$PBS_SCRIPT" <<EOF
#!/usr/bin/env bash
#PBS -P $PROJECT
#PBS -q $QUEUE
#PBS -l walltime=$WALLTIME
#PBS -l mem=$MEMORY
#PBS -l ncpus=$NCPUS
#PBS -l storage=$STORAGE
#PBS -l wd
#PBS -r y
#PBS -J 1-$NOTEBOOK_COUNT
#PBS -N cosima_all_recipes
#PBS -o $RUN_DIR/logs/all-recipes.\$PBS_ARRAY_INDEX.pbs.out
#PBS -e $RUN_DIR/logs/all-recipes.\$PBS_ARRAY_INDEX.pbs.err

set -uo pipefail
RUN_DIR="$RUN_DIR"
SOURCE_DIR="$SOURCE_DIR"
MANIFEST="$MANIFEST"
CONDA_MODULE="$CONDA_MODULE"
MODULE_BASE_PATH="$MODULE_BASE_PATH"
COMMIT="$COMMIT"
EXECUTE_TIMEOUT_SECONDS="$EXECUTE_TIMEOUT_SECONDS"
ARRAY_INDEX="\${PBS_ARRAY_INDEX:-1}"
START_EPOCH=\$(date +%s)
STATUS=failed
EXIT_CODE=0

mkdir -p "\$RUN_DIR/logs" "\$RUN_DIR/results" "\$RUN_DIR/outputs"
LINE=\$(awk -F '\t' -v idx="\$ARRAY_INDEX" '\$1 == idx { print; exit }' "\$MANIFEST")
if [[ -z "\$LINE" ]]; then
  echo "No notebook manifest entry for array index \$ARRAY_INDEX" >&2
  exit 22
fi
IFS=\$'\t' read -r INDEX NOTEBOOK_PATH SAFE_NAME <<< "\$LINE"
RESULT_JSON="\$RUN_DIR/results/\$(printf '%03d' "\$INDEX")-\${SAFE_NAME}.result.json"
LOG_PATH="\$RUN_DIR/logs/\$(printf '%03d' "\$INDEX")-\${SAFE_NAME}.notebook.log"
EXECUTED_NOTEBOOK="\$RUN_DIR/outputs/\$(printf '%03d' "\$INDEX")-\${SAFE_NAME}.executed.ipynb"

cd "\$SOURCE_DIR" || exit 20
{
  echo "COSIMA all-recipes task started at \$(date -Is)"
  echo "PBS job id: \${PBS_JOBID:-unknown}"
  echo "Array index: \$ARRAY_INDEX"
  echo "Notebook: \$NOTEBOOK_PATH"
  echo "Commit: \$COMMIT"
  if ! command -v module >/dev/null 2>&1; then
    # shellcheck disable=SC1091
    source /etc/profile >/dev/null 2>&1 || true
  fi
  module use "\$MODULE_BASE_PATH"
  module load "\$CONDA_MODULE"
  module list
  python --version
  python -m jupyter nbconvert --to notebook --execute "\$NOTEBOOK_PATH" \
    --ExecutePreprocessor.kernel_name=python3 \
    --ExecutePreprocessor.timeout="\$EXECUTE_TIMEOUT_SECONDS" \
    --output "\$(basename "\$EXECUTED_NOTEBOOK")" \
    --output-dir "\$(dirname "\$EXECUTED_NOTEBOOK")"
  EXIT_CODE=\$?
} > "\$LOG_PATH" 2>&1 || EXIT_CODE=\$?

END_EPOCH=\$(date +%s)
if [[ "\$EXIT_CODE" -eq 0 ]]; then
  STATUS=passed
else
  STATUS=failed
fi

STATUS="\$STATUS" EXIT_CODE="\$EXIT_CODE" START_EPOCH="\$START_EPOCH" END_EPOCH="\$END_EPOCH" \
  RUN_DIR="\$RUN_DIR" NOTEBOOK_PATH="\$NOTEBOOK_PATH" SAFE_NAME="\$SAFE_NAME" COMMIT="\$COMMIT" \
  INDEX="\$INDEX" ARRAY_INDEX="\$ARRAY_INDEX" JOB_ID="\${PBS_JOBID:-unknown}" CONDA_MODULE="\$CONDA_MODULE" \
  MODULE_BASE_PATH="\$MODULE_BASE_PATH" LOG_PATH="\$LOG_PATH" EXECUTED_NOTEBOOK="\$EXECUTED_NOTEBOOK" RESULT_JSON="\$RESULT_JSON" \
  python3 - <<'PY'
import json, os
start = int(os.environ["START_EPOCH"])
end = int(os.environ["END_EPOCH"])
result = {
    "status": os.environ["STATUS"],
    "exit_code": int(os.environ["EXIT_CODE"]),
    "notebook_index": int(os.environ["INDEX"]),
    "array_index": os.environ["ARRAY_INDEX"],
    "notebook_path": os.environ["NOTEBOOK_PATH"],
    "safe_name": os.environ["SAFE_NAME"],
    "recipes_commit": os.environ["COMMIT"],
    "pbs_job_id": os.environ["JOB_ID"],
    "conda_module": os.environ["CONDA_MODULE"],
    "module_base_path": os.environ["MODULE_BASE_PATH"],
    "run_dir": os.environ["RUN_DIR"],
    "log_path": os.environ["LOG_PATH"],
    "executed_notebook": os.environ["EXECUTED_NOTEBOOK"],
    "started_epoch": start,
    "finished_epoch": end,
    "duration_seconds": end - start,
}
with open(os.environ["RESULT_JSON"], "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

exit "\$EXIT_CODE"
EOF

JOB_ID=$(env \
  -u QSUB_OPTIONS \
  -u PBS_QSUB_OPTS \
  -u PBS_OPTIONS \
  command qsub -r y "$PBS_SCRIPT")
JOB_ID=${JOB_ID%%[[:space:]]*}

JOB_ID="$JOB_ID" RUN_DIR="$RUN_DIR" COMMIT="$COMMIT" NOTEBOOK_COUNT="$NOTEBOOK_COUNT" NOTEBOOK_ROOTS="$NOTEBOOK_ROOTS" \
  CONDA_MODULE="$CONDA_MODULE" MODULE_BASE_PATH="$MODULE_BASE_PATH" SUMMARY_JSON="$SUMMARY_JSON" PBS_SCRIPT="$PBS_SCRIPT" MANIFEST="$MANIFEST" \
  POLL_INTERVAL_SECONDS="$POLL_INTERVAL_SECONDS" EXECUTE_TIMEOUT_SECONDS="$EXECUTE_TIMEOUT_SECONDS" \
  python3 - <<'PY'
import json, os
submitted = {
    "status": "submitted",
    "pbs_job_id": os.environ["JOB_ID"],
    "recipes_commit": os.environ["COMMIT"],
    "notebook_count": int(os.environ["NOTEBOOK_COUNT"]),
    "notebook_roots": os.environ["NOTEBOOK_ROOTS"].split(":"),
    "conda_module": os.environ["CONDA_MODULE"],
    "module_base_path": os.environ["MODULE_BASE_PATH"],
    "execute_timeout_seconds": int(os.environ["EXECUTE_TIMEOUT_SECONDS"]),
    "poll_interval_seconds": int(os.environ["POLL_INTERVAL_SECONDS"]),
    "run_dir": os.environ["RUN_DIR"],
    "summary_json": os.environ["SUMMARY_JSON"],
    "notebooks_manifest": os.environ["MANIFEST"],
    "pbs_script": os.environ["PBS_SCRIPT"],
}
with open(os.path.join(os.environ["RUN_DIR"], "results", "all-recipes.submitted.json"), "w", encoding="utf-8") as handle:
    json.dump(submitted, handle, indent=2, sort_keys=True)
    handle.write("\n")
print(json.dumps(submitted, sort_keys=True))
PY
