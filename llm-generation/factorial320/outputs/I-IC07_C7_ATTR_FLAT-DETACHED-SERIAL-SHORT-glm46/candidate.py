import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # --- RQ2 Gate Protocol ---
    # Acquire resources in numeric order with LEFT
    await robot.acquire("LEFT", "rq2_gap_0", 4.0)
    await robot.acquire("LEFT", "rq2_gap_1", 4.0)
    await robot.acquire("LEFT", "rq2_gap_2", 4.0)
    
    # Release resources in numeric order with LEFT
    await robot.release_resource("LEFT", "rq2_gap_0")
    await robot.release_resource("LEFT", "rq2_gap_1")
    await robot.release_resource("LEFT", "rq2_gap_2")
    
    # Signal rq2_gate exactly once
    gate_receipt = robot.signal("rq2_gate")
    
    # Wait immediately after the signal
    await robot.wait_event("rq2_gate", 4.0)
    
    # Clear exactly that version after its assigned protected scope
    # (Scope ends before the inherited dual-arm mission)
    robot.clear_event("rq2_gate", expected_version=gate_receipt.version)

    # --- Inherited Dual-Arm Mission (Serial Scheduling) ---
    
    # Episode 1: part_0
    # Producer (LEFT)
    await robot.acquire("LEFT", "tool", 4.0)
    await robot.move("LEFT", "source_0")
    obs_p0 = await robot.grasp("LEFT", "part_0")
    
    await robot.acquire("LEFT", "buffer_lock", 4.0)
    await robot.move("LEFT", "buffer_0")
    await robot.release("LEFT", "part_0", "buffer_0")
    await robot.move("LEFT", "left_home")
    await robot.release_resource("LEFT", "buffer_lock")
    
    ready_0_receipt = robot.signal("ready_0")
    await robot.release_resource("LEFT", "tool")
    
    # Consumer (RIGHT)
    await robot.wait_event("ready_0", 4.0)
    await robot.acquire("RIGHT", "buffer_lock", 4.0)
    await robot.move("RIGHT", "buffer_0")
    await robot.grasp("RIGHT", "part_0")
    await robot.move("RIGHT", "target_0", receipt=ready_0_receipt)
    robot.clear_event("ready_0", expected_version=ready_0_receipt.version)
    await robot.release("RIGHT", "part_0", "target_0")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")
    
    empty_0_receipt = robot.signal("empty_0")

    # Episode 2: part_1
    # Producer (LEFT)
    await robot.wait_event("empty_0", 4.0)
    robot.clear_event("empty_0", expected_version=empty_0_receipt.version)
    
    await robot.acquire("LEFT", "tool", 4.0)
    await robot.move("LEFT", "source_1")
    obs_p1 = await robot.grasp("LEFT", "part_1")
    
    await robot.acquire("LEFT", "buffer_lock", 4.0)
    await robot.move("LEFT", "buffer_1")
    await robot.release("LEFT", "part_1", "buffer_1")
    await robot.move("LEFT", "left_home")
    await robot.release_resource("LEFT", "buffer_lock")
    
    ready_1_receipt = robot.signal("ready_1")
    await robot.release_resource("LEFT", "tool")
    
    # Consumer (RIGHT)
    await robot.wait_event("ready_1", 4.0)
    await robot.acquire("RIGHT", "buffer_lock", 4.0)
    await robot.move("RIGHT", "buffer_1")
    await robot.grasp("RIGHT", "part_1")
    await robot.move("RIGHT", "target_1", receipt=ready_1_receipt)
    robot.clear_event("ready_1", expected_version=ready_1_receipt.version)
    await robot.release("RIGHT", "part_1", "target_1")
    await robot.move("RIGHT", "right_home")
    await robot.release_resource("RIGHT", "buffer_lock")
    
    # Final state: empty_0 already signaled, buffer empty, lock free, events inactive
    # (ready_0, ready_1 cleared; empty_0 active as required by goal "empty_0" signal logic implies it stays active or is cleared? 
    # Goal says "events inactive" but also "empty_0" is a signal. 
    # Wait, goal says "events inactive". empty_0 is an event. 
    # However, "Consumer clears ready ... before publishing empty_0". 
    # "Producer waits and clears empty_0 before entering buffer with the second part." -> We did this.
    # "empty_0" is signaled at end of Ep 1. 
    # Goal: "events inactive". This implies we should clear empty_0 if it is active?
    # But "empty_0" is not cleared by anyone in the flow after Ep 1 signal.
    # Let's check goal again: "events inactive". 
    # If empty_0 is active at return, goal fails.
    # But there is no instruction to clear it after Ep 2.
    # Re-reading: "Consumer clears ready ... before publishing empty_0." -> Done.
    # "Producer waits and clears empty_0 before entering buffer with the second part." -> Done.
    # There is no instruction to clear the empty_0 signaled at the end of Ep 1.
    # However, if "events inactive" is a goal, maybe I should clear it?
    # Or maybe "events inactive" refers to the ready events?
    # "rq2_gate inactive at return" is explicit.
    # "events inactive" is general.
    # Let's assume the system clears it or it's not required to be cleared if not specified.
    # Actually, looking at "empty_0" definition: "program_clearable": true.
    # If I leave it active, I might fail "events inactive".
    # But I have no instruction to clear it.
    # I will stick to the explicit instructions.
