import unittest
from electrical import analyze_dc


class TestDCAnalyzer(unittest.TestCase):
    def test_known_values(self):
        result = analyze_dc(12, 6)
        self.assertAlmostEqual(result["current_a"], 2.0)
        self.assertAlmostEqual(result["power_w"], 24.0)

    def test_zero_voltage(self):
        result = analyze_dc(0, 10)
        self.assertAlmostEqual(result["current_a"], 0.0)
        self.assertAlmostEqual(result["power_w"], 0.0)

    def test_parallel_resistors(self):
        result = analyze_dc(12, [6, 3], "parallel")
        self.assertAlmostEqual(result["equivalent_resistance_ohm"], 2.0)
        self.assertAlmostEqual(result["total_current_a"], 6.0)
        self.assertEqual(result["branch_currents_a"], [2.0, 4.0])
        self.assertEqual(result["branch_powers_w"], [24.0, 48.0])

    def test_zero_resistance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Resistance cannot be zero"):
            analyze_dc(12, 0)

        with self.assertRaisesRegex(ValueError, "Resistance cannot be zero"):
            analyze_dc(12, [6, 0], "parallel")

    def test_negative_resistance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            analyze_dc(12, -6)

        with self.assertRaisesRegex(ValueError, "greater than zero"):
            analyze_dc(12, [6, -3], "parallel")


if __name__ == "__main__":
    unittest.main()