from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, ContractError, MotionFault
import asyncio


async def run_task(robot: Robot) -> None:
    # SERIAL structure: run producer and consumer coroutines together (variant B),
    # but the task_id says SERIAL-L0. The required_order says:
    # "A alternates complete producer/consumer episodes; B runs producer and consumer coroutines together."
    # variant is "A", so we alternate complete producer/consumer episodes serially.

    # Producer episode for part_0:
    #   LEFT: left_home -> source_0 (approach), grasp part_0
    #   LEFT: source_0 -> buffer_0 (carry), release part_0 at buffer_0, depart
    #   signal ready_0
    # Consumer episode for part_0:
    #   RIGHT: right_home -> buffer_0 (approach), grasp part_0 (with ready_0 receipt)
    #   RIGHT: buffer_0 -> target_0 (carry with receipt), release part_0 at target_0, depart
    #   clear ready_0
    #   signal empty_0
    # Producer waits empty_0, clears it, then part_1:
    #   LEFT: left_wait -> source_1 (approach), grasp part_1
    #   LEFT: source_1 -> buffer_1 (carry), release part_1 at buffer_1, depart
    #   signal ready_1
    # Consumer for part_1:
    #   RIGHT: right_wait -> buffer_1 (approach), grasp part_1 (with ready_1 receipt)
    #   RIGHT: buffer_1 -> target_1 (carry with receipt), release part_1 at target_1, depart
    #   clear ready_1
    #   signal empty_0 (again? or final)
    # Then return arms to homes.

    # Both participants own buffer_lock during buffer entry and departure.
    # So acquire buffer_lock before entering buffer, release after departing.

    # --- Episode 1: part_0 ---

    # Producer: LEFT approach source_0 from left_home
    await robot.move("LEFT", "source_0")
    obs0 = await robot.grasp("LEFT", "part_0")

    # Producer: carry to buffer_0, acquire lock first
    await robot.acquire("LEFT", "buffer_lock", 5.0)
    await robot.move("LEFT", "buffer_0")
    await robot.release("LEFT", "part_0", "buffer_0")
    # depart immediately
    await robot.move("LEFT", "left_wait")
    await robot.release_resource("LEFT", "buffer_lock")

    # publish ready_0
    ready0 = robot.signal("ready_0")

    # Consumer: RIGHT approach buffer_0 from right_home
    await robot.move("RIGHT", "buffer_0")
    # acquire lock during buffer entry
    await robot.acquire("RIGHT", "buffer_lock", 5.0)
    obs0c = await robot.grasp("RIGHT", "part_0", observation=obs0)
    # depart buffer immediately
    await robot.move("RIGHT", "right_wait")
    await robot.release_resource("RIGHT", "buffer_lock")

    # Consumer: carry to target_0 with ready_0 receipt
    await robot.move("RIGHT", "target_0", receipt=ready0)
    await robot.release("RIGHT", "part_0", "target_0")
    await robot.move("RIGHT", "right_home")

    # clear ready_0 after carried move
    robot.clear_event("ready_0", expected_version=ready0.version)

    # publish empty_0
    empty0 = robot.signal("empty_0")

    # Producer waits and clears empty_0 before entering buffer with second part
    empty0_recv = await robot.wait_event("empty_0", 5.0)
    robot.clear_event("empty_0", expected_version=empty0_recv.version)

    # --- Episode 2: part_1 ---

    # Producer: LEFT approach source_1 from left_wait
    await robot.move("LEFT", "source_1")
    obs1 = await robot.grasp("LEFT", "part_1")

    # Producer: carry to buffer_1, acquire lock
    await robot.acquire("LEFT", "buffer_lock", 5.0)
    await robot.move("LEFT", "buffer_1")
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_home")
    await robot.release_resource("LEFT", "buffer_lock")

    # publish ready_1
    ready1 = robot.signal("ready_1")

    # Consumer: RIGHT approach buffer_1 from right_wait
    await robot.move("RIGHT", "buffer_1")
    await robot.acquire("RIGHT", "buffer_lock", 5.0)
    obs1c = await robot.grasp("RIGHT", "part_1", observation=obs1)
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")

    # Consumer: carry to target_1 with ready_1 receipt
    await robot.move("RIGHT", "target_1", receipt=ready1)
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home")

    # clear ready_1
    robot.clear_event("ready_1", expected_version=ready1.version)

    # publish empty_0 final
    robot.signal("empty_0")
