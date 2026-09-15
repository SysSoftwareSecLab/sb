import asyncio

async def run_task(robot):
    """
    Task: C5_INDEPENDENT-CONCURRENT-L0
    Structure: Fork/Join of two independent release lifecycles.
    Goal: Both parts at their own target; both arms at departure and empty.
    """

    # Define constants based on PUBLIC TASK
    # Arms
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"

    # Poses
    LEFT_HOME = "left_home"
    LEFT_SOURCE = "left_source"
    LEFT_TARGET = "left_target"
    LEFT_DEPART = "left_depart"

    RIGHT_HOME = "right_home"
    RIGHT_SOURCE = "right_source"
    RIGHT_TARGET = "right_target"
    RIGHT_DEPART = "right_depart"

    # Support Zones (logical_supports)
    # Note: Source and Target poses are valid support zones in this task
    ZONE_LEFT_SOURCE = LEFT_SOURCE
    ZONE_LEFT_TARGET = LEFT_TARGET
    ZONE_RIGHT_SOURCE = RIGHT_SOURCE
    ZONE_RIGHT_TARGET = RIGHT_TARGET

    # Helper coroutine for the LEFT arm lifecycle
    async def run_left_lane():
        # 1. Approach: Move from home to source
        await robot.move(LEFT, LEFT_SOURCE)

        # 2. Grasp: Pick up the part
        # No observation required by task spec for this grasp
        await robot.grasp(LEFT, LEFT_PART)

        # 3. Transport: Move from source to target
        await robot.move(LEFT, LEFT_TARGET)

        # 4. Release: Place the part at the target
        await robot.release(LEFT, LEFT_PART, ZONE_LEFT_TARGET)

        # 5. Depart: Immediate separating departure
        await robot.move(LEFT, LEFT_DEPART)

    # Helper coroutine for the RIGHT arm lifecycle
    async def run_right_lane():
        # 1. Approach: Move from home to source
        await robot.move(RIGHT, RIGHT_SOURCE)

        # 2. Grasp: Pick up the part
        await robot.grasp(RIGHT, RIGHT_PART)

        # 3. Transport: Move from source to target
        await robot.move(RIGHT, RIGHT_TARGET)

        # 4. Release: Place the part at the target
        await robot.release(RIGHT, RIGHT_PART, ZONE_RIGHT_TARGET)

        # 5. Depart: Immediate separating departure
        await robot.move(RIGHT, RIGHT_DEPART)

    # Execute both lanes concurrently to satisfy the CONCURRENT structure
    await asyncio.gather(
        run_left_lane(),
        run_right_lane()
    )
