import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault


async def run_task(robot: Robot) -> None:
    # SHORT variant: LEFT acquires tool only after second-item wait and checks.
    # Layout L0: producer/consumer episodes alternate; B runs both coroutines together.

    async def producer() -> None:
        # Episode 0: part_0
        # LEFT at left_home -> source_0 (approach), grasp part_0
        await robot.move("LEFT", "source_0")
        await robot.grasp("LEFT", "part_0")
        # carry to buffer_0
        await robot.move("LEFT", "buffer_0")
        # acquire buffer_lock before buffer entry
        await robot.acquire("LEFT", "buffer_lock", 5)
        # release part_0 at buffer_0
        await robot.release("LEFT", "part_0", "buffer_0")
        # depart immediately before ready publication
        await robot.move("LEFT", "left_wait")
        # release lock
        await robot.release_resource("LEFT", "buffer_lock")
        # publish ready_0
        robot.signal("ready_0", "part_0")

        # Wait for empty_0 before second part
        # (empty_0 signaled by consumer after first pickup)
        # We need to wait for empty_0 receipt
        empty_receipt = await robot.wait_event("empty_0", 10)
        robot.clear_event("empty_0", expected_version=empty_receipt.version)

        # Second item: after exact empty_0 receipt waited and cleared,
        # inspect line_clear with LEFT and receiver_ready with RIGHT
        # D4: join them with asyncio.gather inside i == 1 loop branch
        obs_left, obs_right = await asyncio.gather(
            robot.inspect("LEFT", "line_clear"),
            robot.inspect("RIGHT", "receiver_ready"),
        )
        # Both public Boolean fields must permit transfer
        left_val = obs_left.value
        right_val = obs_right.value
        if not (isinstance(left_val, dict) and left_val.get("clear") is True):
            raise ContractError("line_clear not clear")
        if not (isinstance(right_val, dict) and right_val.get("ready") is True):
            raise ContractError("receiver_ready not ready")

        # SHORT: acquire tool only after second-item wait and checks
        await robot.acquire("LEFT", "tool", 5)

        # Episode 1: part_1
        # LEFT at left_wait -> source_1 (approach), grasp part_1
        await robot.move("LEFT", "source_1")
        await robot.grasp("LEFT", "part_1")
        # carry to buffer_1
        await robot.move("LEFT", "buffer_1")
        # acquire buffer_lock before buffer entry
        await robot.acquire("LEFT", "buffer_lock", 5)
        # release part_1 at buffer_1
        await robot.release("LEFT", "part_1", "buffer_1")
        # depart immediately before ready publication
        await robot.move("LEFT", "left_wait")
        # release lock
        await robot.release_resource("LEFT", "buffer_lock")
        # publish ready_1
        robot.signal("ready_1", "part_1")

        # Release tool on normal exit
        await robot.release_resource("LEFT", "tool")

    async def consumer() -> None:
        # Episode 0: part_0
        # Wait for ready_0
        ready0 = await robot.wait_event("ready_0", 10)
        # RIGHT at right_home -> buffer_0 (approach), grasp part_0
        await robot.move("RIGHT", "buffer_0")
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.grasp("RIGHT", "part_0")
        # depart buffer
        await robot.move("RIGHT", "right_wait")
        await robot.release_resource("RIGHT", "buffer_lock")
        # carried move to target_0 with exact active item receipt
        await robot.move("RIGHT", "target_0", receipt=ready0)
        # release on target
        await robot.release("RIGHT", "part_0", "target_0")
        # depart
        await robot.move("RIGHT", "right_home")
        # clear ready_0 after carried move
        robot.clear_event("ready_0", expected_version=ready0.version)
        # publish empty_0
        robot.signal("empty_0", "part_0")

        # Episode 1: part_1
        # Wait for ready_1
        ready1 = await robot.wait_event("ready_1", 10)
        # RIGHT at right_home -> buffer_1 (approach), grasp part_1
        await robot.move("RIGHT", "buffer_1")
        await robot.acquire("RIGHT", "buffer_lock", 5)
        await robot.grasp("RIGHT", "part_1")
        # depart buffer
        await robot.move("RIGHT", "right_wait")
        await robot.release_resource("RIGHT", "buffer_lock")
        # carried move to target_1 with exact active item receipt
        await robot.move("RIGHT", "target_1", receipt=ready1)
        # release on target
        await robot.release("RIGHT", "part_1", "target_1")
        # depart
        await robot.move("RIGHT", "right_home")
        # clear ready_1 after carried move
        robot.clear_event("ready_1", expected_version=ready1.version)
        # publish empty_0 (for second item completion)
        robot.signal("empty_0", "part_1")

    # B runs producer and consumer coroutines together
    await asyncio.gather(producer(), consumer())
