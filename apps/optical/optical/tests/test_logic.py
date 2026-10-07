import unittest

from optical.utils.insurance import split_amounts
from optical.utils.optics import check_eye_values
from optical.utils.workflow import STAGES, enabled_stages, next_stage

ALL_ON = {k: 1 for k in (
    "enable_rx_verification", "enable_measurements_confirmation", "enable_preparation",
    "enable_laboratory", "enable_assembly", "enable_quality_control", "enable_customer_notification",
)}


class TestInsurance(unittest.TestCase):
    def test_percentage_only(self):
        self.assertEqual(split_amounts(1000, 80), (800.0, 200.0))

    def test_deductible(self):
        self.assertEqual(split_amounts(1000, 80, deductible=200), (640.0, 360.0))

    def test_max_coverage_cap(self):
        self.assertEqual(split_amounts(1000, 80, max_coverage=500), (500.0, 500.0))

    def test_deductible_larger_than_total(self):
        self.assertEqual(split_amounts(100, 100, deductible=500), (0.0, 100.0))

    def test_full_coverage_never_exceeds_total(self):
        self.assertEqual(split_amounts(300, 100, max_coverage=1000), (300.0, 0.0))

    def test_totals_always_add_up(self):
        ins, cust = split_amounts(1234.57, 66.6, 400, 50)
        self.assertAlmostEqual(ins + cust, 1234.57, places=2)


class TestWorkflow(unittest.TestCase):
    def test_full_flow(self):
        seen, cur = ["New"], "New"
        while next_stage(cur, ALL_ON):
            cur = next_stage(cur, ALL_ON)
            seen.append(cur)
        self.assertEqual(seen, STAGES)

    def test_skips_disabled_stages(self):
        flags = dict(ALL_ON, enable_laboratory=0, enable_assembly=0, enable_customer_notification=0)
        self.assertEqual(next_stage("Preparation", flags), "Quality Control")
        self.assertEqual(next_stage("Ready", flags), "Delivered")

    def test_minimal_shop(self):
        stages = enabled_stages({})
        self.assertEqual(stages, ["New", "Ready", "Delivered"])

    def test_terminal(self):
        self.assertIsNone(next_stage("Delivered", ALL_ON))


class TestOptics(unittest.TestCase):
    def test_valid_prescription(self):
        v = {"od_sph": -2.25, "od_cyl": -0.75, "od_axis": 180, "os_sph": -1.5, "os_pd": 31.5}
        self.assertEqual(check_eye_values(v), [])

    def test_axis_required_with_cylinder(self):
        codes = [e[0] for e in check_eye_values({"od_cyl": -1.0, "od_axis": 0})]
        self.assertIn("axis_required", codes)

    def test_bad_step(self):
        codes = [e[0] for e in check_eye_values({"os_sph": -2.30})]
        self.assertIn("step", codes)

    def test_sph_out_of_range(self):
        codes = [e[0] for e in check_eye_values({"od_sph": -35})]
        self.assertIn("range", codes)

    def test_empty_values_ignored(self):
        self.assertEqual(check_eye_values({"od_pd": 0, "od_add": 0, "od_axis": 0, "od_prism": None}), [])

    def test_binocular_pd_range(self):
        self.assertEqual(check_eye_values({"binocular_pd": 62}), [])
        self.assertTrue(check_eye_values({"binocular_pd": 120}))


if __name__ == "__main__":
    unittest.main()
