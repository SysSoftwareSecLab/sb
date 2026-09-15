from __future__ import annotations

import unittest

from analyze_rq2 import condition_metrics, holm_adjust, program_metrics


class AnalysisTests(unittest.TestCase):
    def test_seed_denominator_is_not_reweighted_by_trace_hash(self):
        rows = [
            {"schedule_hash": "a", "P": "V", "lifecycle_complete": True, "cleanup_ok": True},
            {"schedule_hash": "a", "P": "V", "lifecycle_complete": True, "cleanup_ok": True},
            {"schedule_hash": "b", "P": "C", "lifecycle_complete": True, "cleanup_ok": True},
        ]
        result = condition_metrics(rows)
        self.assertEqual(result["distinct_interleavings"], 2)
        self.assertEqual(result["protocol_seed_V_incidence"], 2 / 3)
        self.assertEqual(result["distinct_trace_type_V_rate"], 0.5)

    def test_factorial_contrasts(self):
        risks = {"SERIAL_SHORT": "C", "SERIAL_LONG": "C", "CONCURRENT_SHORT": "V", "CONCURRENT_LONG": "V"}
        rows = []
        for condition, label in risks.items():
            schedule, distance = condition.split("_")
            rows.append({
                "slot_id": "s", "family_id": "f", "mechanism": "m", "profile": "p", "repeat": 1,
                "condition": condition, "schedule": schedule, "distance": distance, "seed": 0,
                "schedule_hash": condition, "P": label, "lifecycle_complete": True, "cleanup_ok": True,
            })
        result = program_metrics(rows)[0]["contrasts"]
        self.assertEqual(result["CONCURRENT_MINUS_SERIAL"], 1.0)
        self.assertEqual(result["LONG_MINUS_SHORT"], 0.0)
        self.assertEqual(result["CONCURRENCY_BY_DISTANCE_INTERACTION"], 0.0)

    def test_holm_is_monotone_in_order(self):
        adjusted = holm_adjust({"a": 0.01, "b": 0.03, "c": 0.2})
        self.assertEqual(adjusted["a"], 0.03)
        self.assertEqual(adjusted["b"], 0.06)
        self.assertEqual(adjusted["c"], 0.2)


if __name__ == "__main__":
    unittest.main()
