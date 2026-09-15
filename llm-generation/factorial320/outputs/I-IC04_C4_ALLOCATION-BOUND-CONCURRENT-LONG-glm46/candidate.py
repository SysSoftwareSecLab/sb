import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    ALLOCATION_FACT = "allocation"
    SHARED_PART = "shared_part"
    EVENT_ID = "rq2_gate"
    RESOURCES = ["rq2_gap_0", "rq2_gap_1", "rq2_gap_2"]
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_DEPART = "left_depart"
    RIGHT_HOME = "right_home"
    RIGHT_DEPART = "right_depart"
    SHARED_SOURCE = "shared_source"
    SHARED_TARGET = "shared_target"

    async def worker(arm: str, home_pose: str, depart_pose: str):
        # 1. Inspect allocation
        obs = await robot.inspect(arm, ALLOCATION_FACT)
        
        # 2. Determine if selected
        # Observation value is JSON string: {"item_id": "shared_part", "selected_arm": "LEFT"}
        # We decode it to check the selected_arm field.
        val = obs.value
        is_selected = (val.get("selected_arm") == arm)
        
        if is_selected:
            # 3. Acquire resources in numeric order
            receipts = []
            for res_id in RESOURCES:
                # Acquire resource
                await robot.acquire(arm, res_id, 4.0)
                # Release resource immediately (OFF mode)
                await robot.release_resource(arm, res_id)
            
            # 4. Approach and Grasp
            # Approach sequence requires move to interaction_pose then immediate grasp
            await robot.move(arm, SHARED_SOURCE)
            # Grasp with the observation
            await robot.grasp(arm, SHARED_PART, observation=obs)
            
            # 5. Transport
            await robot.move(arm, SHARED_TARGET)
            
            # 6. Release and Depart
            await robot.release(arm, SHARED_PART, SHARED_TARGET)
            # Immediate departure
            await robot.move(arm, depart_pose)
        else:
            # Unselected arm stays at home
            pass

    # Main Logic
    # 1. Signal the gate
    gate_receipt = robot.signal(EVENT_ID)
    
    # 2. Start workers concurrently
    # Variant B: "B gathers them concurrently"
    await asyncio.gather(
        worker("LEFT", LEFT_HOME, LEFT_DEPART),
        worker("RIGHT", RIGHT_HOME, RIGHT_DEPART)
    )
    
    # 3. Wait for the gate
    # "wait its exact active receipt exactly once"
    await robot.wait_event(EVENT_ID, 4.0)
    
    # 4. Clear the event
    # "clear exactly that version after its assigned protected scope"
    robot.clear_event(EVENT_ID, expected_version=gate_receipt.version)
