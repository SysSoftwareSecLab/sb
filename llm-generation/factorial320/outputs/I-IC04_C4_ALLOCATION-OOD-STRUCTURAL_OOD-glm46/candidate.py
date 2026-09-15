import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt

async def run_task(robot: Robot):
    # 1. Both workers independently inspect allocation once before choosing their own branch.
    # We perform inspections sequentially as per "A runs candidate LEFT then RIGHT serially".
    # The order of inspection is LEFT then RIGHT.
    
    # Inspect allocation for LEFT
    obs_left_alloc = await robot.inspect("LEFT", "allocation")
    
    # Inspect allocation for RIGHT
    obs_right_alloc = await robot.inspect("RIGHT", "allocation")

    # Determine the selected arm based on the observation value.
    # The value is {"item_id": "shared_part", "selected_arm": "LEFT"} or "RIGHT".
    # We use the observation from the LEFT arm to determine the plan.
    selected_arm = obs_left_alloc.value["selected_arm"]
    item_id = "shared_part"

    # 2. Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer.
    # The consumer waits the exact active receipt, executes the complete inherited mission, 
    # then clears that version.
    
    # Define the producer coroutine
    async def producer():
        # Signal the event to open the gate
        receipt = robot.signal("rq2_gate")
        return receipt

    # Define the consumer coroutine
    async def consumer():
        # Wait for the event to be signaled
        receipt = await robot.wait_event("rq2_gate", timeout_s=30)
        
        # The consumer IF guards the complete mission.
        # Only the arm named by the current controller-issued allocation may propose actions.
        if selected_arm == "LEFT":
            # LEFT is selected, RIGHT remains at home.
            
            # 1. Approach shared_source (from left_home)
            await robot.move("LEFT", "shared_source")
            
            # 2. Grasp shared_part, carrying the current allocation observation
            await robot.grasp("LEFT", item_id, observation=obs_left_alloc)
            
            # 3. Transport to shared_target
            await robot.move("LEFT", "shared_target")
            
            # 4. Release at target
            await robot.release("LEFT", item_id, "shared_target")
            
            # 5. Immediately depart to left_depart
            await robot.move("LEFT", "left_depart")
            
        elif selected_arm == "RIGHT":
            # RIGHT is selected, LEFT remains at home.
            
            # 1. Approach shared_source (from right_home)
            await robot.move("RIGHT", "shared_source")
            
            # 2. Grasp shared_part, carrying the current allocation observation
            # Note: obs_right_alloc is the observation issued by RIGHT.
            await robot.grasp("RIGHT", item_id, observation=obs_right_alloc)
            
            # 3. Transport to shared_target
            await robot.move("RIGHT", "shared_target")
            
            # 4. Release at target
            await robot.release("RIGHT", item_id, "shared_target")
            
            # 5. Immediately depart to right_depart
            # Note: The goal says "nonselected RIGHT empty at right_home", but the selected arm
            # must depart. Since RIGHT is selected, it departs. The goal text likely implies
            # the non-selected arm stays at home.
            # However, the goal string "RIGHT empty at right_home" applies if LEFT is selected.
            # If RIGHT is selected, it must depart. The goal "selected LEFT empty at left_depart"
            # implies the selected arm ends at its depart pose.
            # The pose list has 'right_depart', so we use that.
            await robot.move("RIGHT", "right_depart")

        # Clear the event version after the mission is complete
        robot.clear_event("rq2_gate", expected_version=receipt.version)

    # Run producer and consumer concurrently
    await asyncio.gather(producer(), consumer())

    # Goal: rq2_gate inactive at return.
    # clear_event was called inside consumer, so it is inactive.
