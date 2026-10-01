from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_gadi_allocation import available_service_units


class AllocationTests(unittest.TestCase):
    def test_scaled_service_units(self) -> None:
        for value, expected in [
            ("0.00 SU", Decimal(0)),
            ("26.87 KSU", Decimal(26870)),
            ("9.97 MSU", Decimal(9970000)),
        ]:
            with self.subTest(value=value):
                self.assertEqual(available_service_units(f"    Avail:     {value}    \n"), expected)

    def test_missing_availability_fails(self) -> None:
        with self.assertRaises(ValueError):
            available_service_units("Grant: 10.00 MSU\n")


if __name__ == "__main__":
    unittest.main()
