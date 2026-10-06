from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIN = "6278c5bf45924f756de9c00058eecdea0514d7ad"
CASES = (
    ("all", ROOT / ".github/configs/cosima-all-recipes.json", ROOT / "scripts/plan_cosima_all_recipes.py"),
    ("smoke", ROOT / ".github/configs/cosima-smoke.json", ROOT / "scripts/plan_cosima_smoke.py"),
)


class PinnedRecipesRefTests(unittest.TestCase):
    def plan(self, kind: str, script: Path, config: Path, output: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        args = [sys.executable, str(script)]
        if kind == "smoke":
            args += ["--manifest", str(config), "--notebook-path", "02-Easy-Recipes/Barotropic_Streamfunction.ipynb"]
        else:
            args += ["--config", str(config)]
        return subprocess.run(args + ["--out", str(output), *extra], capture_output=True, text=True)

    def test_both_planners_use_the_reviewed_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for kind, config, script in CASES:
                with self.subTest(kind=kind):
                    output = Path(tmp) / f"{kind}.json"
                    result = self.plan(kind, script, config, output)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(output.read_text())["recipes_ref"], PIN)

    def test_branch_config_and_dispatch_style_override_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for kind, config, script in CASES:
                with self.subTest(kind=kind):
                    altered = json.loads(config.read_text())
                    altered["defaults"]["recipes_ref"] = "main"
                    bad_config = Path(tmp) / f"{kind}-bad.json"
                    bad_config.write_text(json.dumps(altered))
                    output = Path(tmp) / f"{kind}.json"
                    result = self.plan(kind, script, bad_config, output)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("full lowercase 40-character commit SHA", result.stderr)
                    self.assertFalse(output.exists())

                    result = self.plan(kind, script, config, output, "--recipes-ref", "main")
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("unrecognized arguments", result.stderr)
                    self.assertFalse(output.exists())

    def test_gadi_submitters_reject_a_moving_ref_before_creating_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            all_args = [
                str(run_dir), "https://github.com/COSIMA/cosima-recipes.git", "main", "XLarge",
                "02-Easy-Recipes", "conda/analysis3-26.10", "/g/data/xp65/public/modules",
                "tm70", "normalbw", "02:00:00", "63GB", "14", "gdata/xp65", "100GB", "3600", "120",
            ]
            smoke_args = [
                str(run_dir), "https://github.com/COSIMA/cosima-recipes.git", "main",
                "02-Easy-Recipes/Barotropic_Streamfunction.ipynb", "conda/analysis3-26.10",
                "/g/data/xp65/public/modules", "tm70", "normal", "00:30:00", "4GB", "1", "gdata/xp65",
            ]
            for script, args in (
                ("gadi_submit_cosima_all_recipes.sh", all_args),
                ("gadi_submit_cosima_smoke.sh", smoke_args),
            ):
                with self.subTest(script=script):
                    result = subprocess.run(["bash", str(ROOT / "scripts" / script), *args], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("full lowercase 40-character commit SHA", result.stderr)
                    self.assertFalse(run_dir.exists())


if __name__ == "__main__":
    unittest.main()
