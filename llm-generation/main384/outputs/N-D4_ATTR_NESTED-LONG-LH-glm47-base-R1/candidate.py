import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt, MotionFault

async def run_task(robot: Robot):
    # Constants extracted from PUBLIC TASK
    ARMS = ["LEFT", "RIGHT"]
    PARTS = ["part_0", "part_1"]
    SOURCES = {"part_0": "source_0", "part_1": "source_1"}
    TARGETS = {"part_0": "target_0", "part_1": "target_1"}
    BUFFER_POSES = {"part_0": "buffer_0", "part_1": "buffer_1"}
    READY_EVENTS = {"part_0": "ready_0", "part_1": "ready_1"}
    EMPTY_EVENT = "empty_0"
    LOCK_ID = "buffer_lock"
    TOOL_ID = "tool"
    
    # Helper to release tool safely
    async def release_tool_safely(arm: str):
        try:
            await robot.set_mode(arm, TOOL_ID, "OFF")
            await robot.release_resource(arm, TOOL_ID)
        except Exception:
            pass

    # Producer coroutine (LEFT arm)
    async def producer():
        try:
            # LONG variant: Acquire tool before source pickup
            await robot.acquire("LEFT", TOOL_ID, 4.0)
            await robot.set_mode("LEFT", TOOL_ID, "LEFT_PROFILE")

            for i, part_id in enumerate(PARTS):
                source = SOURCES[part_id]
                buffer_pose = BUFFER_POSES[part_id]
                ready_event = READY_EVENTS[part_id]
                
                # Initial pose for approach
                start_pose = "left_home" if i == 0 else "left_wait"
                
                # 1. Acquire buffer lock
                await robot.acquire("LEFT", LOCK_ID, 4.0)
                
                # 2. Approach and Grasp
                await robot.move("LEFT", start_pose)
                await robot.move("LEFT", source) # Approach
                obs = await robot.grasp("LEFT", part_id) # Grasp
                
                # 3. Move to buffer and Release
                await robot.move("LEFT", buffer_pose)
                await robot.release("LEFT", part_id, buffer_pose)
                
                # 4. Depart buffer immediately
                await robot.move("LEFT", start_pose)
                
                # 5. Release buffer lock
                await robot.release_resource("LEFT", LOCK_ID)
                
                # 6. Signal ready
                robot.signal(ready_event, part_id)
                
                # 7. Wait for empty_0 before second item entry
                if i == 0:
                    # Wait for consumer to signal empty_0
                    await robot.wait_event(EMPTY_EVENT, 50.0)
                    # Clear empty_0
                    robot.clear_event(EMPTY_EVENT, expected_version=1)
                else:
                    # After second item, release tool
                    await release_tool_safely("LEFT")
                    
        except Exception:
            await release_tool_safely("LEFT")
            raise

    # Consumer coroutine (RIGHT arm)
    async def consumer():
        try:
            for i, part_id in enumerate(PARTS):
                buffer_pose = BUFFER_POSES[part_id]
                target = TARGETS[part_id]
                ready_event = READY_EVENTS[part_id]
                
                # 1. Wait for ready event
                ready_receipt = await robot.wait_event(ready_event, 50.0)
                
                # 2. Acquire buffer lock
                await robot.acquire("RIGHT", LOCK_ID, 4.0)
                
                # 3. Approach and Grasp
                start_pose = "right_home" if i == 0 else "right_wait"
                await robot.move("RIGHT", start_pose)
                await robot.move("RIGHT", buffer_pose) # Approach
                obs = await robot.grasp("RIGHT", part_id) # Grasp
                
                # 4. Depart buffer immediately
                await robot.move("RIGHT", start_pose)
                
                # 5. Release buffer lock
                await robot.release_resource("RIGHT", LOCK_ID)
                
                # 6. Perform checks for second item (i == 1)
                if i == 1:
                    # LONG variant: Acquire tool after wait and checks
                    await robot.acquire("RIGHT", TOOL_ID, 4.0)
                    await robot.set_mode("RIGHT", TOOL_ID, "RIGHT_PROFILE")
                    
                    # D4: Join checks with asyncio.gather
                    await asyncio.gather(
                        robot.inspect("LEFT", "line_clear"),
                        robot.inspect("RIGHT", "receiver_ready")
                    )
                
                # 7. Move to target with receipt
                await robot.move("RIGHT", target, receipt=ready_receipt)
                
                # 8. Clear ready event after carried move
                robot.clear_event(ready_event, expected_version=ready_receipt.version)
                
                # 9. Release and depart
                await robot.release("RIGHT", part_id, target)
                await robot.move("RIGHT", start_pose)
                
                # 10. Signal empty_0
                robot.signal(EMPTY_EVENT)
                
                # Release tool if held (only for i == 1)
                if i == 1:
                    await release_tool_safely("RIGHT")
                    
        except Exception:
            await release_tool_safely("RIGHT")
            raise

    # Run both coroutines concurrently
    await asyncio.gather(producer(), consumer())
