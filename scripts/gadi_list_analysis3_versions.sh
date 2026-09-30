#!/usr/bin/env bash
set -euo pipefail

module_base_path=${1:?module base path is required}
module_dir="${module_base_path%/}/conda"
[[ -d "$module_dir" ]] || { echo "No conda module directory: $module_dir" >&2; exit 2; }

shopt -s nullglob
module_files=("$module_dir"/analysis3-[0-9][0-9].[0-9][0-9])
if (( ${#module_files[@]} < 6 )); then
  echo "Found ${#module_files[@]} versioned analysis3 modules in $module_dir; need six" >&2
  exit 2
fi

printf '%s\n' "${module_files[@]##*/}" | sort -V | tail -n 6 | sed 's/^analysis3-//'
