"""Small deterministic unit checks for the analytic geometry primitives."""
import unittest

from dynamic_geometry_v01 import (
    _distance_disagrees,
    _monotonic_departure,
    _subtract_permissions,
    box_signed_distance,
    swept_aabb,
)


class DynamicGeometryPrimitiveTests(unittest.TestCase):
    def test_stationary_separation(self):
        self.assertIsNone(swept_aabb([0, 0, 0], [0, 0, 0], [1, 0, 0], [1, 0, 0],
                                     [0.1, 0.1, 0.1], [0.1, 0.1, 0.1]))

    def test_opposing_affine_contact_interval(self):
        interval = swept_aabb([-1, 0, 0], [1, 0, 0], [1, 0, 0], [-1, 0, 0],
                              [0.1, 0.1, 0.1], [0.1, 0.1, 0.1])
        self.assertAlmostEqual(interval[0], 0.45)
        self.assertAlmostEqual(interval[1], 0.55)

    def test_aabb_signed_distance(self):
        self.assertAlmostEqual(box_signed_distance([0, 0, 0], [0.5, 0, 0],
                                                   [0.1, 0.1, 0.1], [0.2, 0.1, 0.1]), 0.2)
        self.assertLess(box_signed_distance([0, 0, 0], [0.1, 0, 0],
                                            [0.1, 0.1, 0.1], [0.2, 0.1, 0.1]), 0)

    def test_permission_subtraction_does_not_extend_after_clearance(self):
        self.assertEqual(_subtract_permissions([2.5, 4.0], [(2.5, 2.6, "DEPARTURE")]),
                         [[2.6, 4.0]])

    def test_point_permission_is_exact(self):
        self.assertEqual(_subtract_permissions([1.0, 1.0], [(1.0, 1.0, "POINT")]), [])
        self.assertEqual(_subtract_permissions([1.1, 1.1], [(1.0, 1.0, "POINT")]), [[1.1, 1.1]])

    def test_bullet_distance_gate(self):
        self.assertFalse(_distance_disagrees(0.2, 0.2 + 1e-8))
        self.assertTrue(_distance_disagrees(-0.1, 0.01))

    def test_zero_displacement_is_not_departure(self):
        self.assertFalse(_monotonic_departure([0, 0, 0], [0, 0, 0], [0, 0, 0]))

    def test_nonzero_outward_motion_is_monotonic(self):
        self.assertTrue(_monotonic_departure([0, 0, 0], [0.2, 0, 0], [0, 0, 0]))


if __name__ == "__main__":
    unittest.main()
