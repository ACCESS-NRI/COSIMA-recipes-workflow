#!/usr/bin/env python3
"""Build static dashboard data for COSIMA Recipes workflow results.

The dashboard starts from the legacy recipe manifest and can be enriched with one
or more all-recipes summary JSON files produced by the Gadi polling workflow.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ENVIRONMENT = "conda/analysis3"
STYLE_META = {
    "01-Cooking-Tutorials": {
        "style": "tutorial",
        "label": "Cooking tutorial",
        "description": "Introductory and advanced tutorial notebooks.",
    },
    "02-Easy-Recipes": {
        "style": "easy",
        "label": "Easy recipe",
        "description": "Common analysis examples intended to be quick to run.",
    },
    "03-Advanced-Recipes": {
        "style": "advanced",
        "label": "Advanced recipe",
        "description": "Specialist diagnostics or heavier workflows.",
    },
    "04-Regional-Specialties": {
        "style": "regional",
        "label": "Regional specialty",
        "description": "Regional model and domain-specific examples.",
    },
}
STATUS_ORDER = ["passed", "failed", "timeout", "missing-result", "incomplete", "submitted", "not-run", "disabled"]


def slugify(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-._")
    return safe.lower() or "recipe"


def recipe_title(path: str) -> str:
    stem = Path(path).stem
    title = stem.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", title).strip()


def top_level(path: str) -> str:
    return path.split("/", 1)[0]


def style_for_path(path: str) -> dict[str, str]:
    root = top_level(path)
    meta = STYLE_META.get(root, {})
    return {
        "root": root,
        "style": meta.get("style", "other"),
        "style_label": meta.get("label", root.replace("-", " ")),
        "style_description": meta.get("description", "Recipe category inferred from the top-level folder."),
    }


def parse_recipe_manifest(path: Path) -> list[dict[str, Any]]:
    """Parse the simple recipe list in .github/configs/cosima-all-recipes.yml.

    This avoids adding a PyYAML dependency just to read the existing manifest.
    It intentionally handles only the manifest structure used by this repository.
    """
    recipes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_recipes = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "recipes:":
            in_recipes = True
            continue
        if not in_recipes:
            continue
        if stripped.startswith("- "):
            if current:
                recipes.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if stripped:
                key, value = parse_key_value(stripped)
                current[key] = value
            continue
        if current is not None and ":" in stripped:
            key, value = parse_key_value(stripped)
            current[key] = value
    if current:
        recipes.append(current)
    return recipes


def parse_key_value(text: str) -> tuple[str, Any]:
    key, value = text.split(":", 1)
    value = value.strip()
    if value.lower() == "true":
        parsed: Any = True
    elif value.lower() == "false":
        parsed = False
    else:
        parsed = value.strip('"\'')
    return key.strip(), parsed


def load_defaults(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle).get("defaults", {})


def normalise_result(result: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    status = result.get("status") or "unknown"
    return {
        "status": status,
        "exit_code": result.get("exit_code"),
        "duration_seconds": result.get("duration_seconds"),
        "started_epoch": result.get("started_epoch"),
        "finished_epoch": result.get("finished_epoch"),
        "log_path": result.get("log_path", ""),
        "executed_notebook": result.get("executed_notebook", ""),
        "pbs_job_id": result.get("pbs_job_id") or summary.get("pbs_job_id", ""),
        "run_dir": result.get("run_dir") or summary.get("run_dir", ""),
        "recipes_commit": result.get("recipes_commit") or summary.get("recipes_commit", ""),
        "summary_status": summary.get("status", ""),
        "summary_json": summary.get("summary_json", ""),
        "last_updated": summary.get("generated_at") or datetime.now(timezone.utc).isoformat(),
    }


def load_summaries(patterns: list[str]) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]], set[str]]:
    by_env: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    runs: list[dict[str, Any]] = []
    environments: set[str] = set()
    paths: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if not matches and Path(pattern).exists():
            matches = [pattern]
        paths.extend(matches)

    for path in paths:
        with open(path, encoding="utf-8") as handle:
            summary = json.load(handle)
        env = summary.get("conda_module") or DEFAULT_ENVIRONMENT
        environments.add(env)
        results = summary.get("results", [])
        for result in results:
            notebook_path = result.get("notebook_path")
            if notebook_path:
                by_env[env][notebook_path] = normalise_result(result, summary)
        runs.append({
            "status": summary.get("status", "unknown"),
            "resource_profile": summary.get("resource_profile", ""),
            "queue": summary.get("queue", ""),
            "walltime": summary.get("walltime", ""),
            "memory": summary.get("memory", ""),
            "ncpus": summary.get("ncpus"),
            "conda_module": env,
            "recipes_ref": summary.get("recipes_ref", ""),
            "recipes_commit": summary.get("recipes_commit", ""),
            "pbs_job_id": summary.get("pbs_job_id", ""),
            "run_dir": summary.get("run_dir", ""),
            "expected_count": summary.get("expected_count"),
            "completed_count": summary.get("completed_count"),
            "passed_count": summary.get("passed_count"),
            "failed_count": summary.get("failed_count"),
            "missing_count": summary.get("missing_count"),
            "generated_at": summary.get("generated_at", ""),
            "source_file": path,
        })
    return by_env, runs, environments


def build_dashboard(defaults_path: Path, manifest_path: Path, summary_patterns: list[str]) -> dict[str, Any]:
    defaults = load_defaults(defaults_path)
    recipes = parse_recipe_manifest(manifest_path)
    by_env, runs, result_envs = load_summaries(summary_patterns)
    default_env = defaults.get("conda_module", DEFAULT_ENVIRONMENT)
    environments = sorted({default_env, *result_envs})

    recipe_rows = []
    env_counts: dict[str, Counter[str]] = {env: Counter() for env in environments}
    style_counts: Counter[str] = Counter()
    for entry in recipes:
        path = str(entry.get("path", ""))
        enabled = bool(entry.get("enabled", True))
        style = style_for_path(path)
        style_counts[style["style"]] += 1
        statuses: dict[str, dict[str, Any]] = {}
        for env in environments:
            if not enabled:
                status = {"status": "disabled"}
            else:
                status = by_env.get(env, {}).get(path, {"status": "not-run"})
            statuses[env] = status
            env_counts[env][status.get("status", "unknown")] += 1
        recipe_rows.append({
            "id": slugify(path),
            "name": entry.get("name") or slugify(path),
            "title": recipe_title(path),
            "path": path,
            "enabled": enabled,
            **style,
            "statuses": statuses,
        })

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": "ACCESS-NRI/COSIMA-recipes-workflow",
        "source_repository": defaults.get("repository_url", "https://github.com/COSIMA/cosima-recipes.git"),
        "default_environment": default_env,
        "environments": environments,
        "views": ["overview", "cards", "table", "detail"],
        "assumptions": [
            "Recipe style is inferred from the top-level COSIMA Recipes folder.",
            "Recipes without an imported all-recipes summary are shown as not-run for that analysis3 environment.",
            "The analysis3 environment selector is populated from workflow defaults and any summary JSON files used to build this data.",
        ],
        "summary": {
            "recipe_count": len(recipe_rows),
            "style_counts": dict(sorted(style_counts.items())),
            "environment_counts": {env: dict(env_counts[env]) for env in environments},
        },
        "runs": runs,
        "recipes": recipe_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--defaults", default=".github/configs/cosima-all-recipes.json")
    parser.add_argument("--manifest", default=".github/configs/cosima-all-recipes.yml")
    parser.add_argument("--summary-json", action="append", default=[], help="Summary JSON path or glob. Can be repeated.")
    parser.add_argument("--out", default="dashboard/dashboard-data.json")
    args = parser.parse_args()

    data = build_dashboard(Path(args.defaults), Path(args.manifest), args.summary_json)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out} with {len(data['recipes'])} recipes and {len(data['environments'])} environment(s)")


if __name__ == "__main__":
    main()
