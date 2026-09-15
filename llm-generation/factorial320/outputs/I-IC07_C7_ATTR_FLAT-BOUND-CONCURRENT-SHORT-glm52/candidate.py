import asyncio
from bridge_robot_api import Robot


async def run_task(robot: Robot) -> None:
    # ---- constants from PUBLIC TASK ----
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    POSE_LEFT_HOME = "left_home"
    POSE_LEFT_WAIT = "left_wait"
    POSE_RIGHT_HOME = "right_home"
    POSE_RIGHT_WAIT = "right_wait"
    POSE_SOURCE_0 = "source_0"
    POSE_SOURCE_1 = "source_1"
    POSE_BUFFER_0 = "buffer_0"
    POSE_BUFFER_1 = "buffer_1"
    POSE_TARGET_0 = "target_0"
    POSE_TARGET_1 = "target_1"

    PART_0 = "part_0"
    PART_1 = "part_1"

    RES_BUFFER_LOCK = "buffer_lock"
    RES_TOOL = "tool"
    RES_RQ2_GAP_0 = "rq2_gap_0"
    RES_RQ2_GAP_1 = "rq2_gap_1"
    RES_RQ2_GAP_2 = "rq2_gap_2"

    EVT_EMPTY_0 = "empty_0"
    EVT_READY_0 = "ready_0"
    EVT_READY_1 = "ready_1"
    EVT_RQ2_GATE = "rq2_gate"

    FACT_LINE_CLEAR = "line_clear"
    FACT_RECEIVER_READY = "receiver_ready"

    MODE_OFF = "OFF"

    MOVE_TIMEOUT = 4
    ACQUIRE_TIMEOUT = 5

    # ---- helpers ----
    async def move(arm: str, pose: str, receipt=None) -> None:
        await robot.move(arm, pose, timeout_s=MOVE_TIMEOUT, receipt=receipt)

    async def acquire(arm: str, resource_id: str) -> None:
        await robot.acquire(arm, resource_id, ACQUIRE_TIMEOUT)

    async def release_resource_off(arm: str, resource_id: str) -> None:
        await robot.set_mode(arm, resource_id, MODE_OFF)
        await robot.release_resource(arm, resource_id)

    # ---- LEFT producer episode for one part ----
    async def producer_episode(part_id: str, src_pose: str, buf_pose: str,
                               ready_evt: str, empty_evt: str) -> None:
        # tool ownership from before source pickup through ready publication
        await acquire(LEFT, RES_TOOL)

        # approach source from left_home; immediately grasp
        await move(LEFT, src_pose)
        await robot.grasp(LEFT, part_id)

        # carry to buffer; supply the matching active ready receipt on carried move
        ready_receipt = await robot.wait_event(ready_evt, ACQUIRE_TIMEOUT)
        await acquire(LEFT, RES_BUFFER_LOCK)
        await move(LEFT, buf_pose, receipt=ready_receipt)

        # release on buffer and immediately depart
        await robot.release(LEFT, part_id, buf_pose)
        await move(LEFT, POSE_LEFT_HOME)
        await release_resource_off(LEFT, RES_BUFFER_LOCK)

        # publish ready after departing buffer
        robot.signal(ready_evt, part_id)

        # release tool on every exit
        await release_resource_off(LEFT, RES_TOOL)

        # producer waits and clears empty_0 before entering buffer with second part
        empty_receipt = await robot.wait_event(empty_evt, ACQUIRE_TIMEOUT)
        robot.clear_event(empty_evt, expected_version=empty_receipt.version)

    # ---- RIGHT consumer episode for one part ----
    async def consumer_episode(part_id: str, buf_pose: str, tgt_pose: str,
                               ready_evt: str, empty_evt: str) -> None:
        # wait corresponding ready receipt before pickup
        ready_receipt = await robot.wait_event(ready_evt, ACQUIRE_TIMEOUT)

        # approach buffer from right_home; immediately grasp
        await acquire(RIGHT, RES_BUFFER_LOCK)
        await move(RIGHT, buf_pose)
        await robot.grasp(RIGHT, part_id, observation=ready_receipt)
        await move(RIGHT, POSE_RIGHT_HOME)
        await release_resource_off(RIGHT, RES_BUFFER_LOCK)

        # carried move to target supplies that exact active item receipt
        await move(RIGHT, tgt_pose, receipt=ready_receipt)

        # release on target and depart before publishing empty_0
        await robot.release(RIGHT, part_id, tgt_pose)
        await move(RIGHT, POSE_RIGHT_HOME)

        # clear ready after carried move
        robot.clear_event(ready_evt, expected_version=ready_receipt.version)

        # publish empty_0 after departing target
        robot.signal(empty_evt, part_id)

    # ---- LEFT side: A alternates complete producer/consumer episodes ----
    async def left_side() -> None:
        # episode 1: producer for part_0
        await producer_episode(PART_0, POSE_SOURCE_0, POSE_BUFFER_0,
                               EVT_READY_0, EVT_EMPTY_0)

        # transition to left_wait for part_1 source approach
        await move(LEFT, POSE_LEFT_WAIT)

        # episode 2: producer for part_1
        await producer_episode(PART_1, POSE_SOURCE_1, POSE_BUFFER_1,
                               EVT_READY_1, EVT_EMPTY_0)

        # return home
        await move(LEFT, POSE_LEFT_HOME)

    # ---- RIGHT side: B runs producer and consumer coroutines together ----
    async def right_side() -> None:
        async def producer_for_part_1() -> None:
            # wait and clear empty_0, then inspect both readiness facts
            empty_receipt = await robot.wait_event(EVT_EMPTY_0, ACQUIRE_TIMEOUT)
            robot.clear_event(EVT_EMPTY_0, expected_version=empty_receipt.version)

            # C7 checks serially and C8 joins the two checks inside the loop branch
            await robot.inspect(RIGHT, FACT_LINE_CLEAR)
            await robot.inspect(RIGHT, FACT_RECEIVER_READY)

            # approach source_1 from right_wait; immediately grasp
            await acquire(RIGHT, RES_TOOL)
            await move(RIGHT, POSE_SOURCE_1)
            await robot.grasp(RIGHT, PART_1)

            # carry to buffer_1; supply matching ready receipt on carried move
            ready_receipt = await robot.wait_event(EVT_READY_1, ACQUIRE_TIMEOUT)
            await acquire(RIGHT, RES_BUFFER_LOCK)
            await move(RIGHT, POSE_BUFFER_1, receipt=ready_receipt)

            # release on buffer and immediately depart
            await robot.release(RIGHT, PART_1, POSE_BUFFER_1)
            await move(RIGHT, POSE_RIGHT_WAIT)
            await release_resource_off(RIGHT, RES_BUFFER_LOCK)

            # publish ready_1 after departing buffer
            robot.signal(EVT_READY_1, PART_1)

            # release tool on every exit
            await release_resource_off(RIGHT, RES_TOOL)

        async def consumer_for_part_0() -> None:
            await consumer_episode(PART_0, POSE_BUFFER_0, POSE_TARGET_0,
                                    EVT_READY_0, EVT_EMPTY_0)

        async def consumer_for_part_1() -> None:
            await consumer_episode(PART_1, POSE_BUFFER_1, POSE_TARGET_1,
                                    EVT_READY_1, EVT_EMPTY_0)

        # B runs producer and consumer coroutines together
        await asyncio.gather(
            producer_for_part_1(),
            consumer_for_part_0(),
            consumer_for_part_1(),
        )

    # ---- rq2_gate protected scope: gap checks, signal, wait, mission, clear ----
    async def rq2_gate_scope() -> None:
        # acquire and release rq2_gap_0/1/2 once each with LEFT, in numeric order
        await acquire(LEFT, RES_RQ2_GAP_0)
        await release_resource_off(LEFT, RES_RQ2_GAP_0)
        await acquire(LEFT, RES_RQ2_GAP_1)
        await release_resource_off(LEFT, RES_RQ2_GAP_1)
        await acquire(LEFT, RES_RQ2_GAP_2)
        await release_resource_off(LEFT, RES_RQ2_GAP_2)

        # complete all three rq2_gap resource checks before signalling rq2_gate
        robot.signal(EVT_RQ2_GATE)

        # wait immediately after the signal
        gate_receipt = await robot.wait_event(EVT_RQ2_GATE, ACQUIRE_TIMEOUT)

        # keep rq2_gate active while executing the complete inherited dual-arm mission
        await asyncio.gather(left_side(), right_side())

        # clear only after the mission
        robot.clear_event(EVT_RQ2_GATE, expected_version=gate_receipt.version)

    await rq2_gate_scope()
