from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AllRecipesSummaryTests(unittest.TestCase):
    def test_poll_summary_contains_discovered_notebooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            results_dir = run_dir / "results"
            results_dir.mkdir()
            paths = ["02-Easy-Recipes/First.ipynb", "02-Easy-Recipes/Second.ipynb"]
            (run_dir / "notebooks.tsv").write_text(
                "".join(f"{i}\t{path}\tnotebook-{i}\n" for i, path in enumerate(paths, 1)),
                encoding="utf-8",
            )
            (results_dir / "all-recipes.submitted.json").write_text(
                json.dumps({"notebooks_manifest": str(run_dir / "notebooks.tsv"), "conda_module": "conda/analysis3"}),
                encoding="utf-8",
            )
            for i, path in enumerate(paths, 1):
                (results_dir / f"{i:03d}.result.json").write_text(
                    json.dumps({"notebook_path": path, "status": "passed"}), encoding="utf-8"
                )
            summary_path = results_dir / "all-recipes.summary.json"
            subprocess.run(
                [
                    "bash",
                    str(ROOT / "scripts/gadi_poll_cosima_all_recipes.sh"),
                    str(run_dir),
                    str(summary_path),
                    "2",
                    "0",
                    "1",
                    "1.gadi-pbs,2.gadi-pbs",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            summary = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["notebook_paths"], paths)
        self.assertEqual(summary["conda_module"], "conda/analysis3")

    def test_missing_result_reports_pbs_jobfs_termination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "results").mkdir()
            (run_dir / "logs").mkdir()
            (run_dir / "notebooks.tsv").write_text("1\tExample.ipynb\texample\n", encoding="utf-8")
            (run_dir / "logs" / "all-recipes.001.pbs.out").write_text(
                "Job 1.gadi-pbs killed due to exceeding jobfs quota. Quota: 100MB, Used: 1GB\n",
                encoding="utf-8",
            )
            (run_dir / "logs" / "all-recipes.001.pbs.out.jobfs100").write_text(
                "Job 2.gadi-pbs killed due to exceeding jobfs quota. Quota: 100GB, Used: 117GB\n",
                encoding="utf-8",
            )
            summary_path = run_dir / "results" / "all-recipes.summary.json"
            completed = subprocess.run(
                ["bash", str(ROOT / "scripts/gadi_poll_cosima_all_recipes.sh"),
                 str(run_dir), str(summary_path), "1", "0", "1", "1.gadi-pbs"],
                capture_output=True, text=True, timeout=10,
            )
            summary = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertIn(completed.returncode, (4, 124))
        self.assertEqual(summary["missing_count"], 1)
        self.assertEqual(summary["results"][0]["status"], "missing-result")
        self.assertEqual(summary["failure_types"], {"PBSJobKilled": 1})
        self.assertIn("Quota: 100GB", summary["failed_notebooks"][0]["failure_summary"])

    def test_job_summary_python_block_compiles(self) -> None:
        lines = (ROOT / ".github/workflows/cosima-all-recipes.yml").read_text(encoding="utf-8").splitlines()
        start = lines.index('          python3 - <<\'PY\' >> "$GITHUB_STEP_SUMMARY"') + 1
        end = lines.index("          PY", start)
        code = "\n".join(line[10:] for line in lines[start:end]) + "\n"
        compile(code, "all-recipes-job-summary", "exec")

    def test_job_summary_reports_failed_notebook(self) -> None:
        lines = (ROOT / ".github/workflows/cosima-all-recipes.yml").read_text(encoding="utf-8").splitlines()
        start = lines.index("      - name: Write job summary")
        run_start = lines.index("        run: |", start) + 1
        script = "\n".join(line[10:] for line in lines[run_start:]) + "\n"
        script = re.sub(r"\$\{\{.*?\}\}", "sample", script)
        script = script.replace("status='sample'", "status='failed'")
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            (work_dir / "summary.json").write_text(
                json.dumps({"failed_notebooks": [{"notebook_path": "Example.ipynb", "exception_type": "ValueError", "exception_message": "synthetic failure"}]}),
                encoding="utf-8",
            )
            summary_path = work_dir / "step-summary.md"
            completed = subprocess.run(
                ["bash", "-c", script],
                cwd=work_dir,
                env={**os.environ, "GITHUB_STEP_SUMMARY": str(summary_path)},
                capture_output=True,
                text=True,
                timeout=10,
            )
            step_summary = summary_path.read_text(encoding="utf-8")

        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn("Example.ipynb", step_summary)
        self.assertIn("ValueError", step_summary)
        self.assertIn("synthetic failure", step_summary)


if __name__ == "__main__":
    unittest.main()
