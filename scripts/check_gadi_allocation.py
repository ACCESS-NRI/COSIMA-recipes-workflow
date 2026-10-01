#!/usr/bin/env python3
"""Fail if an NCI project has no available compute service units."""
from __future__ import annotations

import argparse
import re
from decimal import Decimal
from pathlib import Path


def available_service_units(report: str) -> Decimal:
    match = re.search(r"^\s*Avail:\s*([\d,]+(?:\.\d+)?)\s+([KM]?)SU\s*$", report, re.MULTILINE)
    if not match:
        raise ValueError("Could not read available service units from nci_account output")
    multiplier = {"": 1, "K": 1000, "M": 1000000}[match.group(2)]
    return Decimal(match.group(1).replace(",", "")) * multiplier


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    available = available_service_units(args.report.read_text(encoding="utf-8"))
    if available <= 0:
        raise SystemExit("No service units available for the configured PBS project; skipping notebook submissions")
    print(f"Available service units: {available}")


if __name__ == "__main__":
    main()
