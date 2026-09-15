from __future__ import annotations

import json
from pathlib import Path
import unittest

from atomic_contract_oracle import required_steps, static_local_contract


HERE = Path(__file__).resolve().parent


class AtomicContractOracleTests(unittest.TestCase):
    def test_all_references_pass_static_contract(self):
        for task in json.loads((HERE / "REFERENCE_TASK_CATALOG.json").read_text()):
            spec = json.loads((HERE / task["spec_path"]).read_text())
            source = (HERE / task["reference_source_path"]).read_text()
            self.assertTrue(static_local_contract(source, spec)["passed"], task["family_id"])

    def test_all_families_have_both_dynamic_contracts(self):
        for task in json.loads((HERE / "REFERENCE_TASK_CATALOG.json").read_text()):
            spec = json.loads((HERE / task["spec_path"]).read_text())
            self.assertGreaterEqual(len(required_steps(spec, "A")), 4)
            self.assertGreaterEqual(len(required_steps(spec, "B")), 4)

    def test_wrong_arm_is_rejected(self):
        task = json.loads((HERE / "REFERENCE_TASK_CATALOG.json").read_text())[0]
        spec = json.loads((HERE / task["spec_path"]).read_text())
        source = (HERE / task["reference_source_path"]).read_text().replace(
            'robot.move("LEFT", "left_approach", 4)',
            'robot.move("RIGHT", "left_approach", 4)',
            1,
        )
        self.assertFalse(static_local_contract(source, spec)["passed"])

    def test_hidden_timeout_asymmetry_cannot_recur(self):
        task = json.loads((HERE / "REFERENCE_TASK_CATALOG.json").read_text())[0]
        spec = json.loads((HERE / task["spec_path"]).read_text())
        source = (HERE / task["reference_source_path"]).read_text().replace(
            'robot.move("LEFT", "left_approach", 4)',
            'robot.move("LEFT", "left_approach", 60)',
            1,
        )
        result = static_local_contract(source, spec)
        self.assertIn("atom_a_prepare:move:TIMEOUT_OUTSIDE_PUBLIC_RANGE", result["errors"])

    def test_required_call_cannot_move_to_another_hook(self):
        task = json.loads((HERE / "REFERENCE_TASK_CATALOG.json").read_text())[0]
        spec = json.loads((HERE / task["spec_path"]).read_text())
        source = (HERE / task["reference_source_path"]).read_text().replace(
            'async def atom_a_dependency(robot):\n    await robot.move("LEFT", "a_zone", 4)',
            'async def atom_a_dependency(robot):\n    pass',
            1,
        ).replace(
            'async def atom_a_commit(robot):',
            'async def atom_a_commit(robot):\n    await robot.move("LEFT", "a_zone", 4)',
            1,
        )
        result = static_local_contract(source, spec)
        self.assertIn("atom_a_dependency:REQUIRED_HOOK_CALLS_MISSING_OR_REORDERED", result["errors"])


if __name__ == "__main__":
    unittest.main()
