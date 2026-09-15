import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt

async def run_task(robot: Robot):
    # Constants from task
    ALLOCATION_FACT = "allocation"
    SHARED_PART = "shared_part"
    GATE_EVENT = "rq2_gate"
    
    # Poses
    LEFT_HOME = "left_home"
    LEFT_DEPART = "left_depart"
    RIGHT_HOME = "right_home"
    RIGHT_DEPART = "right_depart"
    SHARED_SOURCE = "shared_source"
    SHARED_TARGET = "shared_target"

    # Arms
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    # 1. Both workers independently inspect allocation once before choosing their own branch.
    # This satisfies the first required order item.
    obs_left = await robot.inspect(LEFT, ALLOCATION_FACT)
    obs_right = await robot.inspect(RIGHT, ALLOCATION_FACT)

    # Determine selected arm from the observation
    # The observation value is {"item_id": "shared_part", "selected_arm": "LEFT"}
    selected_arm = obs_left.value["selected_arm"]
    
    # 2. Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer.
    # The consumer waits the exact active receipt, executes the complete inherited mission, 
    # then clears that version.
    # Use the development shape FOR -> IF -> PAR_JOIN.
    
    # We execute the loop once.
    for _ in range(1):
        # PAR_JOIN: Create producer and consumer tasks
        async def producer():
            # Signal the gate
            return robot.signal(GATE_EVENT)

        async def consumer():
            # Wait for the exact active receipt
            receipt = await robot.wait_event(GATE_EVENT, timeout_s=30)
            
            # Execute the complete inherited mission
            # "Only the arm named by the current controller-issued allocation may propose..."
            # "The selected grasp must carry that arm's own current allocation observation"
            
            # Select the observation corresponding to the selected arm
            current_obs = obs_left if selected_arm == LEFT else obs_right
            
            # Move to source (Approach)
            await robot.move(selected_arm, SHARED_SOURCE)
            
            # Grasp with observation
            await robot.grasp(selected_arm, SHARED_PART, observation=current_obs)
            
            # Move to target (Transport)
            await robot.move(selected_arm, SHARED_TARGET)
            
            # Release
            await robot.release(selected_arm, SHARED_PART, SHARED_TARGET)
            
            # Depart immediately
            depart_pose = LEFT_DEPART if selected_arm == LEFT else RIGHT_DEPART
            await robot.move(selected_arm, depart_pose)
            
            # Clear the event version
            robot.clear_event(GATE_EVENT, expected_version=receipt.version)

        # Run concurrently
        prod_task = asyncio.create_task(producer())
        cons_task = asyncio.create_task(consumer())
        
        await prod_task
        await cons_task

    # The unselected arm remains at home (no move/grasp/release calls made for it).
    # rq2_gate is cleared.
    # Goals met.
