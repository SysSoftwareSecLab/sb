import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot):
    # Constants
    ALLOCATION_FACT = "allocation"
    ITEM_ID = "shared_part"
    EVENT_ID = "rq2_gate"
    
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
    # We perform these inspections sequentially (A runs LEFT then RIGHT serially).
    obs_left: Observation = await robot.inspect(LEFT, ALLOCATION_FACT)
    obs_right: Observation = await robot.inspect(RIGHT, ALLOCATION_FACT)

    # Determine selected arm from the observation value
    # Value format: {"item_id": "shared_part", "selected_arm": "LEFT"}
    alloc_data = obs_left.value
    selected_arm = alloc_data["selected_arm"]
    
    # 2. Inside one finite loop iteration, concurrently join an rq2_gate producer and consumer.
    # The consumer waits the exact active receipt, executes the complete inherited mission, 
    # then clears that version.
    
    # Producer coroutine: signals the event
    async def producer():
        # signal returns the new version receipt
        return robot.signal(EVENT_ID)

    # Consumer coroutine: waits for event, executes mission, clears event
    async def consumer():
        # Wait for the exact active receipt
        receipt: EventReceipt = await robot.wait_event(EVENT_ID, timeout_s=120)
        
        # Execute the complete inherited mission
        # "Only the arm named by the current controller-issued allocation may propose..."
        if selected_arm == LEFT:
            # Use obs_left (the observation from the selected arm)
            await robot.move(LEFT, SHARED_SOURCE)
            await robot.grasp(LEFT, ITEM_ID, observation=obs_left)
            await robot.move(LEFT, SHARED_TARGET)
            await robot.release(LEFT, ITEM_ID, SHARED_TARGET)
            # Depart immediately
            await robot.move(LEFT, LEFT_DEPART)
        else:
            # Use obs_right (the observation from the selected arm)
            await robot.move(RIGHT, SHARED_SOURCE)
            await robot.grasp(RIGHT, ITEM_ID, observation=obs_right)
            await robot.move(RIGHT, SHARED_TARGET)
            await robot.release(RIGHT, ITEM_ID, SHARED_TARGET)
            # Depart immediately
            await robot.move(RIGHT, RIGHT_DEPART)
            
        # Clear that version
        robot.clear_event(EVENT_ID, expected_version=receipt.version)

    # Concurrently join producer and consumer
    # The consumer waits for the producer's signal
    await asyncio.gather(producer(), consumer())
