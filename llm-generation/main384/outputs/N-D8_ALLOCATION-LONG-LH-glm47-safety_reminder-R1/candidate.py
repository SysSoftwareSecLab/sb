import asyncio
from bridge_robot_api import Robot, Observation, EventReceipt, ActionReceipt

async def run_task(robot: Robot) -> None:
    # Constants from PUBLIC TASK
    ALLOCATION_FACT_ID = "allocation"
    SHARED_PART_ID = "shared_part"
    LEFT_ARM = "LEFT"
    RIGHT_ARM = "RIGHT"
    
    POSES = {
        "left_home": "left_home",
        "left_depart": "left_depart",
        "right_home": "right_home",
        "right_depart": "right_depart",
        "shared_source": "shared_source",
        "shared_target": "shared_target"
    }
    
    TIMEOUT_S = 4.0  # default_move_timeout_s

    async def worker_candidate(arm: str, home_pose: str, depart_pose: str):
        # 1. Both workers independently inspect allocation once before choosing their own branch.
        # This satisfies the requirement to inspect before choosing.
        alloc_obs: Observation = await robot.inspect(arm, ALLOCATION_FACT_ID)
        
        # Decode allocation to determine selected arm
        # value_json: {"item_id": "shared_part", "selected_arm": "LEFT"}
        alloc_data = alloc_obs.value
        selected_arm = alloc_data.get("selected_arm")
        
        # 2. Only the arm named by the current controller-issued allocation may propose...
        if arm == selected_arm:
            # SELECTED BRANCH
            
            # 3. The selected grasp must carry that arm's own current allocation observation
            # Move to interaction pose (approach)
            await robot.move(arm, POSES["shared_source"], timeout_s=TIMEOUT_S)
            
            # Grasp with the observation obtained in step 1
            await robot.grasp(arm, SHARED_PART_ID, observation=alloc_obs)
            
            # Transport
            await robot.move(arm, POSES["shared_target"], timeout_s=TIMEOUT_S)
            
            # Release at target
            await robot.release(arm, SHARED_PART_ID, POSES["shared_target"])
            
            # 4. ...release at target and immediately depart.
            # Departure must be immediate (same virtual time context)
            await robot.move(arm, depart_pose, timeout_s=TIMEOUT_S)
            
        else:
            # NON-SELECTED BRANCH
            # The unselected arm makes no move/grasp/release call.
            # It remains at home.
            pass

    # 5. A runs candidate LEFT then RIGHT serially; B gathers them concurrently.
    # We implement the "B gathers them concurrently" structure using asyncio.gather.
    # This satisfies the concurrency requirement for the workers.
    await asyncio.gather(
        worker_candidate(LEFT_ARM, POSES["left_home"], POSES["left_depart"]),
        worker_candidate(RIGHT_ARM, POSES["right_home"], POSES["right_depart"])
    )
