#!/usr/bin/env python3
"""Plan a COSIMA Recipes all-notebooks PBS-array run."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import PurePosixPath
from typing import Any

SAFE_VALUE = re.compile(r"^[A-Za-z0-9_./:+@=-]+$")
SAFE_RESOURCE = re.compile(r"^[A-Za-z0-9_./:+-]+$")
SAFE_WALLTIME = re.compile(r"^\d{2}:\d{2}:\d{2}$")
RESOURCE_PROFILES: dict[str, dict[str, Any]] = {
    "medium": {"label": "Medium", "queue": "normalbw", "ncpus": 4, "memory": "18GB"},
    "large": {"label": "Large", "queue": "normalbw", "ncpus": 7, "memory": "32GB"},
    # Backward-compat alias: CLarge now canonicalizes to Large.
    "clarge": {"label": "Large", "queue": "normalbw", "ncpus": 7, "memory": "32GB"},
    "xlarge": {"label": "XLarge", "queue": "normalbw", "ncpus": 14, "memory": "63GB"},
    "xxlarge": {"label": "XXLarge", "queue": "normalbw", "ncpus": 28, "memory": "126GB"},
    "xxlargemem": {"label": "XXLargeMem", "queue": "normalbw", "ncpus": 28, "memory": "252GB"},
}


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def require_safe_value(label: str, value: str, pattern: re.Pattern[str] = SAFE_VALUE) -> str:
    if value is None or value == "":
        fail(f"{label} must not be empty")
    if not pattern.match(value):
        fail(f"{label} contains unsupported characters: {value!r}")
    return value


def require_safe_root(root: str) -> str:
    if not root:
        fail("notebook roots must not be empty")
    path = PurePosixPath(root)
    if path.is_absolute() or ".." in path.parts:
        fail(f"unsafe notebook root: {root!r}")
    if not SAFE_VALUE.match(root):
        fail(f"notebook root contains unsupported characters: {root!r}")
    return path.as_posix()


def load_config(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_profile_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--recipes-ref", default="")
    parser.add_argument("--conda-module", default="")
    parser.add_argument("--module-base-path", default="")
    parser.add_argument("--poll-timeout-minutes", default="")
    parser.add_argument("--execute-timeout-seconds", default="")
    parser.add_argument("--resource-profile", default="")
    parser.add_argument("--out", default="planned-all-recipes-run.json")
    args = parser.parse_args()

    config = load_config(args.config)
    planned = dict(config.get("defaults", {}))
    for key, value in {
        "recipes_ref": args.recipes_ref,
        "conda_module": args.conda_module,
        "module_base_path": args.module_base_path,
        "poll_timeout_minutes": args.poll_timeout_minutes,
        "execute_timeout_seconds": args.execute_timeout_seconds,
        "resource_profile": args.resource_profile,
    }.items():
        if value not in (None, ""):
            planned[key] = value

    profile_input = str(planned.get("resource_profile", "XLarge") or "XLarge")
    profile_key = normalize_profile_name(profile_input)
    profile = RESOURCE_PROFILES.get(profile_key)
    if profile is None:
        fail(f"resource_profile must be one of: {', '.join(v['label'] for v in RESOURCE_PROFILES.values())}")
    planned["resource_profile"] = profile["label"]
    planned["queue"] = profile["queue"]
    planned["ncpus"] = profile["ncpus"]
    planned["memory"] = profile["memory"]

    require_safe_value("repository_url", planned["repository_url"])
    require_safe_value("recipes_ref", planned["recipes_ref"])
    require_safe_value("project", planned["project"])
    require_safe_value("queue", planned["queue"])
    require_safe_value("walltime", planned["walltime"], SAFE_WALLTIME)
    require_safe_value("memory", planned["memory"], SAFE_RESOURCE)
    require_safe_value("storage", planned["storage"], SAFE_RESOURCE)
    require_safe_value("conda_module", planned["conda_module"])
    require_safe_value("module_base_path", planned["module_base_path"])
    planned["ncpus"] = int(planned.get("ncpus", 1))
    planned["poll_interval_seconds"] = int(planned.get("poll_interval_seconds", 120))
    planned["poll_timeout_minutes"] = int(planned.get("poll_timeout_minutes", 240))
    planned["execute_timeout_seconds"] = int(planned.get("execute_timeout_seconds", 3600))
    planned["notebook_roots"] = [require_safe_root(root) for root in planned.get("notebook_roots", [])]
    if not planned["notebook_roots"]:
        fail("at least one notebook root is required")
    planned["notebook_roots_arg"] = ":".join(planned["notebook_roots"])

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(planned, handle, indent=2, sort_keys=True)
        handle.write("\n")

    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            for key in [
                "repository_url", "recipes_ref", "resource_profile", "project", "queue", "walltime", "memory",
                "storage", "conda_module", "module_base_path", "poll_interval_seconds",
                "poll_timeout_minutes", "ncpus", "execute_timeout_seconds", "notebook_roots_arg",
            ]:
                handle.write(f"{key}={planned[key]}\n")
    else:
        print(json.dumps(planned, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
