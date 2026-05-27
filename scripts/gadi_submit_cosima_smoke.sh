#!/usr/bin/env bash
# Submit one COSIMA Recipes notebook to PBS on Gadi, non-blocking.
set -euo pipefail

if [[ $# -ne 12 ]]; then
  echo "usage: $0 RUN_DIR REPO_URL RECIPES_REF NOTEBOOK_PATH CONDA_MODULE MODULE_BASE_PATH PROJECT QUEUE WALLTIME MEMORY NCPUS STORAGE" >&2
  exit 2
fi

RUN_DIR=$1
REPO_URL=$2
RECIPES_REF=$3
NOTEBOOK_PATH=$4
CONDA_MODULE=$5
MODULE_BASE_PATH=$6
PROJECT=$7
QUEUE=$8
WALLTIME=$9
MEMORY=${10}
NCPUS=${11}
STORAGE=${12}
SAFE_NAME=$(printf '%s' "$NOTEBOOK_PATH" | sed -E 's#[^A-Za-z0-9_.-]+#-#g; s#^-+##; s#-+$##')
[[ -n "$SAFE_NAME" ]] || SAFE_NAME=notebook
PBS_JOB_NAME=$(printf '%s' "$SAFE_NAME" | sed -E 's#[^A-Za-z0-9_-]+#_#g' | cut -c1-40)
[[ -n "$PBS_JOB_NAME" ]] || PBS_JOB_NAME=notebook

case "$NOTEBOOK_PATH" in
  /*|*..*) echo "unsafe notebook path: $NOTEBOOK_PATH" >&2; exit 2 ;;
esac

diagnose_path() {
  local path=$1
  echo "Diagnostics for $path:" >&2
  df -h "$path" >&2 || true
  df -i "$path" >&2 || true
  ls -ld "$path" >&2 || true
}

mkdir -p "$RUN_DIR" "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/outputs"
SOURCE_DIR="$RUN_DIR/source"
PBS_SCRIPT="$RUN_DIR/${SAFE_NAME}.pbs"
SUBMISSION_JSON="$RUN_DIR/results/${SAFE_NAME}.submitted.json"
RESULT_JSON="$RUN_DIR/results/${SAFE_NAME}.result.json"

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

if [[ ! -f "$SOURCE_DIR/$NOTEBOOK_PATH" ]]; then
  echo "notebook not found after checkout: $NOTEBOOK_PATH" >&2
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
#PBS -N cosima_$PBS_JOB_NAME
#PBS -o $RUN_DIR/logs/${SAFE_NAME}.pbs.out
#PBS -e $RUN_DIR/logs/${SAFE_NAME}.pbs.err

set -uo pipefail
RUN_DIR="$RUN_DIR"
SOURCE_DIR="$SOURCE_DIR"
NOTEBOOK_PATH="$NOTEBOOK_PATH"
SAFE_NAME="$SAFE_NAME"
RESULT_JSON="$RESULT_JSON"
CONDA_MODULE="$CONDA_MODULE"
MODULE_BASE_PATH="$MODULE_BASE_PATH"
COMMIT="$COMMIT"
START_EPOCH=\$(date +%s)
STATUS=failed
EXIT_CODE=0

mkdir -p "\$RUN_DIR/logs" "\$RUN_DIR/results" "\$RUN_DIR/outputs"
cd "\$SOURCE_DIR" || exit 20

{
  echo "COSIMA smoke test started at \$(date -Is)"
  echo "PBS job id: \${PBS_JOBID:-unknown}"
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
    --ExecutePreprocessor.timeout=1800 \
    --output "\${SAFE_NAME}.executed.ipynb" \
    --output-dir "\$RUN_DIR/outputs"
  EXIT_CODE=\$?
} > "\$RUN_DIR/logs/\${SAFE_NAME}.notebook.log" 2>&1 || EXIT_CODE=\$?

END_EPOCH=\$(date +%s)
if [[ "\$EXIT_CODE" -eq 0 ]]; then
  STATUS=passed
else
  STATUS=failed
fi

STATUS="\$STATUS" EXIT_CODE="\$EXIT_CODE" START_EPOCH="\$START_EPOCH" END_EPOCH="\$END_EPOCH" \
  RUN_DIR="\$RUN_DIR" NOTEBOOK_PATH="\$NOTEBOOK_PATH" SAFE_NAME="\$SAFE_NAME" COMMIT="\$COMMIT" \
  JOB_ID="\${PBS_JOBID:-unknown}" CONDA_MODULE="\$CONDA_MODULE" MODULE_BASE_PATH="\$MODULE_BASE_PATH" \
  python3 - <<'PY'
import json, os
start = int(os.environ["START_EPOCH"])
end = int(os.environ["END_EPOCH"])
result = {
    "status": os.environ["STATUS"],
    "exit_code": int(os.environ["EXIT_CODE"]),
    "notebook_path": os.environ["NOTEBOOK_PATH"],
    "safe_name": os.environ["SAFE_NAME"],
    "recipes_commit": os.environ["COMMIT"],
    "pbs_job_id": os.environ["JOB_ID"],
    "conda_module": os.environ["CONDA_MODULE"],
    "module_base_path": os.environ["MODULE_BASE_PATH"],
    "run_dir": os.environ["RUN_DIR"],
    "log_path": f'{os.environ["RUN_DIR"]}/logs/{os.environ["SAFE_NAME"]}.notebook.log',
    "executed_notebook": f'{os.environ["RUN_DIR"]}/outputs/{os.environ["SAFE_NAME"]}.executed.ipynb',
    "started_epoch": start,
    "finished_epoch": end,
    "duration_seconds": end - start,
}
with open(os.path.join(os.environ["RUN_DIR"], "results", f'{os.environ["SAFE_NAME"]}.result.json'), "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

exit "\$EXIT_CODE"
EOF

JOB_ID=$(qsub "$PBS_SCRIPT")
JOB_ID=${JOB_ID%%[[:space:]]*}

JOB_ID="$JOB_ID" RUN_DIR="$RUN_DIR" NOTEBOOK_PATH="$NOTEBOOK_PATH" SAFE_NAME="$SAFE_NAME" COMMIT="$COMMIT" \
  CONDA_MODULE="$CONDA_MODULE" MODULE_BASE_PATH="$MODULE_BASE_PATH" RESULT_JSON="$RESULT_JSON" PBS_SCRIPT="$PBS_SCRIPT" \
  python3 - <<'PY'
import json, os
submitted = {
    "status": "submitted",
    "pbs_job_id": os.environ["JOB_ID"],
    "notebook_path": os.environ["NOTEBOOK_PATH"],
    "safe_name": os.environ["SAFE_NAME"],
    "recipes_commit": os.environ["COMMIT"],
    "conda_module": os.environ["CONDA_MODULE"],
    "module_base_path": os.environ["MODULE_BASE_PATH"],
    "run_dir": os.environ["RUN_DIR"],
    "result_json": os.environ["RESULT_JSON"],
    "pbs_script": os.environ["PBS_SCRIPT"],
}
with open(os.path.join(os.environ["RUN_DIR"], "results", f'{os.environ["SAFE_NAME"]}.submitted.json'), "w", encoding="utf-8") as handle:
    json.dump(submitted, handle, indent=2, sort_keys=True)
    handle.write("\n")
print(json.dumps(submitted, sort_keys=True))
PY
