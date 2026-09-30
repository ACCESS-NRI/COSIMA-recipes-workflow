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
            "resource_profile": "CLarge",
            "queue": "normalbw",
            "walltime": "02:00:00",
            "memory": "32GB",
            "ncpus": 7,
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

        self.assertEqual(data["default_environment"], "conda/analysis3-26.04")
        self.assertEqual(data["environments"], ["conda/analysis3-26.04"])
        recipe = next(item for item in data["recipes"] if item["path"] == "02-Easy-Recipes/Barotropic_Streamfunction.ipynb")
        self.assertEqual(recipe["statuses"]["conda/analysis3-26.04"]["status"], "failed")
        run = data["runs"][0]
        self.assertEqual(run["resource_profile"], "CLarge")
        self.assertEqual(run["queue"], "normalbw")
        self.assertEqual(run["memory"], "32GB")
        self.assertEqual(run["ncpus"], 7)

    def test_discovered_notebooks_replace_stale_manifest_and_show_missing_results(self) -> None:
        new_path = "03-Advanced-Recipes/Horizontal_Regridding_Compare_Resolutions.ipynb"
        missing_path = "01-Cooking-Tutorials/02-Advanced/CFxarray_and_Pint.ipynb"
        summary = {
            "status": "missing-result",
            "conda_module": "conda/analysis3",
            "notebook_paths": [new_path, missing_path],
            "results": [{"notebook_path": new_path, "status": "passed"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "summary.json"
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            data = dashboard.build_dashboard(
                Path(".github/configs/cosima-all-recipes.json"),
                Path(".github/configs/cosima-all-recipes.yml"),
                [str(summary_path)],
            )

        self.assertEqual([recipe["path"] for recipe in data["recipes"]], [new_path, missing_path])
        self.assertEqual(data["recipes"][0]["statuses"]["conda/analysis3"]["status"], "passed")
        self.assertEqual(data["recipes"][1]["statuses"]["conda/analysis3"]["status"], "missing-result")

    def test_six_selected_versions_include_missing_summary(self) -> None:
        modules = [f"conda/analysis3-26.{month:02d}" for month in range(5, 11)]
        path = "02-Easy-Recipes/Barotropic_Streamfunction.ipynb"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            versions_path = root / "analysis3-versions.json"
            versions_path.write_text(json.dumps(modules), encoding="utf-8")
            summary_paths = []
            for module, status in [(modules[0], "failed"), (modules[-1], "passed")]:
                summary_path = root / f"{module.rsplit('-', 1)[-1]}.json"
                summary_path.write_text(json.dumps({
                    "conda_module": module,
                    "status": status,
                    "notebook_paths": [path],
                    "results": [{"notebook_path": path, "status": status}],
                }), encoding="utf-8")
                summary_paths.append(str(summary_path))
            data = dashboard.build_dashboard(
                Path(".github/configs/cosima-all-recipes.json"),
                Path(".github/configs/cosima-all-recipes.yml"),
                summary_paths,
                versions_path,
            )

        self.assertEqual(data["environments"], list(reversed(modules)))
        self.assertEqual(data["default_environment"], modules[-1])
        self.assertEqual(len(data["recipes"]), 1)
        statuses = data["recipes"][0]["statuses"]
        self.assertEqual(statuses[modules[-1]]["status"], "passed")
        self.assertEqual(statuses[modules[0]]["status"], "failed")
        self.assertEqual(statuses[modules[2]]["status"], "not-run")


if __name__ == "__main__":
    unittest.main()
