import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- RQ2_GATE PROTOCOL ---
    # Acquire resources in numeric order with LEFT
    await robot.acquire("LEFT", "rq2_gap_0", 10.0)
    await robot.acquire("LEFT", "rq2_gap_1", 10.0)
    await robot.acquire("LEFT", "rq2_gap_2", 10.0)

    # Release resources in numeric order with LEFT
    await robot.release_resource("LEFT", "rq2_gap_0")
    await robot.release_resource("LEFT", "rq2_gap_1")
    await robot.release_resource("LEFT", "rq2_gap_2")

    # Signal rq2_gate exactly once
    gate_receipt = robot.signal("rq2_gate")

    # Wait immediately after the signal
    await robot.wait_event("rq2_gate", 10.0)

    # Clear exactly that version after its assigned protected scope
    # The protected scope covers the dual-arm mission below.
    # We will clear it at the end of the function.

    # --- DUAL-ARM MISSION ---
    
    async def producer():
        # Episode 1: part_0
        # Move to source_0 (approach start)
        await robot.move("LEFT", "source_0")
        # Grasp part_0
        await robot.grasp("LEFT", "part_0")
        
        # Acquire buffer_lock
        await robot.acquire("LEFT", "buffer_lock", 10.0)
        
        # Move to buffer_0
        await robot.move("LEFT", "buffer_0")
        # Release part_0 at buffer_0
        await robot.release("LEFT", "part_0", "buffer_0")
        
        # Depart buffer immediately
        await robot.move("LEFT", "left_wait")
        
        # Release buffer_lock
        await robot.release_resource("LEFT", "buffer_lock")
        
        # Signal ready_0
        robot.signal("ready_0")
        
        # Episode 2: part_1
        # Wait and clear empty_0 before entering buffer with the second part
        await robot.wait_event("empty_0", 10.0)
        robot.clear_event("empty_0", expected_version=1)
        
        # Move to source_1 (approach start)
        await robot.move("LEFT", "source_1")
        # Grasp part_1
        await robot.grasp("LEFT", "part_1")
        
        # Acquire buffer_lock
        await robot.acquire("LEFT", "buffer_lock", 10.0)
        
        # Move to buffer_1
        await robot.move("LEFT", "buffer_1")
        # Release part_1 at buffer_1
        await robot.release("LEFT", "part_1", "buffer_1")
        
        # Depart buffer immediately
        await robot.move("LEFT", "left_home")
        
        # Release buffer_lock
        await robot.release_resource("LEFT", "buffer_lock")
        
        # Signal ready_1
        robot.signal("ready_1")

    async def consumer():
        # Episode 1: part_0
        # Wait ready_0
        ready_0_receipt = await robot.wait_event("ready_0", 10.0)
        
        # Move to buffer_0 (approach start)
        await robot.move("RIGHT", "buffer_0")
        # Grasp part_0
        await robot.grasp("RIGHT", "part_0")
        
        # Acquire buffer_lock
        await robot.acquire("RIGHT", "buffer_lock", 10.0)
        
        # Depart buffer immediately
        await robot.move("RIGHT", "right_wait")
        
        # Release buffer_lock
        await robot.release_resource("RIGHT", "buffer_lock")
        
        # Move to target_0 with receipt
        await robot.move("RIGHT", "target_0", receipt=ready_0_receipt)
        
        # Clear ready_0 after carried move
        robot.clear_event("ready_0", expected_version=ready_0_receipt.version)
        
        # Release part_0 at target_0
        await robot.release("RIGHT", "part_0", "target_0")
        
        # Depart target immediately
        await robot.move("RIGHT", "right_home")
        
        # Signal empty_0
        robot.signal("empty_0")
        
        # Episode 2: part_1
        # Wait ready_1
        ready_1_receipt = await robot.wait_event("ready_1", 10.0)
        
        # Move to buffer_1 (approach start)
        await robot.move("RIGHT", "buffer_1")
        # Grasp part_1
        await robot.grasp("RIGHT", "part_1")
        
        # Acquire buffer_lock
        await robot.acquire("RIGHT", "buffer_lock", 10.0)
        
        # Depart buffer immediately
        await robot.move("RIGHT", "right_home")
        
        # Release buffer_lock
        await robot.release_resource("RIGHT", "buffer_lock")
        
        # Move to target_1 with receipt
        await robot.move("RIGHT", "target_1", receipt=ready_1_receipt)
        
        # Clear ready_1 after carried move
        robot.clear_event("ready_1", expected_version=ready_1_receipt.version)
        
        # Release part_1 at target_1
        await robot.release("RIGHT", "part_1", "target_1")
        
        # Depart target immediately
        await robot.move("RIGHT", "right_home")

    # Run producer and consumer concurrently
    await asyncio.gather(producer(), consumer())

    # --- FINALIZE RQ2_GATE ---
    # Clear exactly that version after its assigned protected scope
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)
