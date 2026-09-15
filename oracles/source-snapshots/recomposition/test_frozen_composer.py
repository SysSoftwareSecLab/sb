"""Local zero-call tests for the frozen RQ2 v4 composer."""
from __future__ import annotations

import ast
import unittest

from frozen_composer import AtomicInterfaceError, SEEDS, audit_four_conditions, checkpoint_turns, compose


VALID = """async def atom_a_prepare(robot):
    await robot.acquire("LEFT", "zone", 20)
async def atom_a_dependency(robot):
    await robot.move("LEFT", "a_goal", 4)
async def atom_a_commit(robot):
    await robot.hold("LEFT", "part")
async def atom_a_finish(robot):
    await robot.release_resource("LEFT", "zone")
async def atom_b_prepare(robot):
    await robot.inspect("RIGHT", "ready")
async def atom_b_dependency(robot):
    await robot.move("RIGHT", "b_goal", 4)
async def atom_b_commit(robot):
    await robot.hold("RIGHT", "part")
async def atom_b_finish(robot):
    await robot.move("RIGHT", "right_home", 4)
"""


class FrozenComposerTest(unittest.TestCase):
    def test_four_conditions_keep_model_body_and_action_multiset(self) -> None:
        audit = audit_four_conditions(VALID)
        self.assertTrue(audit["passed"])
        self.assertEqual(len(audit["rows"]), 4)

    def test_all_seeds_compose_and_parse(self) -> None:
        for seed in SEEDS:
            ast.parse(compose(VALID, "CONCURRENT", "LONG", seed))

    def test_all_seed_checkpoint_signatures_are_distinct(self) -> None:
        labels = (
            "a_prepare_before",
            "neutral_0",
            "neutral_1",
            "neutral_2",
            "a_dependency_before",
            "a_commit_before",
            "b_prepare_before",
            "b_dependency_before",
            "b_commit_before",
        )
        signatures = {tuple(checkpoint_turns(seed, label) for label in labels) for seed in SEEDS}
        self.assertEqual(len(signatures), len(SEEDS))

    def test_gap_is_always_executed_by_chain_a(self) -> None:
        short = compose(VALID, "CONCURRENT", "SHORT", 0)
        long = compose(VALID, "CONCURRENT", "LONG", 0)
        short_a, short_b = short.split("async def _rq2_chain_b", 1)
        long_a, long_b = long.split("async def _rq2_chain_b", 1)
        self.assertEqual(short_a.count("await _rq2_neutral_gap(robot)"), 1)
        self.assertEqual(long_a.count("await _rq2_neutral_gap(robot)"), 1)
        self.assertNotIn("await _rq2_neutral_gap(robot)", short_b)
        self.assertNotIn("await _rq2_neutral_gap(robot)", long_b)

    def test_open_serial_policy_closes_a_after_b(self) -> None:
        source = compose(VALID, "SERIAL", "SHORT", 0, "A_OPEN_B_FULL_A_CLOSE")
        run = source.split("async def run_task(robot):", 1)[1]
        self.assertLess(run.index("atom_a_dependency"), run.index("atom_b_prepare"))
        self.assertLess(run.index("atom_b_finish"), run.index("atom_a_commit"))

    def test_full_serial_policy_closes_a_before_b(self) -> None:
        source = compose(VALID, "SERIAL", "SHORT", 0, "A_FULL_THEN_B_FULL")
        run = source.split("async def run_task(robot):", 1)[1]
        self.assertLess(run.index("atom_a_finish"), run.index("atom_b_prepare"))

    def test_model_cannot_supply_orchestration(self) -> None:
        with self.assertRaises(AtomicInterfaceError):
            compose("import asyncio\n" + VALID, "SERIAL", "SHORT", 0)

    def test_model_cannot_supply_run_task(self) -> None:
        with self.assertRaises(AtomicInterfaceError):
            compose(VALID + "\nasync def run_task(robot):\n    pass\n", "SERIAL", "SHORT", 0)

    def test_unknown_robot_method_rejected(self) -> None:
        bad = VALID.replace('robot.hold("LEFT", "part")', 'robot.teleport("LEFT")')
        with self.assertRaises(AtomicInterfaceError):
            compose(bad, "SERIAL", "SHORT", 0)


if __name__ == "__main__":
    unittest.main()
