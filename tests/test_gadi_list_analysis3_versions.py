from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/gadi_list_analysis3_versions.sh"


class ListAnalysis3VersionsTests(unittest.TestCase):
    def test_selects_six_newest_numeric_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "conda"
            module_dir.mkdir()
            for name in [
                "analysis3-26.03", "analysis3-26.04", "analysis3-26.05",
                "analysis3-26.06", "analysis3-26.07", "analysis3-26.08",
                "analysis3-26.09", "analysis3-26.10", "analysis3-latest",
            ]:
                (module_dir / name).touch()
            result = subprocess.run(["bash", str(SCRIPT), tmp], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.splitlines(), [
            "26.05", "26.06", "26.07", "26.08", "26.09", "26.10",
        ])

    def test_fails_when_fewer_than_six_versions_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module_dir = Path(tmp) / "conda"
            module_dir.mkdir()
            (module_dir / "analysis3-26.10").touch()
            result = subprocess.run(["bash", str(SCRIPT), tmp], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("need six", result.stderr)


if __name__ == "__main__":
    unittest.main()
