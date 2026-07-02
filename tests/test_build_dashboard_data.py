from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_dashboard_data as dashboard


class BuildDashboardDataTests(unittest.TestCase):
    def test_parse_manifest_and_infer_styles(self) -> None:
        recipes = dashboard.parse_recipe_manifest(Path(".github/configs/cosima-all-recipes.yml"))
        self.assertGreaterEqual(len(recipes), 30)
        barotropic = next(item for item in recipes if item["path"] == "02-Easy-Recipes/Barotropic_Streamfunction.ipynb")
        self.assertIs(barotropic["enabled"], True)
        self.assertEqual(dashboard.style_for_path(barotropic["path"])["style"], "easy")

    def test_build_dashboard_data_with_summary(self) -> None:
        summary = {
            "status": "failed",
            "pbs_job_id": "123.gadi-pbs",
            "conda_module": "conda/analysis3-26.04",
            "expected_count": 38,
            "completed_count": 1,
            "passed_count": 0,
            "failed_count": 1,
            "missing_count": 37,
            "generated_at": "2026-07-02T00:00:00+00:00",
            "results": [
                {
                    "status": "failed",
                    "exit_code": 1,
                    "notebook_path": "02-Easy-Recipes/Barotropic_Streamfunction.ipynb",
                    "conda_module": "conda/analysis3-26.04",
                    "duration_seconds": 42,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "summary.json"
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            data = dashboard.build_dashboard(
                Path(".github/configs/cosima-all-recipes.json"),
                Path(".github/configs/cosima-all-recipes.yml"),
                [str(summary_path)],
            )

        self.assertEqual(data["default_environment"], "conda/analysis3")
        self.assertIn("conda/analysis3-26.04", data["environments"])
        recipe = next(item for item in data["recipes"] if item["path"] == "02-Easy-Recipes/Barotropic_Streamfunction.ipynb")
        self.assertEqual(recipe["statuses"]["conda/analysis3-26.04"]["status"], "failed")
        self.assertEqual(recipe["statuses"]["conda/analysis3"]["status"], "not-run")


if __name__ == "__main__":
    unittest.main()
