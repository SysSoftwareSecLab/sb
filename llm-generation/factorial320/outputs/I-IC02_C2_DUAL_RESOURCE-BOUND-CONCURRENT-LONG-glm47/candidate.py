import asyncio
from bridge_robot_api import Robot, ActionReceipt, EventReceipt, MotionFault

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FIXTURE = "fixture"
    TOOL = "tool"
    GATE_EVENT = "rq2_gate"
    GAP_RESOURCES = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_SOURCE = "left_source"
    LEFT_TARGET = "left_target"
    LEFT_DEPART = "left_depart"
    RIGHT_HOME = "right_home"
    RIGHT_SOURCE = "right_source"
    RIGHT_TARGET = "right_target"
    RIGHT_DEPART = "right_depart"

    # Objects
    LEFT_PART = "left_part"
    RIGHT_PART = "right_part"

    # Timeout
    TIMEOUT = 30.0

    async def acquire_resources(arm: str):
        """Acquire fixture then tool. Ensures release on timeout."""
        acquired = []
        try:
            await robot.acquire(arm, FIXTURE, TIMEOUT)
            acquired.append(FIXTURE)
            await robot.acquire(arm, TOOL, TIMEOUT)
            acquired.append(TOOL)
        except Exception:
            # Release any acquired resources if failure occurs
            for res in acquired:
                try:
                    await robot.release_resource(arm, res)
                except Exception:
                    pass
            raise

    async def release_resources(arm: str):
        """Release tool then fixture."""
        await robot.release_resource(arm, TOOL)
        await robot.release_resource(arm, FIXTURE)

    async def worker(arm: str, home: str, source: str, target: str, depart: str, part: str):
        """Complete inherited dual-arm mission."""
        # 1. Acquire resources
        await acquire_resources(arm)

        # 2. Move to source
        await robot.move(arm, source, timeout_s=TIMEOUT)

        # 3. Grasp part
        await robot.grasp(arm, part)

        # 4. Move to target
        await robot.move(arm, target, timeout_s=TIMEOUT)

        # 5. Release part
        await robot.release(arm, part, target)

        # 6. Depart immediately
        await robot.move(arm, depart, timeout_s=TIMEOUT)

        # 7. Release resources
        await release_resources(arm)

    async def gate_producer():
        """Signal rq2_gate exactly once."""
        robot.signal(GATE_EVENT)

    async def gate_consumer():
        """Wait for rq2_gate exactly once."""
        await robot.wait_event(GATE_EVENT, TIMEOUT)

    async def gap_checker():
        """Acquire and release rq2_gap_0, rq2_gap_1, rq2_gap_2 once each with LEFT, in numeric order."""
        for res in GAP_RESOURCES:
            await robot.acquire(LEFT, res, TIMEOUT)
            await robot.release_resource(LEFT, res)

    # --- Main Execution Flow (Variant B: CONCURRENT) ---

    # 1. Launch Gate Producer
    producer_task = asyncio.create_task(gate_producer())

    # 2. Launch Gap Checker
    gap_task = asyncio.create_task(gap_checker())

    # 3. Wait for Gate Producer and Gap Checker to complete
    await producer_task
    await gap_task

    # 4. Wait for rq2_gate (Consumer)
    gate_receipt = await asyncio.create_task(gate_consumer())

    # 5. Execute Inherited Dual-Arm Mission Concurrently
    # Both workers run concurrently while rq2_gate is active
    left_worker = asyncio.create_task(worker(LEFT, LEFT_HOME, LEFT_SOURCE, LEFT_TARGET, LEFT_DEPART, LEFT_PART))
    right_worker = asyncio.create_task(worker(RIGHT, RIGHT_HOME, RIGHT_SOURCE, RIGHT_TARGET, RIGHT_DEPART, RIGHT_PART))

    await left_worker
    await right_worker

    # 6. Clear rq2_gate
    robot.clear_event(GATE_EVENT, expected_version=gate_receipt.version)
