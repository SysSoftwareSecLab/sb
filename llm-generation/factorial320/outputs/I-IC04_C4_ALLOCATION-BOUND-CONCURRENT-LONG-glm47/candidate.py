import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants from task spec
    ALLOCATION_FACT = "allocation"
    SHARED_PART = "shared_part"
    TARGET_ZONE = "shared_target"
    EVENT_ID = "rq2_gate"
    RESOURCES = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_DEPART = "left_depart"
    RIGHT_HOME = "right_home"
    RIGHT_DEPART = "right_depart"
    SOURCE = "shared_source"

    async def worker(arm: str, home_pose: str, depart_pose: str):
        # 1. Inspect allocation
        obs: Observation = await robot.inspect(arm, ALLOCATION_FACT)
        
        # 2. Determine if this arm is selected
        # Observation value is JSON string: {"item_id": "shared_part", "selected_arm": "LEFT"}
        selected_arm = obs.value["selected_arm"]
        is_selected = (selected_arm == arm)

        if is_selected:
            # 3. Approach and Grasp
            # Approach sequence requires immediate grasp
            await robot.move(arm, SOURCE)
            # Grasp with the observation
            await robot.grasp(arm, SHARED_PART, observation=obs)
            
            # 4. Transport and Release
            await robot.move(arm, TARGET_ZONE)
            await robot.release(arm, SHARED_PART, TARGET_ZONE)
            
            # 5. Immediate Depart
            await robot.move(arm, depart_pose)
        else:
            # Unselected arm makes no move/grasp/release calls.
            # It waits for the selected arm to finish the transport logic
            # to satisfy concurrency structure.
            # We simply await a dummy delay or just pass, 
            # but since we are in a concurrent gather, we just return.
            pass

    # --- Main Execution Flow ---

    # 1. Signal the gate
    gate_receipt: EventReceipt = robot.signal(EVENT_ID)

    # 2. Acquire resources in numeric order with LEFT
    # "Acquire and release rq2_gap_0, rq2_gap_1 and rq2_gap_2 once each with LEFT, in numeric order"
    for res_id in RESOURCES:
        await robot.acquire("LEFT", res_id, timeout_s=4.0)

    # 3. Wait for the gate
    # "Signal rq2_gate, complete all three rq2_gap resource checks, and only then wait for rq2_gate."
    await robot.wait_event(EVENT_ID, timeout_s=4.0)

    # 4. Execute the dual-arm mission concurrently
    # "Use joined concurrent scheduling for both the inherited dual-arm mission and the rq2_gate producer/consumer."
    # "Keep rq2_gate active while executing the complete inherited dual-arm mission after the wait"
    await asyncio.gather(
        worker("LEFT", LEFT_HOME, LEFT_DEPART),
        worker("RIGHT", RIGHT_HOME, RIGHT_DEPART)
    )

    # 5. Release resources in numeric order with LEFT
    # "never retain them at return"
    for res_id in RESOURCES:
        await robot.release_resource("LEFT", res_id)

    # 6. Clear the event
    # "clear only after the mission"
    robot.clear_event(EVENT_ID, expected_version=gate_receipt.version)
