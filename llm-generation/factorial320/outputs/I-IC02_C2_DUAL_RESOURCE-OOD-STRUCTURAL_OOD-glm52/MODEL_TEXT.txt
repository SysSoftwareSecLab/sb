```python
import asyncio

from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    """IC02_C2_DUAL_RESOURCE-OOD-STRUCTURAL_OOD, variant A (SERIAL, L0).

    Structural shape: FOR -> PAR_JOIN -> consumer IF.
    The loop directly contains the join; the consumer IF guards the
    complete inherited mission.
    """

    async def _worker(arm: str, part: str, source: str, target: str,
                      depart: str, home: str) -> None:
        # Inherited mission for one lane:
        # acquire fixture then tool, carry the part to target while owning
        # both, release and depart, then release tool and fixture.
        # try/finally releases every successfully acquired controller.
        acquired_fixture = False
        acquired_tool = False
        try:
            await robot.acquire(arm, "fixture", 5.0)
            acquired_fixture = True
            await robot.acquire(arm, "tool", 5.0)
            acquired_tool = True

            # Approach from declared start_pose (home) to interaction_pose
            # (source); immediately grasp in the same virtual moment.
            await robot.move(arm, home)
            await robot.move(arm, source)
            await robot.grasp(arm, part)

            # Carry the held part to its target while owning both
            # controllers, then release on the named support zone.
            await robot.move(arm, target)
            await robot.release(arm, part, target)

            # Immediate separating departure from the release pose.
            await robot.move(arm, depart)
        finally:
            if acquired_tool:
                await robot.release_resource(arm, "tool")
            if acquired_fixture:
                await robot.release_resource(arm, "fixture")

    async def _producer() -> None:
        # Producer: signal rq2_gate, making it active with a new version.
        robot.signal("rq2_gate")

    async def _consumer(receipt) -> None:
        # Consumer IF guards the complete mission. It waits the exact active
        # receipt, executes the complete inherited mission, then clears that
        # version.
        await robot.wait_event("rq2_gate", 5.0)
        if arm_receipt_match(receipt):
            await _worker("LEFT", "left_part", "left_source",
                           "left_target", "left_depart", "left_home")
            await _worker("RIGHT", "right_part", "right_source",
                          "right_target", "right_depart", "right_home")
            robot.clear_event("rq2_gate", expected_version=receipt.version)

    def arm_receipt_match(receipt) -> bool:
        # Guard predicate for the consumer IF.
        return getattr(receipt, "event_id", None) == "rq2_gate"

    # FOR: finite loop over the two lanes.
    for _ in range(2):
        # PAR_JOIN: concurrently join an rq2_gate producer and consumer.
        receipt_holder = {}

        async def _producer_capture() -> None:
            await _producer()
            # Capture the active receipt produced for the consumer.
            receipt_holder["receipt"] = robot.signal("rq2_gate")

        async def _consumer_capture() -> None:
            # Wait for the producer to make the receipt available.
            for _ in range(1000):
                if "receipt" in receipt_holder:
                    break
                await asyncio.sleep(0)
            receipt = receipt_holder.get("receipt")
            if receipt is not None:
                await _consumer(receipt)

        await asyncio.gather(_producer_capture(), _consumer_capture())
