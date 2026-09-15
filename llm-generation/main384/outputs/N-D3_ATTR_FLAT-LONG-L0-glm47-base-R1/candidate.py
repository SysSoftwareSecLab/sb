import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TOOL = "tool"
    BUFFER_LOCK = "buffer_lock"
    EMPTY_EVENT = "empty_0"
    
    # Items and Poses
    items = ["part_0", "part_1"]
    sources = {"part_0": "source_0", "part_1": "source_1"}
    targets = {"part_0": "target_0", "part_1": "target_1"}
    # buffer_0 and buffer_1 are the same physical location, used logically per item
    buffers = {"part_0": "buffer_0", "part_1": "buffer_1"}
    ready_events = {"part_0": "ready_0", "part_1": "ready_1"}
    
    # Homes and Waits
    left_home = "left_home"
    right_home = "right_home"
    left_wait = "left_wait"
    right_wait = "right_wait"

    # Helper to wait for event with timeout
    async def wait_for_event(event_id: str, timeout_s: float) -> EventReceipt:
        return await robot.wait_event(event_id, timeout_s)

    # Helper to clear event
    def clear_event_sync(event_id: str, receipt: EventReceipt):
        robot.clear_event(event_id, expected_version=receipt.version)

    # Helper to acquire tool
    async def acquire_tool(arm: str, timeout_s: float) -> ActionReceipt:
        return await robot.acquire(arm, TOOL, timeout_s)

    # Helper to release tool
    async def release_tool(arm: str) -> ActionReceipt:
        # Must be OFF to release
        await robot.set_mode(arm, TOOL, "OFF")
        return await robot.release_resource(arm, TOOL)

    # Helper to acquire buffer lock
    async def acquire_buffer_lock(arm: str, timeout_s: float) -> ActionReceipt:
        return await robot.acquire(arm, BUFFER_LOCK, timeout_s)

    # Helper to release buffer lock
    async def release_buffer_lock(arm: str) -> ActionReceipt:
        return await robot.release_resource(arm, BUFFER_LOCK)

    # --- Producer Coroutine (LEFT) ---
    async def producer():
        try:
            for i, item in enumerate(items):
                source = sources[item]
                buf = buffers[item]
                ready_evt = ready_events[item]
                
                # 1. Acquire tool (LONG: acquire before source pickup)
                # Timeout 4s is safe within 50s deadline
                await acquire_tool(LEFT, 4.0)
                
                # 2. Move to source and grasp
                # Approach sequence: left_home -> source_0 (part_0), left_wait -> source_1 (part_1)
                start_pose = left_home if i == 0 else left_wait
                await robot.move(LEFT, start_pose)
                obs = await robot.grasp(LEFT, item)
                
                # 3. Acquire buffer lock
                await acquire_buffer_lock(LEFT, 4.0)
                
                # 4. Move to buffer and release
                await robot.move(LEFT, buf)
                await robot.release(LEFT, item, buf)
                
                # 5. Depart buffer (immediately)
                # Move to wait pose for part_1, home for part_0 (to clear way)
                depart_pose = left_wait if i == 0 else left_home
                await robot.move(LEFT, depart_pose)
                
                # 6. Release buffer lock
                await release_buffer_lock(LEFT)
                
                # 7. Signal ready
                robot.signal(ready_evt, item)
                
                # 8. Release tool
                await release_tool(LEFT)
                
                # 9. Wait for empty_0 before entering buffer with second part
                if i == 0:
                    # Wait for consumer to signal empty_0
                    empty_receipt = await wait_for_event(EMPTY_EVENT, 20.0)
                    # Clear it
                    clear_event_sync(EMPTY_EVENT, empty_receipt)
                else:
                    # For part 1, we already waited and cleared empty_0 before loop start
                    pass
        finally:
            # Ensure tool is released on exit
            try:
                await release_tool(LEFT)
            except Exception:
                pass

    # --- Consumer Coroutine (RIGHT) ---
    async def consumer():
        try:
            for i, item in enumerate(items):
                buf = buffers[item]
                target = targets[item]
                ready_evt = ready_events[item]
                
                # 1. Wait for ready event
                ready_receipt = await wait_for_event(ready_evt, 20.0)
                
                # 2. Acquire tool (LONG: acquire before source pickup -> here before buffer pickup)
                await acquire_tool(RIGHT, 4.0)
                
                # 3. Acquire buffer lock
                await acquire_buffer_lock(RIGHT, 4.0)
                
                # 4. Move to buffer and grasp
                # Approach: right_home -> buffer_0 (part_0), right_wait -> buffer_1 (part_1)
                start_pose = right_home if i == 0 else right_wait
                await robot.move(RIGHT, start_pose)
                obs = await robot.grasp(RIGHT, item)
                
                # 5. Depart buffer (immediately)
                await robot.move(RIGHT, right_wait)
                
                # 6. Release buffer lock
                await release_buffer_lock(RIGHT)
                
                # 7. Perform checks for second item (D3: serial)
                if i == 1:
                    # Inspect line_clear with LEFT
                    # Note: LEFT is idle at left_home here
                    obs_lc = await robot.inspect(LEFT, "line_clear")
                    if not obs_lc.value.get("clear"):
                        raise ValueError("Line not clear")
                    
                    # Inspect receiver_ready with RIGHT
                    obs_rr = await robot.inspect(RIGHT, "receiver_ready")
                    if not obs_rr.value.get("ready"):
                        raise ValueError("Receiver not ready")
                
                # 8. Move to target using the ready receipt
                # "supplies that exact active item receipt on carried move to target"
                await robot.move(RIGHT, target, receipt=ready_receipt)
                
                # 9. Clear ready event after carried move
                clear_event_sync(ready_evt, ready_receipt)
                
                # 10. Release on target
                await robot.release(RIGHT, item, target)
                
                # 11. Depart target (immediately)
                await robot.move(RIGHT, right_home)
                
                # 12. Release tool
                await release_tool(RIGHT)
                
                # 13. Signal empty_0
                robot.signal(EMPTY_EVENT)
        finally:
            try:
                await release_tool(RIGHT)
            except Exception:
                pass

    # --- Main Execution ---
    # "B runs producer and consumer coroutines together"
    await asyncio.gather(producer(), consumer())
