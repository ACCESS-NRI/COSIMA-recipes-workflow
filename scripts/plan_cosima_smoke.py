#!/usr/bin/env python3
"""Plan a single COSIMA Recipes smoke-test run from a small JSON manifest."""
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


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def require_safe_path(path: str) -> str:
    if not path:
        fail("notebook path must not be empty")
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts:
        fail(f"unsafe notebook path: {path!r}")
    if p.suffix != ".ipynb":
        fail(f"notebook path must end in .ipynb: {path!r}")
    if not SAFE_VALUE.match(path):
        fail(f"notebook path contains unsupported characters: {path!r}")
    return p.as_posix()


def require_safe_value(label: str, value: str, pattern: re.Pattern[str] = SAFE_VALUE) -> str:
    if value is None or value == "":
        fail(f"{label} must not be empty")
    if not pattern.match(value):
        fail(f"{label} contains unsupported characters: {value!r}")
    return value


def sanitize_name(path: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", path).strip("-._")
    return safe or "notebook"


def load_manifest(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def merge(defaults: dict[str, Any], entry: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    planned = dict(defaults)
    planned.update(entry)
    for key, value in overrides.items():
        if value not in (None, ""):
            planned[key] = value
    return planned


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--notebook-path", required=True)
    parser.add_argument("--recipes-ref", default="")
    parser.add_argument("--conda-module", default="")
    parser.add_argument("--module-base-path", default="")
    parser.add_argument("--poll-timeout-minutes", default="")
    parser.add_argument("--out", default="planned-run.json")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    defaults = manifest.get("defaults", {})
    notebooks = manifest.get("notebooks", [])
    requested_path = require_safe_path(args.notebook_path)

    matches = [entry for entry in notebooks if entry.get("path") == requested_path]
    if not matches:
        known = ", ".join(entry.get("path", "<missing>") for entry in notebooks) or "<none>"
        fail(f"notebook {requested_path!r} is not in the Stage 1 manifest. Known notebooks: {known}")

    planned = merge(defaults, matches[0], {
        "recipes_ref": args.recipes_ref,
        "conda_module": args.conda_module,
        "module_base_path": args.module_base_path,
        "poll_timeout_minutes": args.poll_timeout_minutes,
    })
    planned["path"] = requested_path
    planned["safe_name"] = sanitize_name(requested_path)

    # Validate values passed to shell/PBS. This is intentionally conservative.
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
    planned["poll_interval_seconds"] = int(planned.get("poll_interval_seconds", 60))
    planned["poll_timeout_minutes"] = int(planned.get("poll_timeout_minutes", 45))

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(planned, handle, indent=2, sort_keys=True)
        handle.write("\n")

    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            for key in [
                "repository_url", "recipes_ref", "project", "queue", "walltime", "memory",
                "storage", "conda_module", "module_base_path", "path", "safe_name",
                "poll_interval_seconds", "poll_timeout_minutes", "ncpus",
            ]:
                handle.write(f"{key}={planned[key]}\n")
    else:
        print(json.dumps(planned, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
